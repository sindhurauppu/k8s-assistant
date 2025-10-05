import json
import os
from pathlib import Path
from tqdm.auto import tqdm
from sentence_transformers import SentenceTransformer
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_documents(file_path='../data/docs-ids.json'):
    """Load documents from JSON file"""
    with open(file_path, 'rt') as f_in:
        documents = json.load(f_in)
    return documents


def encode_documents(documents, model_name='multi-qa-MiniLM-L6-cos-v1'):
    """Encode documents with sentence transformers"""
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)
    
    print("Encoding documents...")
    for doc in tqdm(documents, desc="Encoding"):
        title = doc['title']
        text = doc['text']
        title_text = title + ' ' + text
        
        doc['title_vector'] = model.encode(title).tolist()
        doc['text_vector'] = model.encode(text).tolist()
        doc['title_text_vector'] = model.encode(title_text).tolist()
    
    return documents


def create_index(es_client, index_name):
    """Create Elasticsearch index with proper mappings"""
    index_settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "title": {"type": "keyword"},
                "source_file": {"type": "text"},
                "id": {"type": "keyword"},
                "title_vector": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                },
                "text_vector": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                },
                "title_text_vector": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                },
            }
        }
    }
    
    # Delete index if it exists
    if es_client.indices.exists(index=index_name):
        print(f"Deleting existing index: {index_name}")
        es_client.indices.delete(index=index_name)
    
    # Create new index
    print(f"Creating index: {index_name}")
    es_client.indices.create(index=index_name, body=index_settings)


def index_documents(es_client, documents, index_name):
    """Index documents into Elasticsearch"""
    print("Indexing documents...")
    for doc in tqdm(documents, desc="Indexing"):
        es_client.index(index=index_name, document=doc)
    
    print(f"Successfully indexed {len(documents)} documents!")


def main():
    # Get configuration from environment
    es_host = os.environ.get('ELASTICSEARCH_HOST', 'http://localhost:9200')
    index_name = os.environ.get('ELASTICSEARCH_INDEX', 'k8s-questions')
    model_name = os.environ.get('SENTENCE_TRANSFORMER_MODEL', 'multi-qa-MiniLM-L6-cos-v1')
    docs_path = os.environ.get('DOCS_PATH', '../data/docs-ids.json')
    
    print("=" * 50)
    print("Kubernetes Q&A Indexing Script")
    print("=" * 50)
    print(f"Elasticsearch: {es_host}")
    print(f"Index name: {index_name}")
    print(f"Model: {model_name}")
    print(f"Documents: {docs_path}")
    print("=" * 50)
    
    # Check if documents file exists
    if not Path(docs_path).exists():
        print(f"Error: Documents file not found at {docs_path}")
        return 1
    
    try:
        # Connect to Elasticsearch
        print("\nConnecting to Elasticsearch...")
        es_client = Elasticsearch(es_host)
        
        # Wait for Elasticsearch to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                if es_client.ping():
                    print("✓ Connected to Elasticsearch")
                    break
            except:
                pass
            if i < max_retries - 1:
                print(f"Waiting for Elasticsearch... ({i+1}/{max_retries})")
                import time
                time.sleep(2)
        else:
            print("Error: Cannot connect to Elasticsearch after retries.")
            return 1
        
        # Load documents
        print("\nLoading documents...")
        documents = load_documents(docs_path)
        print(f"✓ Loaded {len(documents)} documents")
        
        # Encode documents
        documents = encode_documents(documents, model_name)
        print("✓ Encoded all documents")
        
        # Create index
        create_index(es_client, index_name)
        print("✓ Index created")
        
        # Index documents
        index_documents(es_client, documents, index_name)
        print("✓ Documents indexed")
        
        print("\n" + "=" * 50)
        print("✓ Indexing completed successfully!")
        print("=" * 50)
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())