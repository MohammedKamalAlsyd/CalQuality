from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores import FAISS
from src.config import embedder, FAISS_DIR

# Load the FAISS index globally so it's not reloaded on every query
vectorstore = FAISS.load_local(
    FAISS_DIR, 
    embedder, 
    allow_dangerous_deserialization=True # Required for local FAISS loading
)

@tool
def search_documents(query: str, config: RunnableConfig) -> str:
    """
    Search policies, agreements, product documentation, and SOPs.
    Always use this to check rules before answering.
    """
    account_id = config.get("configurable", {}).get("account_id", "GLOBAL")
    
    docs = vectorstore.similarity_search(query, k=5)
    
    # ENFORCE ACCESS CONTROL & SOURCE PRECEDENCE AT DATA LAYER
    filtered_docs = []
    for doc in docs:
        meta = doc.metadata
        doc_account = meta.get("account_id", "GLOBAL")
        status = meta.get("status", "current")
        
        # 1. Filter out deprecated documents
        if status == "deprecated":
            continue
            
        # 2. Filter out other customers' contracts
        if doc_account != "GLOBAL" and doc_account != account_id and account_id != "INTERNAL_OPS":
            continue
            
        filtered_docs.append(f"Source: {meta.get('source_file')} | Type: {meta.get('doc_type')}\nContent: {doc.page_content}")
    
    if not filtered_docs:
        return "No relevant authorized documents found."
        
    return "\n\n---\n\n".join(filtered_docs)