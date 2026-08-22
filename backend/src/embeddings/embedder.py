import os
import json
import torch
import faiss
import numpy as np
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings

# Mock import for your Bedrock client
try:
    from src.clients.bedrock import bedrock
except ImportError:
    bedrock = None
    print("Warning: bedrock client not found. Bedrock embeddings will fail.")

class UnifiedEmbedder(Embeddings):
    """
    A LangChain-compatible embedding class that handles Local HF, Voyage, and Bedrock.
    """
    
    # Class-level cache for local models to prevent reloading across instances
    _local_model_cache: Dict[tuple, SentenceTransformer] = {}

    def __init__(self, model_name: str, config: dict):
        self.model_name = model_name
        self.config = config

    def _get_local_model(self) -> SentenceTransformer:
        """Return a cached local model, loading if necessary."""
        cache_key = (self.model_name, self.config.get("type"))
        if cache_key not in self.__class__._local_model_cache:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
            
            print(f"Loading local HF model '{self.model_name}' to {device}...")
            self.__class__._local_model_cache[cache_key] = SentenceTransformer(
                self.model_name,
                model_kwargs={"torch_dtype": dtype},
                trust_remote_code=True,
            )
        return self.__class__._local_model_cache[cache_key]

    def _generate_embeddings(
        self,
        texts: list[str],
        is_query: bool = False,
        max_chars_per_text: int = -1,
        max_batch_texts: int = 2,
    ) -> np.ndarray:
        """Core unified embedding logic (adapted from user's provided snippet)."""
        embeddings = []
        config_type = self.config.get("type", "").lower()

        # --- HuggingFace Path ---
        if config_type == "hf":
            local_model = self._get_local_model()
            truncated_texts = [t[:max_chars_per_text] if max_chars_per_text > 0 else t for t in texts]
            
            # Formatting for specific models
            processed_texts = truncated_texts
            model_lower = self.model_name.lower()
            if is_query:
                if "nomic" in model_lower:
                    processed_texts = [f"search_query: {t}" for t in truncated_texts]
                elif "instruct" in model_lower:
                    processed_texts = [f"Instruct: Retrieve code definitions.\nQuery: {t}" for t in truncated_texts]
                elif "mxbai" in model_lower:
                    processed_texts = [f"Represent this query for retrieving relevant documents: {t}" for t in truncated_texts]
            else:
                if "nomic" in model_lower:
                    processed_texts = [f"search_document: {t}" for t in truncated_texts]

            all_embeddings = []
            for i in range(0, len(processed_texts), max_batch_texts):
                sub_batch = processed_texts[i : i + max_batch_texts]
                embs = local_model.encode(
                    sub_batch,
                    batch_size=4,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                all_embeddings.append(embs)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            return np.concatenate(all_embeddings, axis=0)

        # --- Voyage AI Path ---
        elif config_type == "voyage":
            import voyageai
            api_key = os.environ.get("VOYAGE_API_KEY")
            if not api_key:
                raise ValueError("VOYAGE_API_KEY is missing.")
            
            vo = voyageai.Client(api_key=api_key) # type: ignore
            input_type = "query" if is_query else "document"
            safe_texts = [t[:60000] for t in texts]
            dim = int(os.environ.get("VECTOR_DIMENSION", 2048))
            
            for i in range(0, len(safe_texts), 64):
                batch = safe_texts[i : i + 64]
                try:
                    result = vo.embed(texts=batch, model=self.model_name, input_type=input_type, output_dimension=dim, output_dtype="float")
                    embeddings.extend(result.embeddings)
                except Exception as e:
                    print(f"      ! Error embedding snippet with Voyage: {e}")
                    embeddings.extend([[0.0] * dim] * len(batch))

            emb_array = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(emb_array)
            return emb_array

        # --- Bedrock API Path ---
        elif config_type == "bedrock":
            if bedrock is None:
                raise RuntimeError("Bedrock client is not initialized.")
                
            model_lower = self.model_name.lower()
            if "titan" in model_lower:
                for text in texts:
                    safe_text = text[:16000]
                    body = json.dumps({"inputText": safe_text, "dimensions": 1024, "normalize": True})
                    try:
                        response = bedrock.invoke_model(body=body, modelId=self.model_name, accept="application/json", contentType="application/json")
                        res_body = json.loads(response.get("body").read())
                        embeddings.append(res_body.get("embedding"))
                    except Exception as e:
                        print(f"      ! Error embedding with Titan: {str(e)[:100]}")
                        embeddings.append([0.0] * 1024)

            elif "cohere" in model_lower:
                input_type = "search_query" if is_query else "search_document"
                safe_texts = [t[:2048] for t in texts]
                for i in range(0, len(safe_texts), 90):
                    batch = safe_texts[i : i + 90]
                    body = json.dumps({"texts": batch, "input_type": input_type, "truncate": "END"})
                    response = bedrock.invoke_model(body=body, modelId=self.model_name, accept="application/json", contentType="application/json")
                    res_body = json.loads(response.get("body").read())
                    embeddings.extend(res_body.get("embeddings"))

            emb_array = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(emb_array)
            return emb_array

        raise ValueError(f"Unsupported model type in config: {config_type}")

    # --- LangChain Interface Implementation ---
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents. Called by FAISS.from_documents()"""
        emb_array = self._generate_embeddings(texts, is_query=False)
        return emb_array.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query. Called during document retrieval."""
        emb_array = self._generate_embeddings([text], is_query=True)
        return emb_array[0].tolist()