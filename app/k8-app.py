import streamlit as st
import time

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import json
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

es_client = Elasticsearch('http://localhost:9200') 

model_name = 'multi-qa-MiniLM-L6-cos-v1'
model = SentenceTransformer(model_name)


def elastic_search(field, query, vector, index_name="k8s-questions"):
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

    es_results = es_client.search(
        index=index_name,
        knn=knn_query,
        query=keyword_query,
        size=5,
        _source=["text", "title", "source_file", "id"]
    )

    result_docs = []
    
    for hit in es_results['hits']['hits']:
        result_docs.append(hit['_source'])

    return result_docs

    


def build_prompt(query, search_results):
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

def llm(prompt):
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content

def rag(query):
    v_q = model.encode(query)
    print("Vector encoding done")
    search_results = elastic_search('title_vector', query, v_q)
    print("Search results from elastic: ", search_results)
    prompt = build_prompt(query, search_results)
    print("Prompt: ", prompt)
    answer = llm(prompt)
    print("Answer: ", answer)
    return answer


def main():
    st.title("KubeQuery RAG Application")

    user_input = st.text_input("Enter your input:")

    if st.button("Ask"):
        with st.spinner('Processing...'):
            output = rag(user_input)
            st.success("Completed!")
            st.write(output)

if __name__ == "__main__":
    main()