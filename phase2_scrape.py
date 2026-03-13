"""
Phase 2 — Autonomous Web Scraper (The Gatherer)

Visits URLs using Playwright + stealth, extracts raw HTML.
Headless, fast, and resilient to timeouts.

Supports optional rotating residential proxies to avoid IP bans
when scraping at scale (1,000+ URLs).  Activate by setting
PROXY_SERVER / PROXY_USERNAME / PROXY_PASSWORD in .env.
"""

import asyncio
from playwright.async_api import async_playwright
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, module="playwright_stealth")
    from playwright_stealth import stealth_async
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

import config

console = Console()




async def _scrape_page(
    context, url: str, semaphore: asyncio.Semaphore, max_retries: int = 2,
) -> dict | None:
    """Scrape a single URL within a browser context, with retry logic."""
    async with semaphore:
        for attempt in range(1, max_retries + 2):
            page = await context.new_page()
            await stealth_async(page)
            try:
                await page.goto(
                    url,
                    timeout=config.PLAYWRIGHT_TIMEOUT,
                    wait_until=config.PLAYWRIGHT_WAIT_UNTIL,
                )
                html = await page.content()
                return {"url": url, "html": html}
            except Exception as exc:
                if attempt <= max_retries:
                    await asyncio.sleep(1)
                else:
                    console.print(
                        f"  [red]✗[/] [dim]{url[:80]}[/] — "
                        f"{type(exc).__name__}: {str(exc)[:120]}"
                    )
                    return None
            finally:
                await page.close()


async def _scrape_all(urls: list[str]) -> list[dict]:
    """Launch Playwright and scrape all URLs concurrently."""
    results: list[dict] = []

    # ── Proxy + concurrency setup ────────────────────────────────────────
    if config.PROXY_ENABLED:
        concurrency = config.SCRAPE_CONCURRENCY_PROXY
        proxy_cfg = {"server": config.PROXY_SERVER}
        if config.PROXY_USERNAME:
            proxy_cfg["username"] = config.PROXY_USERNAME
        if config.PROXY_PASSWORD:
            proxy_cfg["password"] = config.PROXY_PASSWORD
        console.print(f"  [bright_cyan]🛡 Proxy mode[/]: routing through "
                      f"[yellow]{config.PROXY_SERVER}[/]  "
                      f"(concurrency={concurrency})")
    else:
        concurrency = config.SCRAPE_CONCURRENCY
        proxy_cfg = None
        console.print(f"  [dim]Direct mode (no proxy)[/]  "
                      f"(concurrency={concurrency})")

    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as pw:
        # Inject proxy at browser launch level
        launch_kwargs = {"headless": config.PLAYWRIGHT_HEADLESS}
        if proxy_cfg:
            launch_kwargs["proxy"] = proxy_cfg

        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("  Scraping pages…", total=len(urls))
            successes = 0
            failures = 0

            # Process in batches to keep progress bar accurate
            tasks = []
            for url in urls:
                tasks.append(_scrape_page(context, url, semaphore))

            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    results.append(result)
                    successes += 1
                else:
                    failures += 1
                progress.update(task, advance=1)

        await browser.close()

    console.print(f"  [green]✓[/] Scraped [bold]{successes}[/] pages  "
                  f"| [red]{failures}[/] failed/timed-out.")
    return results


# ── Public API ───────────────────────────────────────────────────────────────

def scrape_urls(urls: list[str]) -> list[dict]:
    """
    Phase 2 orchestrator: takes a list of URLs, returns
    [{"url": ..., "html": ...}, ...] for every successfully scraped page.
    """
    if not urls:
        console.print("[yellow]  ⚠ No URLs to scrape.[/]")
        return []

    mode_label = "[bright_cyan]proxy[/]" if config.PROXY_ENABLED else "direct"
    console.print(f"\n[bold cyan]Phase 2[/] → Scraping [bold]{len(urls)}[/] URLs "
                  f"(mode={mode_label}, "
                  f"headless={config.PLAYWRIGHT_HEADLESS}, "
                  f"timeout={config.PLAYWRIGHT_TIMEOUT / 1000:.0f}s)…")

    return asyncio.run(_scrape_all(urls))


def run(urls: list[str]) -> list[dict]:
    """Alias for scrape_urls."""
    return scrape_urls(urls)
