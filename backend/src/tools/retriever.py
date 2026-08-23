from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores import FAISS
from src.config import embedder, FAISS_DIR

vectorstore = FAISS.load_local(
    FAISS_DIR, 
    embedder, 
    allow_dangerous_deserialization=True
)

@tool
def search_documents(query: str, config: RunnableConfig) -> str:
    """
    Search policies, customer agreements, SOPs, and product operations guides.
    Retrieves up to 15 candidates and applies strict access control and deprecation filtering.
    """
    account_id = config.get("configurable", {}).get("account_id", "GLOBAL")
    
    # Retrieve more candidates (k=15) so post-filtering doesn't starve the prompt
    docs = vectorstore.similarity_search(query, k=15)
    
    filtered_docs = []
    for doc in docs:
        meta = doc.metadata
        doc_account = meta.get("account_id", "GLOBAL")
        status = meta.get("status", "current")
        
        # 1. Ignore deprecated files completely
        if status == "deprecated":
            continue
            
        # 2. Filter other accounts' private service agreements
        if doc_account != "GLOBAL" and doc_account != account_id and account_id != "INTERNAL_OPS":
            continue
            
        filtered_docs.append(
            f"📄 [SOURCE: {meta.get('source_file')} | TYPE: {meta.get('doc_type', 'unknown').upper()}]\n{doc.page_content}"
        )
    
    if not filtered_docs:
        return "No relevant authorized current documents found for your query."
        
    return "\n\n---\n\n".join(filtered_docs[:5])