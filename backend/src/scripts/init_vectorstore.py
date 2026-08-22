# python -m src.scripts.init_vectorstore
import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from src.config import embedder, PDF_DIR, FAISS_DIR


# Metadata mapping for strict Access Control
METADATA_MAP = {
    "01_Support_Policy_v3_CURRENT.pdf": {"doc_type": "policy", "status": "current", "account_id": "GLOBAL"},
    "02_Support_Policy_v2_DEPRECATED.pdf": {"doc_type": "policy", "status": "deprecated", "account_id": "GLOBAL"},
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {"doc_type": "sop", "status": "current", "account_id": "GLOBAL"},
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {"doc_type": "ops_guide", "status": "current", "account_id": "GLOBAL"},
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {"doc_type": "contract", "status": "current", "account_id": "ACCT-001"},
    "06_LumenWorks_Service_Agreement.pdf": {"doc_type": "contract", "status": "current", "account_id": "ACCT-002"}
}

def init_vectorstore():    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_chunks = []

    for filename in os.listdir(PDF_DIR):
        if not filename.endswith(".pdf"):
            continue
            
        file_path = os.path.join(PDF_DIR, filename)
        print(f"Processing {filename}...")
        
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        chunks = text_splitter.split_documents(docs)
        
        # Inject custom metadata
        file_metadata = METADATA_MAP.get(filename, {"account_id": "GLOBAL"})
        for chunk in chunks:
            chunk.metadata.update(file_metadata)
            chunk.metadata["source_file"] = filename
            
        all_chunks.extend(chunks)

    print(f"Creating FAISS vector store with {len(all_chunks)} chunks...")
    vectorstore = FAISS.from_documents(documents=all_chunks, embedding=embedder)
    
    os.makedirs(FAISS_DIR, exist_ok=True)
    vectorstore.save_local(FAISS_DIR)
    print(f"✅ FAISS index saved successfully at {FAISS_DIR}")

if __name__ == "__main__":
    init_vectorstore()