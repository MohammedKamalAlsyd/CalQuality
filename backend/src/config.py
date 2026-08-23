import os
from src.embeddings.embedder import UnifiedEmbedder
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "data/parcelpilot.db"
MODEL_ID = os.getenv("GENERATION_MODEL_ID", "openai.gpt-oss-120b-1:0")
FAISS_DIR = "data/faiss_index/"
PDF_DIR = "data/pdf/"
EXCEL_PATH = "data/excel/ParcelPilot_Assessment_Data.xlsx"

# Strict snapshot timestamp specified in the dataset README
DATASET_SNAPSHOT_TIME = "2026-08-16 11:00 Asia/Kolkata"
CURRENCY = "INR"

embedder = UnifiedEmbedder(
    model_name="voyage-code-3", 
    config={"type": "voyage"}
)