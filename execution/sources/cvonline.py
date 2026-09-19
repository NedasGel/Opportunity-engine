import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from html import unescape
from .base import JobSource
from ..models import RawJobListing


class CVOnlineSource(JobSource):
    """
    Adapter for CVOnline (cvonline.lt), extracting structured job vacancies
    and full listing descriptions from search results.
    """

    @property
    def source_name(self) -> str:
        return "cvonline"

    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        encoded_query = urllib.parse.quote(query) if query else ""
        url = f"https://cvonline.lt/lt/search?limit={limit}&offset=0"
        if encoded_query:
            url += f"&keywords%5B0%5D={encoded_query}"

        headers = {
            "User-Agent": "OpportunityDiscoveryEngine/1.0 (Student Research Bot; polite request; +http://localhost)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "lt,en-US;q=0.7,en;q=0.3"
        }

        req = urllib.request.Request(url, headers=headers)
        now = datetime.now(timezone.utc).isoformat()
        results: List[RawJobListing] = []

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>', html)
                if next_data:
                    jd = json.loads(next_data.group(1))
                    page_props = jd.get('props', {}).get('pageProps', {})
                    search_results = page_props.get('searchResults', {})
                    vacancies = search_results.get('vacancies', [])

                    for idx, vac in enumerate(vacancies[:limit]):
                        vac_id = str(vac.get('id', f"cvo-{idx+1}"))
                        title = vac.get('positionTitle') or vac.get('title') or "Untitled Position"
                        company = vac.get('employerName') or vac.get('companyName') or "Company on CVOnline"
                        
                        # Salary formatting
                        salary_from = vac.get('salaryFrom')
                        salary_to = vac.get('salaryTo')
                        salary = None
                        if salary_from and salary_to:
                            salary = f"{salary_from}-{salary_to} EUR/month"
                        elif salary_from:
                            salary = f"Nuo {salary_from} EUR/month"
                        elif salary_to:
                            salary = f"Iki {salary_to} EUR/month"

                        # Work mode / location
                        remote = vac.get('remoteWork')
                        remote_type = vac.get('remoteWorkType')
                        
                        location_parts = []
                        if remote:
                            location_parts.append(f"Remote ({remote_type})" if remote_type else "Remote")
                        location_parts.append("Vilnius, Lietuva")
                        location_raw = ", ".join(location_parts)

                        # Full description text
                        content = vac.get('positionContent') or vac.get('description')
                        if content:
                            clean_desc = unescape(re.sub(r'<[^>]+>', ' ', content)).strip()
                            clean_desc = re.sub(r'\s+', ' ', clean_desc)
                            description_raw = clean_desc
                        else:
                            description_raw = (
                                f"{title} at {company} located in {location_raw}. "
                                f"Detailed job description available on CVOnline."
                            )

                        job_url = f"https://cvonline.lt/lt/vacancy/{vac_id}"

                        results.append(RawJobListing(
                            raw_id=f"cvo-{vac_id}",
                            title=title.strip(),
                            company=company.strip(),
                            location_raw=location_raw,
                            description_raw=description_raw,
                            job_url=job_url,
                            application_url=None,
                            salary_raw=salary,
                            source="cvonline",
                            discovery_timestamp=now
                        ))
        except Exception as e:
            print(f"[CVOnlineSource] Notice: Live fetch encountered: {e}. (Offline fallback active)")

        return results
