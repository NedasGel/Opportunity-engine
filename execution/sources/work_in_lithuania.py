import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List
from .base import JobSource
from ..models import RawJobListing


class WorkInLithuaniaSource(JobSource):
    """
    Adapter for Work in Lithuania (workinlithuania.com / jobs.workinlithuania.com).
    Note: jobs.workinlithuania.com utilizes a client-side JavaScript Single-Page Application (SPA)
    render layer for active job listings. Under standard HTTP requests without browser automation,
    the raw server response returns the JS container shell.
    This adapter safely attempts retrieval and falls back gracefully.
    """

    @property
    def source_name(self) -> str:
        return "work_in_lithuania"

    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        encoded_query = urllib.parse.quote(query) if query else ""
        url = f"https://jobs.workinlithuania.com/?search={encoded_query}"

        headers = {
            "User-Agent": "OpportunityDiscoveryEngine/1.0 (Student Research Bot; polite request; +http://localhost)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,lt;q=0.8"
        }

        req = urllib.request.Request(url, headers=headers)
        results: List[RawJobListing] = []

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                # Web response received; client-side JS hydration is required for live cards
                pass
        except Exception as e:
            print(f"[WorkInLithuaniaSource] Notice: Live fetch encountered: {e}. (SPA client-side rendering requires headless browser; skipped in lightweight HTTP mode)")

        return results
