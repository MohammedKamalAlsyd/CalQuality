# ParcelPilot AI Support Agent

An AI-powered support and operations chatbot built for the CalQuity/ParcelPilot assessment.
Features multi-tenant data isolation, strict temporal grounding, and proactive anomaly detection.

## Architecture

- **Frontend:** Next.js (React), Ant Design X, TailwindCSS.
- **Backend:** FastAPI (Python), LangGraph, LangChain.
- **Data Layer:** SQLite (in-memory isolated pools for structured data), FAISS (vector store).
- **LLM:** AWS Bedrock (Llama 3 / Claude) / Voyage AI (Embeddings).

## Local Setup Instructions

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
```

**Set your `.env` variables in `backend/.env`:**
```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
GENERATION_MODEL_ID=meta.llama3-70b-instruct-v1:0
VOYAGE_API_KEY=your_voyage_key
```

**Initialize Data & Run Server:**
```bash

# 1. Initialize SQLite Database from Excel

python -m src.scripts.init_sqlite

# 2. Initialize FAISS Vector Store from PDFs

python -m src.scripts.init_vectorstore

# 3. Start the FastAPI server

python -m src.main
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:3000` in your browser.
