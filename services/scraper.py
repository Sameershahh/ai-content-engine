"""
services/scraper.py — Headless scraping of Reddit & Google Trends.
Uses Playwright in async mode; returns ranked TrendingTopic list.
"""
from __future__ import annotations
import asyncio
import re
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.models import TrendingTopic
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ScraperService:
    """Manages a single shared Playwright browser instance."""

    _playwright: Optional[asyncio.AbstractEventLoop] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None

    async def _get_context(self) -> BrowserContext:
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        if self._context is None:
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
        return self._context

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── Reddit ──────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def scrape_reddit(self, subreddits: list[str]) -> list[TrendingTopic]:
        topics: list[TrendingTopic] = []
        ctx = await self._get_context()

        for sub in subreddits:
            page = await ctx.new_page()
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                content = await page.content()

                # JSON is rendered as raw text in browser
                titles = re.findall(r'"title":\s*"([^"]{10,120})"', content)
                scores = re.findall(r'"score":\s*(\d+)', content)

                for i, title in enumerate(titles[:5]):
                    score = float(scores[i]) if i < len(scores) else 0.0
                    topics.append(
                        TrendingTopic(
                            title=title,
                            source=f"reddit/r/{sub}",
                            score=score,
                            url=f"https://www.reddit.com/r/{sub}/hot/",
                        )
                    )
                logger.info("reddit_scraped", subreddit=sub, posts=len(titles[:5]))
            except Exception as exc:
                logger.warning("reddit_scrape_failed", subreddit=sub, error=str(exc))
            finally:
                await page.close()

        return topics

    # ── Google Trends ────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def scrape_google_trends(self, geo: str = "US") -> list[TrendingTopic]:
        topics: list[TrendingTopic] = []
        ctx = await self._get_context()
        page = await ctx.new_page()

        try:
            url = f"https://trends.google.com/trending?geo={geo}&hl=en-US"
            await page.goto(url, wait_until="networkidle", timeout=45_000)
            await page.wait_for_timeout(3000)

            # Extract trending keywords from page text
            items = await page.query_selector_all("div[jsname] span, td span")
            seen: set[str] = set()
            for el in items[:60]:
                text = (await el.inner_text()).strip()
                if 5 < len(text) < 80 and text not in seen:
                    seen.add(text)
                    topics.append(
                        TrendingTopic(
                            title=text,
                            source="google_trends",
                            score=float(100 - len(topics)),
                            url=url,
                        )
                    )
                if len(topics) >= 10:
                    break

            logger.info("trends_scraped", geo=geo, count=len(topics))
        except Exception as exc:
            logger.warning("trends_scrape_failed", geo=geo, error=str(exc))
        finally:
            await page.close()

        return topics

    # ── Aggregated Discovery ─────────────────────────────────────────────────

    async def discover_topics(
        self,
        subreddits: Optional[list[str]] = None,
        geo: Optional[str] = None,
    ) -> list[TrendingTopic]:
        subs = subreddits or settings.subreddit_list
        location = geo or settings.trends_geo

        # Run scrapers with a global timeout to prevent pipeline hang
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self.scrape_reddit(subs),
                    self.scrape_google_trends(location),
                    return_exceptions=True
                ),
                timeout=90.0  # 1.5 min max for scraping
            )
            reddit_topics, trend_topics = results
        except asyncio.TimeoutError:
            logger.error("discovery_timeout", message="Scraping took too long, proceeding with empty topics")
            reddit_topics, trend_topics = [], []

        all_topics: list[TrendingTopic] = []
        
        if isinstance(reddit_topics, Exception):
            logger.error("reddit_scrape_exception", error=str(reddit_topics))
        elif isinstance(reddit_topics, list):
            all_topics.extend(reddit_topics)
            
        if isinstance(trend_topics, Exception):
            logger.error("trends_scrape_exception", error=str(trend_topics))
        elif isinstance(trend_topics, list):
            all_topics.extend(trend_topics)

        return sorted(all_topics, key=lambda t: t.score, reverse=True)
