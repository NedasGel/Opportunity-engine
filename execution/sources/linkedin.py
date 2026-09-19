import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from html import unescape
from .base import JobSource
from ..models import RawJobListing


def extract_linkedin_description_html(html: str) -> Optional[str]:
    """Extracts job description from LinkedIn guest jobPosting HTML."""
    desc_m = re.search(r'<div class="show-more-less-html__markup[^"]*">([\s\S]*?)</div>', html)
    if desc_m:
        raw_text = unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1))).strip()
        cleaned = re.sub(r'\s+', ' ', raw_text)
        return cleaned if cleaned else None
    return None


def fetch_linkedin_detail_description(job_url: str, headers: dict, timeout: int = 8) -> Optional[str]:
    """Fetches LinkedIn job details using the public guest API endpoint."""
    id_m = re.search(r'-(\d+)(?:\?|$)', job_url) or re.search(r'/view/(\d+)', job_url)
    if not id_m:
        return None
    
    job_id = id_m.group(1)
    detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        req = urllib.request.Request(detail_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            detail_html = resp.read().decode('utf-8', errors='ignore')
            return extract_linkedin_description_html(detail_html)
    except Exception:
        return None


class LinkedInSource(JobSource):
    """
    Public guest search adapter for LinkedIn job listings in Lithuania.
    Uses public guest seeMoreJobPostings search and guest jobPosting endpoints.
    """

    @property
    def source_name(self) -> str:
        return "linkedin"

    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        encoded_query = urllib.parse.quote(query) if query else "software"
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={encoded_query}&location=Lithuania&start=0"

        headers = {
            "User-Agent": "OpportunityDiscoveryEngine/1.0 (Student Research Bot; polite request; +http://localhost)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,lt;q=0.8"
        }

        req = urllib.request.Request(url, headers=headers)
        now = datetime.now(timezone.utc).isoformat()
        results: List[RawJobListing] = []

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                cards = re.findall(r'<li[^>]*>([\s\S]*?)</li>', html)

                for idx, card in enumerate(cards[:limit]):
                    title_m = re.search(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>([\s\S]*?)</h3>', card)
                    comp_m = re.search(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>([\s\S]*?)</h4>', card)
                    loc_m = re.search(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>([\s\S]*?)</span>', card)
                    url_m = re.search(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', card)

                    if title_m and url_m:
                        raw_title = unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).strip()
                        raw_comp = unescape(re.sub(r'<[^>]+>', '', comp_m.group(1))).strip() if comp_m else "Company on LinkedIn"
                        raw_loc = unescape(re.sub(r'<[^>]+>', '', loc_m.group(1))).strip() if loc_m else "Vilnius, Lithuania"
                        job_url = url_m.group(1).strip()
                        
                        # Clean tracking params from job_url
                        if "?" in job_url:
                            job_url = job_url.split("?")[0]

                        # Fetch detail page description
                        detail_desc = fetch_linkedin_detail_description(job_url, headers)
                        if detail_desc:
                            description_raw = detail_desc
                        else:
                            description_raw = (
                                f"{raw_title} at {raw_comp} located in {raw_loc}. "
                                f"Detailed job description could not be retrieved from {job_url}."
                            )

                        id_num = re.search(r'-(\d+)$', job_url)
                        raw_id = f"li-{id_num.group(1)}" if id_num else f"li-{idx+1}"

                        results.append(RawJobListing(
                            raw_id=raw_id,
                            title=raw_title,
                            company=raw_comp,
                            location_raw=raw_loc,
                            description_raw=description_raw,
                            job_url=job_url,
                            application_url=None,
                            salary_raw=None,
                            source="linkedin",
                            discovery_timestamp=now
                        ))
        except Exception as e:
            print(f"[LinkedInSource] Notice: Live fetch encountered: {e}. (Offline fallback active)")

        return results
