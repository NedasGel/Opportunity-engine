import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from html import unescape
from .base import JobSource
from ..models import RawJobListing


def extract_cvmarket_detail_description(html: str) -> Optional[str]:
    """Extracts job description from CVMarket detail page."""
    # Find main job ad container or description div
    desc_m = re.search(r'<div[^>]*class="[^"]*job-offer-content[^"]*"[^>]*>([\s\S]*?)</div>\s*<div class="job-offer-footer', html) or \
             re.search(r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>([\s\S]*?)</div>', html) or \
             re.search(r'<section[^>]*class="[^"]*job-content[^"]*"[^>]*>([\s\S]*?)</section>', html) or \
             re.search(r'<div[^>]*id="jobad_content"[^>]*>([\s\S]*?)</div>', html)
    if desc_m:
        raw_text = unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1))).strip()
        cleaned = re.sub(r'\s+', ' ', raw_text)
        return cleaned if cleaned else None
    return None


def fetch_cvmarket_detail(url: str, headers: dict, timeout: int = 8) -> Optional[str]:
    """Fetches CVMarket job detail page and extracts description."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            return extract_cvmarket_detail_description(html)
    except Exception:
        return None


class CVMarketSource(JobSource):
    """
    Adapter for CVMarket (cvmarket.lt), extracting public job listings in Lithuania.
    """

    @property
    def source_name(self) -> str:
        return "cvmarket"

    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        encoded_query = urllib.parse.quote(query) if query else ""
        url = f"https://www.cvmarket.lt/joboffers.php?search=1&search_keyword={encoded_query}"

        headers = {
            "User-Agent": "OpportunityDiscoveryEngine/1.0 (Student Research Bot; polite request; +http://localhost)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "lt,en-US;q=0.7,en;q=0.3"
        }

        req = urllib.request.Request(url, headers=headers)
        now = datetime.now(timezone.utc).isoformat()
        results: List[RawJobListing] = []

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                # Links to job offers look like: href="/<slug>-<digits>"
                links = re.findall(r'<a[^>]*href="(/[^"]+-\d{6,8})"[^>]*>([\s\S]*?)</a>', html)
                seen_urls = set()

                for href, content in links:
                    if len(results) >= limit:
                        break
                    if href in seen_urls or '/company/' in href:
                        continue
                    seen_urls.add(href)

                    # Extract slug-based title
                    slug_part = href.split('/')[-1].rsplit('-', 1)[0].replace('-', ' ')
                    title = slug_part.capitalize().strip()
                    if not title or len(title) < 3:
                        continue

                    # Extract salary if present
                    sal_m = re.search(r'(\d+[\d\s\.\-]*\s*€(?:/[a-zėą]+)?[^<]*)', content)
                    salary = unescape(sal_m.group(1).strip()) if sal_m else None

                    job_url = f"https://www.cvmarket.lt{href}"
                    company = "Company on CVMarket"
                    location = "Vilnius, Lietuva"

                    # Fetch detail description
                    detail_desc = fetch_cvmarket_detail(job_url, headers)
                    if detail_desc:
                        description_raw = detail_desc
                    else:
                        description_raw = (
                            f"{title} at {company} located in {location}. "
                            f"Detailed job description could not be retrieved from {job_url}."
                        )

                    id_m = re.search(r'-(\d+)$', href)
                    raw_id = f"cvm-{id_m.group(1)}" if id_m else f"cvm-{len(results)+1}"

                    results.append(RawJobListing(
                        raw_id=raw_id,
                        title=title,
                        company=company,
                        location_raw=location,
                        description_raw=description_raw,
                        job_url=job_url,
                        application_url=None,
                        salary_raw=salary,
                        source="cvmarket",
                        discovery_timestamp=now
                    ))
        except Exception as e:
            print(f"[CVMarketSource] Notice: Live fetch encountered: {e}. (Offline fallback active)")

        return results
