"""
Phase 4 — Intelligent Labeler (The Classifier)

Runs HuggingFace zero-shot classification on text chunks using
DeBERTa-v3-base-mnli-fever-anli.

Engine priority:
  1. ONNX Runtime  — 3-4× faster on CPU, half the RAM (via optimum)
  2. PyTorch CPU    — fallback if optimum is not installed

MPS (Apple GPU) is intentionally skipped because DeBERTa's
disentangled attention exceeds Apple GPU memory limits.
"""

from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

import config

console = Console()

# ── ONNX availability probe ─────────────────────────────────────────────────
_USE_ONNX = False
try:
    from optimum.onnxruntime import ORTModelForSequenceClassification
    import onnxruntime as ort
    _USE_ONNX = True
except ImportError:
    pass

# PyTorch is always needed for the tokenizer & fallback
import torch
from transformers import pipeline, AutoTokenizer


# ── Cache dir for the exported ONNX model ────────────────────────────────────
_ONNX_CACHE_DIR = Path(config.DEFAULT_OUTPUT_DIR) / ".onnx_cache" / config.HF_MODEL.replace("/", "__")


class Classifier:
    """Lazy-initialized zero-shot classifier with ONNX acceleration."""

    def __init__(self):
        self._pipe = None

    # ── Model loading ────────────────────────────────────────────────────

    def _load_onnx(self):
        """Export (first run) or load (subsequent runs) the model with ONNX Runtime."""
        console.print("  [bright_cyan]⚡ ONNX Runtime[/] engine selected")

        tokenizer = AutoTokenizer.from_pretrained(config.HF_MODEL)
        tokenizer.model_max_length = 512

        # DeBERTa ONNX models often don't expect token_type_ids
        if "token_type_ids" in tokenizer.model_input_names:
            tokenizer.model_input_names.remove("token_type_ids")

        base_path = _ONNX_CACHE_DIR / "model.onnx"

        if base_path.exists():
            console.print("  [green]✓[/] Loading cached ONNX model")
            model = ORTModelForSequenceClassification.from_pretrained(
                _ONNX_CACHE_DIR,
                file_name="model.onnx",
            )
        else:
            console.print("  [yellow]⏳[/] First run: exporting PyTorch → ONNX "
                          "(takes ~1-2 min, cached permanently after)...")
            _ONNX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # Use optimum's built-in export which handles opset and file layout correctly.
            # With torch==2.1.2 this uses the legacy (non-dynamo) exporter at opset 12.
            model = ORTModelForSequenceClassification.from_pretrained(
                config.HF_MODEL,
                export=True,
                provider="CPUExecutionProvider",
            )
            model.save_pretrained(_ONNX_CACHE_DIR)
            tokenizer.save_pretrained(_ONNX_CACHE_DIR)
            console.print("  [green]✓[/] ONNX model exported and cached")

        self._pipe = pipeline(
            "zero-shot-classification",
            model=model,
            tokenizer=tokenizer,
        )
        console.print("  [green]✓[/] ONNX pipeline ready")



    def _load_pytorch(self):
        """Fallback: standard PyTorch CPU inference."""
        console.print("  [yellow]ℹ[/] ONNX not available — falling back to PyTorch CPU")

        device: int | str
        if torch.cuda.is_available():
            console.print("  [green]✓[/] Using NVIDIA GPU (CUDA)")
            device = 0
        else:
            console.print("  [yellow]ℹ[/] Using CPU (recommended for DeBERTa on Mac)")
            device = "cpu"

        tokenizer = AutoTokenizer.from_pretrained(config.HF_MODEL)
        # Explicitly cap to 512 tokens to suppress the truncation warning
        tokenizer.model_max_length = 512

        self._pipe = pipeline(
            "zero-shot-classification",
            model=config.HF_MODEL,
            tokenizer=tokenizer,
            device=device,
            torch_dtype=torch.float32,
        )

    def _load(self):
        """Load the model on first use (ONNX preferred, PyTorch fallback)."""
        if self._pipe is not None:
            return

        console.print(f"\n[bold cyan]Phase 4[/] → Loading classifier "
                      f"[yellow]{config.HF_MODEL}[/]…")

        if _USE_ONNX:
            try:
                self._load_onnx()
            except Exception as exc:
                console.print(f"  [red]⚠ ONNX load failed:[/] {exc}")
                console.print("  [yellow]↻ Falling back to PyTorch…[/]")
                self._pipe = None
                self._load_pytorch()
        else:
            self._load_pytorch()

    # ── Classification ───────────────────────────────────────────────────

    def classify_batch(
        self,
        chunks: list[dict],
        labels: list[str],
        batch_size: int = None,
    ) -> list[dict]:
        """
        Classify every chunk against the given candidate labels.
        Returns the input dicts enriched with 'label' and 'confidence_score'.
        """
        self._load()
        batch_size = batch_size or config.CLASSIFY_BATCH_SIZE
        texts = [c["chunk"] for c in chunks]
        results: list[dict] = []

        console.print(f"  Classifying [bold]{len(texts)}[/] chunks "
                      f"against labels {labels} "
                      f"(batch_size={batch_size})…")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("  Classifying…", total=len(texts))

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_meta = chunks[i:i + batch_size]

                # Pre-truncate texts explicitly to guarantee safe input
                tokenizer = self._pipe.tokenizer
                truncated_texts = []
                for t in batch_texts:
                    enc = tokenizer(
                        t, truncation=True, max_length=512,
                        return_tensors=None,
                    )
                    truncated_texts.append(
                        tokenizer.decode(enc["input_ids"], skip_special_tokens=True)
                    )

                outputs = self._pipe(
                    truncated_texts,
                    candidate_labels=labels,
                    batch_size=batch_size,
                    truncation=True,
                    max_length=512,
                )

                # pipeline returns a single dict if batch_size == 1
                if isinstance(outputs, dict):
                    outputs = [outputs]

                for meta, out in zip(batch_meta, outputs):
                    results.append({
                        "url": meta["url"],
                        "chunk": meta["chunk"],
                        "label": out["labels"][0],
                        "confidence_score": round(out["scores"][0], 4),
                    })

                progress.update(task, advance=len(batch_texts))

        console.print(f"  [green]✓[/] Classification complete.")
        return results

    # ── Confidence filtering ─────────────────────────────────────────────

    @staticmethod
    def filter_low_confidence(results: list[dict]) -> list[dict]:
        """Drop results below per-label confidence gates."""
        kept = []
        dropped_by_label: dict[str, int] = {}
        kept_by_label: dict[str, int] = {}

        for r in results:
            label = r["label"]
            gate = config.CONFIDENCE_GATES.get(
                label, config.CONFIDENCE_THRESHOLD_DEFAULT
            )
            if r["confidence_score"] >= gate:
                kept.append(r)
                kept_by_label[label] = kept_by_label.get(label, 0) + 1
            else:
                dropped_by_label[label] = dropped_by_label.get(label, 0) + 1

        total_dropped = len(results) - len(kept)
        console.print(f"  [green]✓[/] Dynamic confidence filter: "
                      f"[bold]{len(kept)}[/] kept, "
                      f"[red]{total_dropped}[/] dropped.")

        # Per-label breakdown
        all_labels = sorted(set(list(kept_by_label.keys()) + list(dropped_by_label.keys())))
        for label in all_labels:
            gate = config.CONFIDENCE_GATES.get(label, config.CONFIDENCE_THRESHOLD_DEFAULT)
            k = kept_by_label.get(label, 0)
            d = dropped_by_label.get(label, 0)
            console.print(f"    {label} (gate ≥{gate}): "
                          f"[green]{k}[/] kept, [red]{d}[/] dropped")

        return kept

    def filter_off_topic(
        self,
        chunks: list[dict],
        prompt: str,
    ) -> list[dict]:
        """Drop chunks that aren't relevant to the user's prompt.

        Uses a quick zero-shot check: 'Relevant to: {prompt}' vs 'Irrelevant'.
        Chunks where 'Irrelevant' wins are dropped.
        """
        self._load()
        kept = []
        dropped = 0
        texts = [c["chunk"][:300] for c in chunks]  # short prefix for speed
        relevant_label = f"Relevant to: {prompt}"
        candidate_labels = [relevant_label, "Irrelevant or off-topic"]

        console.print(f"  Filtering {len(texts)} chunks for topic relevance…")

        # Classify in large batches for speed
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_chunks = chunks[i:i + batch_size]

            outputs = self._pipe(
                batch_texts,
                candidate_labels=candidate_labels,
                batch_size=batch_size,
                truncation=True,
                max_length=512,
            )
            if isinstance(outputs, dict):
                outputs = [outputs]

            for chunk, out in zip(batch_chunks, outputs):
                top_label = out["labels"][0]
                if top_label == "Irrelevant or off-topic":
                    dropped += 1
                else:
                    kept.append(chunk)

        if dropped:
            console.print(f"  [green]✓[/] Domain filter: [bold]{len(kept)}[/] relevant, "
                          f"[red]{dropped}[/] off-topic dropped.")
        return kept


# Module-level singleton
_classifier = Classifier()


def run(chunks: list[dict], labels: list[str], prompt: str | None = None) -> list[dict]:
    """Phase 4 orchestrator: filter off-topic → classify → confidence filter."""
    if not chunks:
        console.print("[yellow]  ⚠ No chunks to classify.[/]")
        return []
    # Domain-relevance pre-filter
    if prompt:
        chunks = _classifier.filter_off_topic(chunks, prompt)
        if not chunks:
            console.print("[yellow]  ⚠ All chunks filtered as off-topic.[/]")
            return []
    results = _classifier.classify_batch(chunks, labels)
    results = _classifier.filter_low_confidence(results)
    return results
