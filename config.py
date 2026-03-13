"""
Central configuration for the Data Vacuum Pipeline.
Every engineering parameter is defined here for easy tuning.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ── Phase 1: Search Orchestration ────────────────────────────────────────────
LLM_MODEL = "llama-3.1-8b-instant"          # Groq-hosted model
LLM_TEMPERATURE = 0.1                        # Low creativity, high precision
MAX_QUERIES = 50                             # Upper bound on generated queries

TAVILY_SEARCH_DEPTH = "advanced"             # Deep search
TAVILY_MAX_RESULTS = 20                      # Results per query
TAVILY_RAW_CONTENT = False                   # URLs only; scraping in Phase 2

# ── Phase 2: Web Scraping ────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True                   # Invisible browser
PLAYWRIGHT_TIMEOUT = 15_000                  # 15 s per page (fail fast)
PLAYWRIGHT_WAIT_UNTIL = "domcontentloaded"   # Skip images/ads
SCRAPE_CONCURRENCY = 5                       # Parallel page limit (no proxy)

# ── Phase 2: Proxy Settings (optional — activate via .env) ───────────────────
PROXY_SERVER   = os.getenv("PROXY_SERVER", "")       # e.g. http://proxy.provider.com:8000
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "")
PROXY_ENABLED  = bool(PROXY_SERVER)
SCRAPE_CONCURRENCY_PROXY = 3                         # Lower concurrency for residential proxies

# ── Phase 3: Data Cleaning ───────────────────────────────────────────────────
CHUNK_MAX_WORDS = 400                        # Fits transformer context
INCLUDE_COMMENTS_DEFAULT = False             # True for forums/reviews

# ── Phase 4: Classification ──────────────────────────────────────────────────
HF_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
CLASSIFY_BATCH_SIZE = 8                      # Sentences per GPU batch
CONFIDENCE_GATES = {
    "Negative": 0.85,                            # Strict — anger is easy to detect
    "Positive": 0.85,                            # Strict — spam often masquerades as positive
    "Neutral":  0.70,                            # Forgiving — neutral text lacks strong signal
}
CONFIDENCE_THRESHOLD_DEFAULT = 0.85              # Fallback for unlisted labels

# ── Phase 5: Export ──────────────────────────────────────────────────────────
PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "snappy"
DEFAULT_OUTPUT_DIR = "/tmp/output"
DEFAULT_OUTPUT_FILE = "training_dataset.parquet"
