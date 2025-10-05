# KubeQuery RAG Application

A **Retrieval-Augmented Generation (RAG)** system that answers Kubernetes-related questions using official documentation from the [Kubernetes GitHub repository](https://github.com/kubernetes/website).  
It combines **hybrid retrieval (keyword + vector)** search using **Elasticsearch**, response generation with **OpenAI GPT-4o**, evaluation of retrieval and LLM performance, an interactive **Streamlit UI**, and **Grafana monitoring** — all fully containerized with **Docker Compose**.

---

## 1. 🧩 Problem Description

Kubernetes documentation is vast, and developers often struggle to find concise, accurate answers quickly.  
This project solves that by building a **question-answering system** that:

- Retrieves the most relevant documentation chunks.
- Uses an LLM to synthesize answers from those chunks.
- Evaluates and monitors retrieval and response performance.
- Provides a UI for users to interact, rate responses, and visualize system metrics.

---

## 2. 🔍 Retrieval Flow

The application follows a standard **RAG architecture** combining both a **knowledge base** and an **LLM**:

1. **Knowledge Base:**  
   - Source: Kubernetes official GitHub repository (`/glossary`, `/kubectl` directories).  
   - Files: Markdown (`.md`) → JSON transformation via a Python script.  
   - Size: ~1.65 MB of curated, cleaned data.

2. **Retrieval:**
   - **Keyword Search:** Elasticsearch BM25 index.  
   - **Vector Search:** Elasticsearch KNN index using OpenAI’s `text-embedding-3-large` embeddings.  
   - **Hybrid Search:** Combines keyword and vector scores for best retrieval.  
   - **Document Re-ranking:** Applied during evaluation to refine top-K results.

3. **Generation:**
   - Context from top 5 retrieved docs is passed to **OpenAI GPT-4o** for response generation.

4. **User Interaction Flow:**
   ```
   User Query → Retrieval (Keyword + KNN) → Top 5 Docs → GPT-4o → Answer → User Feedback
   ```

---

## 3. 📊 Retrieval Evaluation

To ensure optimal retrieval quality, multiple methods were evaluated:

| Retrieval Method | Hit Rate | MRR  |
|------------------|----------|------|
| Keyword (BM25) | 0.9375 | 0.8643 |
| Minsearch | 0.7765 | 0.5909 |
| FAISS Vector Search | 0.95127 | 0.88624|
| Hybrid (Keyword + KNN) | **0.9756** | **0.9772** |
| Hybrid + Re-ranking | 0.9534 | 0.8778 |

 Search evaluation notebooks: 
 https://github.com/sindhurauppu/k8s-assistant/blob/main/notebooks/evaluate-search.ipynb
 https://github.com/sindhurauppu/k8s-assistant/blob/main/notebooks/hybrid-search.ipynb

✅ **Best performing method:** **Hybrid (Keyword + KNN)**  
This configuration is used in the final system for all user queries.

---

## 4. 🤖 LLM Evaluation

Two evaluation strategies were used to measure answer quality:

### 1. **Cosine Similarity (Embedding-based)**
| Model | Mean Similarity | Std Dev | Min | Max |
|--------|----------------|----------|-----|-----|
| GPT-4o | 0.9186 | 0.0478 | 0.7217 | 1.000 |
| GPT-3.5-Turbo | 0.9187 | 0.0481 | 0.7135 | 0.999 |

Both models produced similar semantic similarity scores, but GPT-4o’s contextual accuracy was superior.

### 2. **LLM-as-a-Judge Evaluation**
Two prompting techniques were tested for answer relevance classification (`RELEVANT`, `PARTLY_RELEVANT`, `NON_RELEVANT`):

| Prompt Technique | RELEVANT | PARTLY | NON |
|------------------|-----------|--------|-----|
| Answer–Question–Answer | 109 | 38 | 3 |
| Question–Answer | **102** | **42** | **6** |

Evaluation notebook: 
https://github.com/sindhurauppu/k8s-assistant/blob/main/notebooks/evaluate-rag.ipynb 

✅ **Chosen Technique:** *Question–Answer* prompt  
This approach was integrated into the live system to automatically assess real user responses.

---

## 5. 💻 Interface

The application includes a **Streamlit UI** for interactive Q&A:

- 🔎 **Search bar** to enter Kubernetes questions  
- 🤖 **Ask button** to trigger RAG workflow  
- 📚 **Source display** showing top 5 retrieved docs  
- 👍/👎 **Feedback buttons** for user relevance feedback  

---

## 6. ⚙️ Ingestion Pipeline

Automated ingestion handled by `ingest.py` during container startup:

1. Initializes Elasticsearch indices (BM25 + KNN).  
2. Prepares the PostgreSQL database with metadata tables.  

Executed automatically when containers spin up — no manual steps required.

---

## 7. 🔁 Reproducibility

- **Dataset:** Kubernetes official website repo (openly available).  
- **Dependencies:** All versions pinned in `requirements.txt` and `docker-compose.yml`.  
- **Environment:** Python 3.10+, Docker 24+.  
- **Setup:** One-command deployment via Docker Compose.  
- **Configuration:** All credentials via `.env` file.  

This ensures the system can be reproduced end-to-end by any user.

### Run locally:
```bash
git clone https://github.com/sindhurauppu/k8s-assistant.git
cd app
cp .env.example .env
Update OPENAI_API_KEY and POSTGRES password in .env
docker-compose up --build
Wait until ingest container is completed and streamlit, grafana containers start.
```

### Code:
The application code is in `app/` directory.

- The Streamlit application code is in `app.py`
- RAG flow is in `rag.py`, `index-documents.py` contains Elastic Search indexing code that will be run at the start of the system.
- Postgres tables and db procedures are in `db.py`

## 8. 📈 Monitoring & Feedback

Real-time monitoring is implemented through **Grafana** with a **PostgreSQL data source**.  
The dashboard includes five key panels:

1. ⏱️ Response Time Over Time  
2. 📊 Relevancy Distribution (RELEVANT / PARTLY / NON)  
3. 👍👎 User Feedback Summary  
4. 💬 Last 5 Conversations  
5. 💰 OpenAI Token Usage Over Time  

All metrics are logged in PostgreSQL and updated dynamically.

---

## 9. 🐳 Containerization

The entire system runs via **Docker Compose**, including:

- `streamlit-app` — Frontend UI  
- `elasticsearch` — Search index  
- `postgres` — Data storage  
- `grafana` — Monitoring dashboard  
- `ingest` — Dataset ingestion service  

### Example `.env` file:
```bash
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_PASSWORD=your_password
POSTGRES_USER=postgres
POSTGRES_DB=ragsystem
```

---


## 10. 🌟 Best Practices Followed

| Category | Technique | Status |
|-----------|------------|--------|
| **Hybrid Search** | Keyword (BM25) + KNN vector retrieval
| **Document Re-ranking** | Post-retrieval similarity reranking
| **Query Rewriting** | OpenAI GPT-4o used

---


## 🧩 Architecture Overview

```
                ┌──────────────────────────────┐
                │      Streamlit UI            │
                │  (User Query + Feedback)     │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │   RAG Backend (Python)       │
                │ Retrieval + GPT-4o Response  │
                └───────┬──────────┬───────────┘
                        │          │
         ┌──────────────┘          └──────────────┐
         ▼                                         ▼
 ┌────────────────┐                      ┌────────────────┐
 │ Elasticsearch  │ ←─ BM25 + KNN Index │ PostgreSQL DB  │
 │ (Hybrid Search)│                      │ (Logs + Metrics)│
 └────────────────┘                      └────────────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │   Grafana Dashboard│
                    │   (Monitoring)     │
                    └────────────────────┘
```

---

## 🧑‍💻 Author

**Sindhura Uppu**  
💡 Built as a personal GenAI project to explore RAG systems, retrieval evaluation, and full-stack observability for AI applications.

---

## 🪄 License

MIT License © 2025 Sindhura Uppu
