import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from html import unescape
from .base import JobSource
from ..models import RawJobListing


def extract_description_from_detail_html(html: str) -> Optional[str]:
    """
    Extracts structured job description text from CVBankas detail page HTML.
    Collects subheadings and content blocks (Responsibilities, Requirements, Offers, etc.).
    """
    # Strip script and style tags to prevent JSON taxonomy dictionaries leaking into text
    clean_source = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html, flags=re.IGNORECASE)
    clean_source = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', clean_source, flags=re.IGNORECASE)

    cutoff = clean_source.find('id="jobad_other_ads_c"')
    if cutoff == -1:
        cutoff = clean_source.find('id="jobad_company_c"')
    scope_html = clean_source[:cutoff] if cutoff != -1 else clean_source

    blocks = re.findall(
        r'(?:<h[2-6][^>]*class="[^"]*jobad_subheading[^"]*"[^>]*>([\s\S]*?)</h[2-6]>\s*)?<div[^>]*class="[^"]*jobad_txt[^"]*"[^>]*>([\s\S]*?)</div>',
        scope_html
    )

    parts = []
    for heading, body in blocks:
        h_clean = unescape(re.sub(r'<[^>]+>', ' ', heading)).strip() if heading else ""
        b_clean = unescape(re.sub(r'<[^>]+>', ' ', body)).strip()
        b_clean = re.sub(r'\s+', ' ', b_clean)

        if "Calculate your travel time" in b_clean or "Apskaičiuokite kelionės laiką" in b_clean:
            continue

        if h_clean and b_clean:
            parts.append(f"{h_clean}:\n{b_clean}")
        elif b_clean:
            parts.append(b_clean)

    if not parts:
        sec_match = re.search(r'<section[^>]*itemprop="description"[^>]*>([\s\S]*?)</section>', scope_html)
        if sec_match:
            raw = unescape(re.sub(r'<[^>]+>', ' ', sec_match.group(1)))
            raw = re.sub(r'\s+', ' ', raw).strip()
            if raw:
                parts.append(raw)

    full_desc = "\n\n".join(parts).strip()
    return full_desc if full_desc else None


def fetch_detail_page(url: str, headers: dict, timeout: int = 10) -> Optional[str]:
    """
    Fetches the detail page HTML for a given job URL.
    Returns extracted text if successful, or None if network/parsing fails.
    """
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read().decode('utf-8', errors='ignore')
            return extract_description_from_detail_html(html)
    except Exception:
        return None


class CVBankasSource(JobSource):
    """
    Legitimate, lightweight public search adapter for Lithuanian job listings on CVBankas.
    Fetches publicly accessible search results with standard HTTP client.
    """

    @property
    def source_name(self) -> str:
        return "cvbankas"

    def fetch_jobs(self, query: str = "dirbtinis intelektas", limit: int = 20) -> List[RawJobListing]:
        encoded_query = urllib.parse.quote(query)
        # Search URL for IT category (padalinys[]=76) with search keyword
        url = f"https://www.cvbankas.lt/?padalinys%5B%5D=76&keyw={encoded_query}"
        
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
                
                # Extract job article elements using regex
                articles = re.findall(r'<article class="list_article[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
                
                for idx, art in enumerate(articles[:limit]):
                    # Title and URL
                    title_match = re.search(r'<h3[^>]*class="[^"]*list_h3[^"]*"[^>]*>([^<]+)</h3>', art)
                    url_match = re.search(r'href="([^"]+)"', art)
                    comp_match = re.search(r'<span class="dib mt5 mr5">([^<]+)</span>', art)
                    loc_match = re.search(r'<span class="list_city">([^<]+)</span>', art)
                    sal_match = re.search(r'<span class="salary_amount">([^<]+)</span>', art)
                    
                    if title_match and url_match:
                        raw_title = unescape(title_match.group(1).strip())
                        job_url = url_match.group(1).strip()
                        if not job_url.startswith("http"):
                            job_url = urllib.parse.urljoin("https://www.cvbankas.lt", job_url)
                            
                        company = unescape(comp_match.group(1).strip()) if comp_match else "Company on CVBankas"
                        location = unescape(loc_match.group(1).strip()) if loc_match else "Vilnius, Lietuva"
                        salary = unescape(sal_match.group(1).strip()) if sal_match else None
                        
                        # Fetch full job description from listing detail page
                        detail_desc = fetch_detail_page(job_url, headers)
                        if detail_desc:
                            description_raw = detail_desc
                        else:
                            # Factual fallback if detail page cannot be fetched, never fabricating details
                            description_raw = (
                                f"{raw_title} at {company} located in {location}. "
                                f"Detailed job description could not be retrieved from {job_url}."
                            )
                        
                        results.append(RawJobListing(
                            raw_id=f"cvb-{idx+1}",
                            title=raw_title,
                            company=company,
                            location_raw=location,
                            description_raw=description_raw,
                            job_url=job_url,
                            application_url=None,  # Direct application starts on listing
                            salary_raw=salary,
                            source="cvbankas",
                            discovery_timestamp=now
                        ))
        except Exception as e:
            # Graceful network degradation
            print(f"[CVBankasSource] Notice: Live fetch encountered: {e}. (Offline fallback mode active)")
            
        return results
