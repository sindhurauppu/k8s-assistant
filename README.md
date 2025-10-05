# KubeQuery RAG Application

A **Retrieval-Augmented Generation (RAG)** system that answers Kubernetes-related questions using official documentation from the [Kubernetes GitHub repository](https://github.com/kubernetes/website).  
It combines **hybrid retrieval (keyword + vector)** search using **Elasticsearch**, response generation with **OpenAI GPT-4o**, evaluation of retrieval and LLM performance, an interactive **Streamlit UI**, and **Grafana monitoring** — all fully containerized with **Docker Compose**.

---

## 🌐 Access Points

After running `docker compose up --build -d`:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Streamlit App** | http://localhost:8501 | None |
| **Grafana Dashboard** | http://localhost:3000 | admin / admin |
| **Elasticsearch** | http://localhost:9200 | None |
| **PostgreSQL** | localhost:5432 | postgres / (from .env) |

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
   - **Vector Search:** Elasticsearch KNN index using OpenAI's `text-embedding-3-large` embeddings.  
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

📓 Search evaluation notebooks: 
- https://github.com/sindhurauppu/k8s-assistant/blob/main/notebooks/evaluate-search.ipynb
- https://github.com/sindhurauppu/k8s-assistant/blob/main/notebooks/hybrid-search.ipynb

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

Both models produced similar semantic similarity scores, but GPT-4o's contextual accuracy was superior.

### 2. **LLM-as-a-Judge Evaluation**
Two prompting techniques were tested for answer relevance classification (`RELEVANT`, `PARTLY_RELEVANT`, `NON_RELEVANT`):

| Prompt Technique | RELEVANT | PARTLY | NON |
|------------------|-----------|--------|-----|
| Answer–Question–Answer | 109 | 38 | 3 |
| Question–Answer | **102** | **42** | **6** |

📓 Evaluation notebook: 
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
- 🎯 **Relevance indicator** showing automatic evaluation (🟢 RELEVANT / 🟡 PARTLY_RELEVANT / 🔴 NON_RELEVANT)
- ⏱️ **Response time** and 💰 **cost** displayed for each query

---

## 6. ⚙️ Ingestion Pipeline

Automated ingestion handled by `index_documents.py` during container startup:

1. Initializes Elasticsearch indices (BM25 + KNN).  
2. Encodes documents using sentence transformers.
3. Indexes 229 Kubernetes documentation files.
4. Prepares the PostgreSQL database with metadata tables.  

Executed automatically when containers spin up — no manual steps required.

---

## 7. 📚 Dataset Details

- **Source**: [Kubernetes Official Documentation](https://github.com/kubernetes/website)
- **Directories Used**: `/content/en/docs/reference/kubectl/`, `/content/en/docs/reference/glossary/`
- **Total Documents**: 229 markdown files
- **Size**: ~1.65 MB (cleaned)
- **Format**: Markdown → JSON (with metadata)
- **Processing**: Automated via `index_documents.py`
- **Embeddings**: Sentence Transformers `multi-qa-MiniLM-L6-cos-v1` (384 dimensions)

---

## 8. 🛠️ Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit 1.31.0 |
| LLM | OpenAI GPT-4o |
| Embeddings | Sentence Transformers (multi-qa-MiniLM-L6-cos-v1) |
| Vector DB | Elasticsearch 8.9.0 (KNN) |
| Database | PostgreSQL 15 |
| Monitoring | Grafana Latest |
| Containerization | Docker Compose |
| Language | Python 3.8 |

---

## 9. 📈 Monitoring & Feedback

Real-time monitoring via **Grafana** dashboard at http://localhost:3000

**Metrics Tracked:**
- ⏱️ **Response Time** - Average and trends over time
- 🎯 **Relevance Distribution** - RELEVANT (🟢) / PARTLY_RELEVANT (🟡) / NON_RELEVANT (🔴)
- 👍👎 **User Feedback** - Positive vs negative ratings
- 💬 **Last 5 Conversations** - Recent Q&A with metadata
- 🪙 **Token Usage** - Prompt and completion tokens over time
- 💰 **OpenAI Costs** - Real-time API cost tracking ($2.50/1M input tokens, $10/1M output tokens)

All metrics are stored in PostgreSQL and auto-evaluated using GPT-4o for relevance assessment.

**Dashboard Features:**
- Auto-refresh every 30 seconds
- Filterable by time range (last 24h, 7d, 30d)
- Exportable queries and panels
- Custom SQL queries supported

---

## 10. 📋 Prerequisites

Before running the application, ensure you have:

- **Docker** 24+ and **Docker Compose** v2.0+
- **OpenAI API Key** (with GPT-4o access)
- **8GB RAM minimum** (Elasticsearch needs 4GB)
- **10GB free disk space**
- **Ports available**: 8501, 3000, 9200, 5432

---

## 11. 🔄 Reproducibility

- **Dataset:** Kubernetes official website repo (openly available).  
- **Dependencies:** All versions pinned in `requirements.txt` and `docker-compose.yml`.  
- **Environment:** Python 3.8+, Docker 24+.  
- **Setup:** One-command deployment via Docker Compose.  
- **Configuration:** All credentials via `.env` file.  

This ensures the system can be reproduced end-to-end by any user.

### Run locally:

```bash
# 1. Clone the repository
git clone https://github.com/sindhurauppu/k8s-assistant.git
cd k8s-assistant/app

# 2. Set up environment variables
cp .env.example .env
# Edit .env and add:
# - OPENAI_API_KEY=sk-your-key-here
# - POSTGRES_PASSWORD=your_secure_password

# 3. Create Grafana directories
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards
mkdir -p grafana/dashboards

# 4. Start all services
docker compose up --build -d

# 5. Monitor startup progress
docker compose logs -f ingest  # Wait for "✓ Indexing completed successfully!"
docker compose logs -f streamlit

# 6. Access the application
# - Streamlit UI: http://localhost:8501
# - Grafana Dashboard: http://localhost:3000 (admin/admin)
```

### Verify Installation:

```bash
# Check all services are running
docker compose ps

# Should show:
# - elasticsearch (healthy)
# - postgres (healthy)  
# - streamlit (healthy)
# - grafana (running)
# - ingest (exited with code 0)

# Test Elasticsearch
curl http://localhost:9200/_cat/indices

# Test PostgreSQL
docker exec -it postgres psql -U postgres -d rag_feedback -c "\dt"
```

---

## 12. 🗂️ Code Structure

The application code is in the `app/` directory:

```
app/
├── app.py                      # Streamlit UI application
├── rag.py                      # RAG logic with monitoring
├── db.py                       # PostgreSQL operations
├── index_documents.py          # Elasticsearch indexing
├── docker-compose.yaml         # Container orchestration
├── Dockerfile.streamlit        # Streamlit container
├── Dockerfile.ingest          # Ingestion container
├── requirements.txt           # Python dependencies
├── requirements-ingest.txt    # Ingestion dependencies
├── init_db.sql                # Database initialization
├── .env                       # Environment variables (create from .env.example)
├── data/
│   └── docs-ids.json          # Kubernetes documentation
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── postgres.yml   # PostgreSQL datasource
    │   └── dashboards/
    │       └── default.yml    # Dashboard config
    └── dashboards/
        └── rag_monitoring.json # Main dashboard
```

---

## 13. 🔧 Troubleshooting

### Ingest container hangs or shows OpenBLAS warning
```bash
docker compose logs ingest
# If stuck with OpenBLAS warning, it will eventually complete (2-5 minutes)
# The warning is harmless - encoding 229 documents just takes time
```

### Grafana dashboard is empty
- Ask 3-5 questions in Streamlit first to generate data
- Adjust time range in Grafana to "Last 7 days" or "All time"
- Verify data exists:
  ```bash
  docker exec -it postgres psql -U postgres -d rag_feedback -c "SELECT COUNT(*) FROM conversations;"
  ```

### Grafana can't connect to PostgreSQL
- Verify password matches in `docker-compose.yaml` and `grafana/provisioning/datasources/postgres.yml`
- Restart Grafana: `docker compose restart grafana`
- Manually configure datasource in Grafana UI (Configuration → Data Sources)

### Port conflicts
```bash
# If ports 8501, 3000, 9200, or 5432 are in use, edit docker-compose.yaml:
ports:
  - "8502:8501"  # Change first number to an available port
```

### Streamlit shows "Index not found" error
```bash
# Re-run ingestion
docker compose run --rm ingest

# Or rebuild everything
docker compose down -v
docker compose up --build -d
```

### Reset everything (fresh start)
```bash
docker compose down -v
docker compose up --build -d
```

### View logs for debugging
```bash
# All services
docker compose logs

# Specific service
docker compose logs streamlit
docker compose logs grafana
docker compose logs postgres
docker compose logs ingest
```

---

## 14. 🌟 Best Practices Followed

| Category | Technique | Status |
|-----------|------------|--------|
| **Hybrid Search** | Keyword (BM25) + KNN vector retrieval | ✅ Implemented |
| **Document Re-ranking** | Post-retrieval similarity reranking | ✅ Evaluated |
| **Query Enhancement** | LLM-based query understanding | ✅ Used GPT-4o |
| **Monitoring** | Real-time metrics and logging | ✅ Grafana + PostgreSQL |
| **Evaluation** | Hit Rate, MRR, Cosine Similarity | ✅ Comprehensive |
| **User Feedback** | Thumbs up/down collection | ✅ Streamlit UI |
| **Auto-Evaluation** | LLM-as-a-Judge relevance scoring | ✅ GPT-4o evaluation |
| **Cost Tracking** | OpenAI token and cost monitoring | ✅ Real-time calculation |
| **Containerization** | Full Docker Compose setup | ✅ Production-ready |
| **Reproducibility** | Pinned dependencies, .env config | ✅ Fully reproducible |

---

## 15. 🧩 Architecture Overview

```
                ┌──────────────────────────────┐
                │      Streamlit UI            │
                │  (User Query + Feedback)     │
                └──────────┬───────────────────┘
                           │
                           ▼
                ┌──────────────────────────────┐
                │   RAG Backend (Python)       │
                │ Retrieval + GPT-4o Response  │
                └────────┬──────────┬───────────┘
                         │          │
         ┌───────────────┘          └──────────────┐
         ▼                                         ▼
 ┌─────────────────┐                      ┌─────────────────┐
 │ Elasticsearch   │ ← BM25 + KNN Index   │ PostgreSQL DB   │
 │ (Hybrid Search) │                      │ (Logs + Metrics)│
 └─────────────────┘                      └────────┬────────┘
                                                   │
                                                   ▼
                                        ┌────────────────────┐
                                        │  Grafana Dashboard │
                                        │   (Monitoring)     │
                                        └────────────────────┘
```

---

## 16. 📸 Example Usage

### Ask a Question:
```
User: "How do I create a Kubernetes deployment?"
System: [Retrieves top 5 docs] → [GPT-4o generates answer]
Answer: "To create a Kubernetes deployment, use kubectl apply..."
Relevance: 🟢 RELEVANT
Response Time: 2.3s
Cost: $0.0023
```

### Provide Feedback:
Click 👍 if the answer was helpful, or 👎 if it wasn't.

### Monitor Performance:
Check Grafana dashboard to see:
- Average response time trends
- Percentage of relevant answers
- User satisfaction scores
- API costs over time

---

## 17. 🧑‍💻 Author

**Sindhura Uppu**  
💡 Built as a personal GenAI project to explore RAG systems, retrieval evaluation, and full-stack observability for AI applications.

📧 Contact: [GitHub Profile](https://github.com/sindhurauppu)

---

## 18. 🪄 License

MIT License © 2025 Sindhura Uppu

---

## 📝 Notes

- First-time setup takes 5-10 minutes (downloading images, indexing documents)
- Subsequent starts are much faster (~30 seconds)
- The system uses ~6GB RAM when fully running
- OpenAI costs are typically $0.001-0.005 per question
- All data is stored locally in Docker volumes
- Grafana dashboards persist across restarts

**Happy querying! 🚀**