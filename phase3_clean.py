"""
Phase 3 — Data Scrubbing Engine (The Cleaner)

Extracts main body text via Trafilatura, chunks it,
and sanitizes zero-width characters and whitespace noise.
"""

import hashlib
import re
import trafilatura
from rich.console import Console

import config

console = Console()


# ── Text Extraction ──────────────────────────────────────────────────────────

def extract_text(html: str, include_comments: bool = False) -> str | None:
    """
    Use Trafilatura to intelligently pull the main content
    from raw HTML, stripping nav bars, sidebars, ads, and footers.
    """
    return trafilatura.extract(
        html,
        include_comments=include_comments,
        include_tables=True,
        include_links=False,
        favor_recall=True,
    )


# ── Sanitization ─────────────────────────────────────────────────────────────

def sanitize(text: str) -> str:
    """Remove zero-width spaces and collapse excessive newlines."""
    text = text.replace("\u200b", "")           # zero-width space
    text = text.replace("\u200c", "")           # zero-width non-joiner
    text = text.replace("\u200d", "")           # zero-width joiner
    text = text.replace("\ufeff", "")           # BOM
    text = re.sub(r"\n{3,}", "\n\n", text)      # collapse 3+ newlines → 2
    text = re.sub(r"[ \t]{2,}", " ", text)      # collapse horizontal whitespace
    return text.strip()


# ── Boilerplate Removal ──────────────────────────────────────────────────────

_BOILERPLATE_PATTERNS = [
    r"While we don['’]t verify specific claims.*?Read more",
    r"To protect platform integrity.*?Read more",
    r"The Trustpilot Experience.*?goes against our guidelines\.",
    r"Anyone can write a Trustpilot review\..*?goes against our guidelines\.",
    r"Company details\s*Written by the company",
    r"How this company uses Trustpilot.*?See how their reviews",
    r"Review summary\s*Based on reviews, created with AI",
    r"What people talk about most\s*Based on these reviews",
    r"People also looked at",
    r"Replied to \d+% of negative reviews",
    r"Typically replies within \d+ \w+",
    r"See what reviewers are saying",
]

_BOILERPLATE_RE = re.compile(
    "|".join(_BOILERPLATE_PATTERNS),
    re.DOTALL | re.IGNORECASE,
)


def strip_boilerplate(text: str) -> str:
    """Remove known review-site boilerplate patterns."""
    text = _BOILERPLATE_RE.sub("", text)
    # Collapse resulting whitespace gaps
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, max_words: int = None) -> list[str]:
    """
    Split text into chunks of at most max_words words,
    breaking on sentence boundaries where possible.
    """
    max_words = max_words or config.CHUNK_MAX_WORDS

    # Split into sentences (crude but effective)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_word_count = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        word_count = len(sentence.split())

        # If a single sentence exceeds max_words, force-split by words
        if word_count > max_words:
            # Flush current chunk first
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_word_count = 0
            # Split the long sentence
            words = sentence.split()
            for i in range(0, len(words), max_words):
                chunks.append(" ".join(words[i:i + max_words]))
            continue

        if current_word_count + word_count > max_words:
            # Flush current chunk
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = word_count
        else:
            current_chunk.append(sentence)
            current_word_count += word_count

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c for c in chunks if c.strip()]


# ── Public API ───────────────────────────────────────────────────────────────

def run(scraped: list[dict], include_comments: bool = None) -> list[dict]:
    """
    Phase 3 orchestrator: takes scraped HTML dicts, returns
    [{"url": ..., "chunk": ...}, ...] for every valid chunk.
    """
    if include_comments is None:
        include_comments = config.INCLUDE_COMMENTS_DEFAULT

    console.print(f"\n[bold cyan]Phase 3[/] → Cleaning & chunking text "
                  f"(include_comments={include_comments}, "
                  f"max_chunk={config.CHUNK_MAX_WORDS} words)…")

    all_chunks: list[dict] = []
    seen_hashes: set[str] = set()
    pages_with_text = 0
    pages_empty = 0
    duplicates_dropped = 0

    for item in scraped:
        url = item["url"]
        html = item["html"]

        text = extract_text(html, include_comments=include_comments)
        if not text or len(text.strip()) < 200:  # skip trivially short pages
            pages_empty += 1
            continue

        text = sanitize(text)
        text = strip_boilerplate(text)

        # Skip if text became too short after boilerplate removal
        if len(text.strip()) < 200:
            pages_empty += 1
            continue

        chunks = chunk_text(text)
        pages_with_text += 1

        for chunk in chunks:
            # Hash-based deduplication
            chunk_hash = hashlib.md5(
                chunk.lower().split().__repr__().encode()
            ).hexdigest()
            if chunk_hash in seen_hashes:
                duplicates_dropped += 1
                continue
            seen_hashes.add(chunk_hash)
            all_chunks.append({"url": url, "chunk": chunk})

    console.print(f"  [green]✓[/] Extracted text from [bold]{pages_with_text}[/] pages  "
                  f"| [dim]{pages_empty} empty/too-short[/]")
    if duplicates_dropped:
        console.print(f"  [green]✓[/] Deduplicated: [red]{duplicates_dropped}[/] duplicate chunks removed.")
    console.print(f"  [green]✓[/] Produced [bold]{len(all_chunks)}[/] text chunks.")
    return all_chunks
