"""Mock fetch provider for testing without real HTTP calls."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .base import FetchProvider, FetchResult


class MockFetchProvider(FetchProvider):
    """Mock provider that returns a fixed response without network calls.

    Responses can be customized via environment variables:
        AI_FINDER_FETCH_MOCK_MARKDOWN
        AI_FINDER_FETCH_MOCK_HTML
        AI_FINDER_FETCH_MOCK_TITLE
    """

    def __init__(
        self,
        markdown: str | None = None,
        html: str | None = None,
        title: str | None = None,
    ):
        self._markdown = markdown or os.environ.get(
            "AI_FINDER_FETCH_MOCK_MARKDOWN",
            "# Mock Page\n\nThis is a mock fetch response for testing.",
        )
        self._html = html or os.environ.get(
            "AI_FINDER_FETCH_MOCK_HTML",
            "<html><head><title>Mock Page</title></head><body>Mock body</body></html>",
        )
        self._title = title or os.environ.get(
            "AI_FINDER_FETCH_MOCK_TITLE",
            "Mock Page",
        )

    def fetch(self, url: str, **kwargs: object) -> FetchResult:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return FetchResult(
            url=url,
            ok=True,
            provider=self.name,
            fetched_at=now,
            status_code=200,
            content_type="text/html",
            markdown=self._markdown,
            html=self._html,
            text=self._markdown,
            title=self._title,
            description="Mock description for testing.",
            links=[
                {"text": "Mock Link 1", "url": "https://example.com/mock1"},
                {"text": "Mock Link 2", "url": "https://example.com/mock2"},
            ],
        )

    @property
    def name(self) -> str:
        return "mock"
