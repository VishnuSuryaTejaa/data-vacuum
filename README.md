# Data Vacuum

Data Vacuum is a highly optimized, high-performance web data harvesting pipeline that generates zero-shot ML datasets from raw web scraping. You provide a prompt and a set of sentiment labels, and the tool will automatically search the web, scrape results, strip out boilerplate, run a domain relevance filter, and evaluate sentiment via an ONNX-accelerated NLP model.

It's designed to be fast, resistant to common scraping blockers, and easy to run either via a CLI or a sleek FastAPI web dashboard.

## Features

- **Automated Web Searching:** Uses the Tavily API and Groq models to generate highly relevant search queries based on your prompt.
- **Stealth Scraping:** Built with Playwright and `playwright-stealth` to bypass basic bot mitigations and Cloudflare protection, executing 10 concurrent headless browsers at a time.
- **Smart Cleanup:** Employs hashing for exact-duplicate chunk removal and regex filtering to strip out common review-site boilerplate (e.g. Trustpilot verification chrome).
- **Domain Pre-filtering:** Before running rigorous zero-shot classification, the tool filters out off-topic text chunks to ensure the dataset is highly relevant.
- **High-Speed NLP:** Powered by the `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` model running on FP32 ONNX Runtime for 2-3x faster CPU execution than PyTorch. Low-confidence predictions are dropped automatically.
- **Live Web Dashboard:** A beautiful glassmorphic frontend built in Vanilla CSS/JS served by FastAPI that streams pipeline logs in real-time via Server-Sent Events (SSE).

## Tech Stack

- **Backend / Orchestration:** Python 3.11, `asyncio`
- **Scraping:** Playwright, `playwright-stealth`, Trafilatura, Selectolax
- **Search API:** Tavily, Groq API (Llama-3.1-8b)
- **Machine Learning:** HuggingFace `transformers`, `optimum[onnxruntime]`
- **Web Dashboard:** FastAPI, Uvicorn, Vanilla HTML/CSS/JS (SSE for live logs)
- **Export Frameworks:** Pandas, PyArrow (Parquet)

## Installation

1. Clone this repository and navigate to the directory:
   ```bash
   cd data-vacuum
   ```

2. Create a virtual environment and install the dependencies. The requirements explicitly cap `numpy<2.0.0` to maintain compatibility with PyTorch/ONNX on CPU:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Install the Playwright Chromium browser executables:
   ```bash
   playwright install chromium
   ```

4. Create a `.env` file in the root directory and add your API keys:
   ```text
   GROQ_API_KEY=your_groq_key_here
   TAVILY_API_KEY=your_tavily_key_here
   ```

## Usage

### Web Dashboard (Recommended)
You can run the web dashboard locally for a beautiful interface that streams the logs and provides immediate CSV/Parquet downloads:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```
Then visit `http://localhost:8000` in your browser.

### Command Line Interface
```bash
python main.py \
  --prompt "Find negative reviews of IoT hardware" \
  --labels "Positive,Negative,Neutral" \
  --max-queries 5 \
  --output "output/training_dataset.parquet"
```
You can pass the `--include-comments` flag if you want trailing noisy text to be chunked as well.

## Architecture

1. **Phase 1 (Search):** Triggers `llama-3.1-8b-instant` to unpack your prompt into multiple distinct search queries, which are then passed to the `Tavily` search API concurrently.
2. **Phase 2 (Scrape):** Leverages `Playwright` to launch headless Chrome browsers, rendering JS heavy pages and bypassing basic bot checks, extracting the HTML source.
3. **Phase 3 (Clean):** Trafilatura performs DOM layout extraction on the raw HTML to extract the core readable text. The script then chunks the text, strips out common boilerplate via regex, and drops exact duplicates via MD5 hashing.
4. **Phase 4 (Classify):** Evaluates every chunk through an FP32 ONNX-optimized DeBERTa pipeline. It runs a domain filter first, and if passed, generates confidence scores for your provided labels.
5. **Phase 5 (Export):** High-confidence chunks are batched into Pandas dataframes and written locally in CSV and Parquet formats.

## License
MIT License
