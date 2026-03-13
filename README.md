---
title: Data Vacuum
emoji: 🌀
colorFrom: indigo
colorTo: cyan
sdk: docker
app_port: 7860
pinned: false
---

# 🌀 Data Vacuum
**Web Data Harvester → ML-Ready Dataset**

A pipeline that converts a plain-English prompt into a labelled training dataset by:
1. **Phase 1** — Generating targeted search queries via Groq LLM
2. **Phase 2** — Scraping matched web pages with headless Playwright
3. **Phase 3** — Cleaning, deduplicating and chunking the raw text
4. **Phase 4** — Zero-shot classifying each chunk with DeBERTa (ONNX Runtime)
5. **Phase 5** — Exporting a labelled Parquet/CSV dataset ready for fine-tuning

## Usage
1. Enter a research prompt (e.g. *"Find negative reviews of AI assistants"*)
2. Enter comma-separated labels (e.g. `Positive,Negative,Neutral`)
3. Click **Run Pipeline** and watch the live log stream
4. Download the labelled dataset when complete
