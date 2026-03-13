"""
Phase 1 — Search Orchestration (The Master Controller)

Converts a plain-English prompt into targeted search queries via Groq LLM,
then collects URLs via the Tavily AI Search API.
"""

import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
from tavily import TavilyClient
from rich.console import Console

import config

console = Console()


# ── Query Generation ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a search-query engineer. Given a research topic, 
generate a JSON array of highly specific Google search queries that would 
surface the most relevant and diverse web pages on this topic.

Rules:
- Return ONLY a valid JSON array of strings, nothing else.
- Each query should be unique and target a different angle, source type, 
  or sub-topic.
- Include queries targeting forums, reviews, news articles, blog posts, 
  and official documentation where applicable.
- Do NOT include generic or overly broad queries.
- Generate up to {max_queries} queries."""


def generate_queries(prompt: str, max_queries: int = None) -> list[str]:
    """Use Groq LLM to generate diverse search queries from a prompt."""
    max_queries = max_queries or config.MAX_QUERIES

    client = Groq(api_key=config.GROQ_API_KEY)

    console.print(f"\n[bold cyan]Phase 1[/] → Generating search queries with "
                  f"[yellow]{config.LLM_MODEL}[/] (temp={config.LLM_TEMPERATURE})…")

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(max_queries=max_queries),
            },
            {
                "role": "user",
                "content": f"Research topic: {prompt}",
            },
        ],
        max_tokens=4096,
        timeout=30,
    )

    raw = response.choices[0].message.content.strip()

    # Robustly extract JSON array from the response
    try:
        queries = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find a JSON array inside markdown code fences
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            queries = json.loads(match.group())
        else:
            console.print("[red]  ✗ Failed to parse LLM output as JSON.[/]")
            console.print(f"  Raw output:\n{raw[:500]}")
            return []

    queries = [q for q in queries if isinstance(q, str) and q.strip()]
    queries = queries[:max_queries]

    console.print(f"  [green]✓[/] Generated [bold]{len(queries)}[/] search queries.")
    return queries


# ── Web Search ───────────────────────────────────────────────────────────────

def _search_single_query(
    client: TavilyClient,
    query: str,
    index: int,
    total: int,
    seen_urls: set,
    url_lock: threading.Lock,
    all_urls: list,
    max_retries: int = 2,
) -> int:
    """Search a single query with retry logic. Returns count of new URLs."""
    for attempt in range(1, max_retries + 2):
        try:
            results = client.search(
                query=query,
                search_depth=config.TAVILY_SEARCH_DEPTH,
                max_results=config.TAVILY_MAX_RESULTS,
                include_raw_content=config.TAVILY_RAW_CONTENT,
            )
            new = 0
            with url_lock:
                for r in results.get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_urls.append(url)
                        new += 1
            console.print(f"  [{index}/{total}] [dim]{query[:60]}…[/]  "
                          f"→ +{new} new URLs")
            return new
        except Exception as e:
            if attempt <= max_retries:
                wait = 2 ** (attempt - 1)
                console.print(f"  [{index}/{total}] [yellow]⟳ Retry {attempt}/{max_retries}[/] "
                              f"after {wait}s: {e}")
                time.sleep(wait)
            else:
                console.print(f"  [{index}/{total}] [red]✗ Failed after {max_retries} retries:[/] {e}")
    return 0


def search_web(queries: list[str]) -> list[str]:
    """Run queries through Tavily concurrently and collect unique URLs."""
    client = TavilyClient(api_key=config.TAVILY_API_KEY)

    console.print(f"\n[bold cyan]Phase 1[/] → Searching the web via Tavily "
                  f"(depth={config.TAVILY_SEARCH_DEPTH}, "
                  f"max_results={config.TAVILY_MAX_RESULTS}, "
                  f"workers=5)…")

    seen_urls: set[str] = set()
    all_urls: list[str] = []
    url_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                _search_single_query,
                client, query, i, len(queries),
                seen_urls, url_lock, all_urls,
            ): query
            for i, query in enumerate(queries, 1)
        }
        for future in as_completed(futures):
            future.result()  # Propagate any unhandled exceptions

    console.print(f"  [green]✓[/] Collected [bold]{len(all_urls)}[/] unique URLs total.")
    return all_urls


# ── Public API ───────────────────────────────────────────────────────────────

def run(prompt: str, max_queries: int = None) -> list[str]:
    """Phase 1 orchestrator: prompt → queries → URLs."""
    queries = generate_queries(prompt, max_queries)
    if not queries:
        return []
    urls = search_web(queries)
    return urls
