import os
import time
import json
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from openai import OpenAI


class RAGSystem:
    def __init__(self):
        """Initialize RAG system with Elasticsearch, OpenAI, and SentenceTransformer"""
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        es_host = os.environ.get("ELASTICSEARCH_HOST", "http://localhost:9200")
        self.es_client = Elasticsearch(es_host)
        
        model_name = os.environ.get("SENTENCE_TRANSFORMER_MODEL", "multi-qa-MiniLM-L6-cos-v1")
        self.model = SentenceTransformer(model_name)
        
        self.index_name = os.environ.get("ELASTICSEARCH_INDEX", "k8s-questions")
        
        # OpenAI pricing (per 1M tokens) - GPT-4o
        self.pricing = {
            'gpt-4o': {
                'prompt': 2.50,  # $2.50 per 1M input tokens
                'completion': 10.00  # $10.00 per 1M output tokens
            }
        }
        
        # Check if index exists - initialize to False by default
        self.index_exists = False
        try:
            self.index_exists = self.check_index_exists()
        except Exception as e:
            print(f"Warning: Could not check index existence: {e}")
    
    def check_index_exists(self):
        """Check if Elasticsearch index exists"""
        try:
            return self.es_client.indices.exists(index=self.index_name)
        except Exception as e:
            print(f"Error checking index: {e}")
            return False
    
    def elastic_search(self, field, query, vector):
        """
        Perform hybrid search using both vector (knn) and keyword search
        
        Args:
            field: Field name for vector search
            query: Text query for keyword search
            vector: Query vector for knn search
            
        Returns:
            List of documents from search results
        """
        knn_query = {
            "field": field,
            "query_vector": vector,
            "k": 5,
            "num_candidates": 10000,
            "boost": 0.5
        }

        keyword_query = {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title", "text"],
                        "type": "best_fields",
                        "boost": 0.5,
                    }
                }
            }
        }

        es_results = self.es_client.search(
            index=self.index_name,
            knn=knn_query,
            query=keyword_query,
            size=5,
            _source=["text", "title", "source_file", "id"]
        )

        result_docs = []
        
        for hit in es_results['hits']['hits']:
            result_docs.append(hit['_source'])

        return result_docs

    def build_prompt(self, query, search_results):
        """
        Build prompt for LLM using query and search results
        
        Args:
            query: User's question
            search_results: List of relevant documents
            
        Returns:
            Formatted prompt string
        """
        prompt_template = """
You are a Kubernetes assistant. Use ONLY the information in the "context" to answer the user's question.

REQUIREMENTS:
- Output ONLY raw Markdown text (no surrounding quotes, no JSON, no markdown in a string).
- Use literal line breaks for paragraphs and fenced code blocks for commands (```bash ... ```).
- Do NOT include backslash-n sequences ("\n") to indicate newlines — use real newlines.
- Do not escape code blocks or wrap them in a string.
- Return the answer only (no meta commentary).

Example of desired output:
To apply a YAML file in Kubernetes, use the following command:

```bash
kubectl apply -f FILENAME.yaml
```

Context:
{context}

User's Question:
{question}

Answer:
""".strip()

        context = ""
        
        for doc in search_results:
            context = context + f"title: {doc['title']}\nanswer: {doc['text']}\n\n"
        
        prompt = prompt_template.format(question=query, context=context).strip()
        return prompt

    def llm(self, prompt, model='gpt-4o'):
        """
        Get response from OpenAI LLM
        
        Args:
            prompt: Formatted prompt string
            model: OpenAI model to use
            
        Returns:
            tuple: (response_text, prompt_tokens, completion_tokens, total_tokens)
        """
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract token usage
        usage = response.usage
        
        return (
            response.choices[0].message.content,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens
        )
    
    def calculate_openai_cost(self, model, prompt_tokens, completion_tokens):
        """Calculate the cost of OpenAI API call"""
        if model not in self.pricing:
            return 0.0
        
        prompt_cost = (prompt_tokens / 1_000_000) * self.pricing[model]['prompt']
        completion_cost = (completion_tokens / 1_000_000) * self.pricing[model]['completion']
        
        return prompt_cost + completion_cost
    
    def evaluate_relevance(self, question, answer):
        """
        Evaluate the relevance of the answer to the question
        
        Returns:
            tuple: (relevance, explanation, eval_prompt_tokens, eval_completion_tokens, eval_total_tokens)
        """
        prompt_template = """
You are an expert evaluator for a Retrieval-Augmented Generation (RAG) system.
Your task is to analyze the relevance of the generated answer to the given question.
Based on the relevance of the generated answer, you will classify it
as "NON_RELEVANT", "PARTLY_RELEVANT", or "RELEVANT".

Here is the data for evaluation:

Question: {question}
Generated Answer: {answer}

Please analyze the content and context of the generated answer in relation to the question
and provide your evaluation in parsable JSON without using code blocks:

{{
  "Relevance": "NON_RELEVANT" | "PARTLY_RELEVANT" | "RELEVANT",
  "Explanation": "[Provide a brief explanation for your evaluation]"
}}
""".strip()
        
        prompt = prompt_template.format(question=question, answer=answer)
        
        try:
            evaluation, eval_prompt_tokens, eval_completion_tokens, eval_total_tokens = self.llm(prompt, model='gpt-4o')
            
            # Parse JSON response
            eval_json = json.loads(evaluation)
            relevance = eval_json.get('Relevance', 'UNKNOWN')
            explanation = eval_json.get('Explanation', 'No explanation provided')
            
            return relevance, explanation, eval_prompt_tokens, eval_completion_tokens, eval_total_tokens
        except Exception as e:
            print(f"Error evaluating relevance: {e}")
            return 'UNKNOWN', f'Error: {str(e)}', 0, 0, 0
    
    def rewrite_query(self, user_query):
        prompt = f"""
        Rewrite the following Kubernetes-related question so that it matches documentation terminology and includes key Kubernetes resource names:
        "{user_query}"
        Return only the rewritten query.
        """

        return prompt

    def query(self, user_query):
        """
        Main RAG pipeline: encode query, search, build prompt, get answer
        
        Args:
            user_query: User's question
            
        Returns:
            dict: Contains answer, search_results, metrics, and relevance evaluation
        """
        start_time = time.time()
        
        # Recheck if index exists (in case it was created after initialization)
        self.index_exists = self.check_index_exists()
        
        # Check if index exists
        if not self.index_exists:
            error_msg = (
                f"Elasticsearch index '{self.index_name}' not found. "
                f"Please run 'python index_documents.py' to create and populate the index."
            )
            raise Exception(error_msg)

        user_query_prompt = rewrite_query(user_query)
        user_query_rewritten, user_prompt_tokens, user_completion_tokens, user_total_tokens = llm(user_query_prompt)
        
        # Encode query to vector
        v_q = self.model.encode(user_query_rewritten)
        print("Vector encoding done")
        
        # Search Elasticsearch
        search_results = self.elastic_search('title_vector', user_query_rewritten, v_q)
        print("Search results from elastic: ", search_results)
        
        # Build prompt with context
        prompt = self.build_prompt(user_query_rewritten, search_results)
        print("Prompt: ", prompt)
        
        # Get answer from LLM with token tracking
        answer, prompt_tokens, completion_tokens, total_tokens = self.llm(prompt)
        print("Answer: ", answer)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Calculate OpenAI cost
        openai_cost = self.calculate_openai_cost('gpt-4o', prompt_tokens, completion_tokens)
        
        # Evaluate relevance
        relevance, explanation, eval_prompt_tokens, eval_completion_tokens, eval_total_tokens = \
            self.evaluate_relevance(user_query_rewritten, answer)
        
        # Calculate total cost including evaluation
        total_eval_cost = self.calculate_openai_cost('gpt-4o', eval_prompt_tokens, eval_completion_tokens)
        total_cost = openai_cost + total_eval_cost
        
        return {
            'answer': answer,
            'search_results': search_results,
            'response_time': response_time,
            'relevance': relevance,
            'relevance_explanation': explanation,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'eval_prompt_tokens': eval_prompt_tokens,
            'eval_completion_tokens': eval_completion_tokens,
            'eval_total_tokens': eval_total_tokens,
            'openai_cost': total_cost
        }