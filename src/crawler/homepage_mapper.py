import os
import re
import time
import requests
from urllib.parse import urlparse, urlunparse, urljoin
from bs4 import BeautifulSoup
from src.crawler.url_crawler import URLCrawler
from src.crawler.sitemap_parser import SitemapParser
from src.fetch import FetchProvider, get_fetch_provider
from src.observability import get_event_logger, log_pipeline_event


def get_base_url(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"

def parse_robots_txt(content):
    sitemaps = []
    if not content:
        return sitemaps
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        # Check if line starts with 'sitemap:' (case-insensitive)
        if line.lower().startswith("sitemap:"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                sitemaps.append(parts[1].strip())
    return sitemaps

from src.crawler.url_classifier import classify_url

class HomepageMapper:
    def __init__(self, timeout=15, max_sitemaps=10, max_sitemap_urls=500, user_agent=None, fetch_provider=None, crawl_filters: dict | None = None):
        self.fetch_provider = self._resolve_fetch_provider(fetch_provider)
        self.crawler = URLCrawler(
            timeout=timeout,
            user_agent=user_agent,
            fetch_provider=self.fetch_provider,
            crawl_filters=crawl_filters,
        )
        self.max_sitemaps = max_sitemaps
        self.max_sitemap_urls = max_sitemap_urls
        self.sitemap_parser = SitemapParser(max_sitemaps=max_sitemaps, max_sitemap_urls=max_sitemap_urls)

    @staticmethod
    def _resolve_fetch_provider(fp):
        if fp is None:
            return None
        if isinstance(fp, FetchProvider):
            return fp
        if isinstance(fp, str):
            return get_fetch_provider(fp)
        return None

    def extract_menu_links(self, html_content, base_url):
        navigation_links = []
        attachment_links = []
        
        if not html_content:
            return navigation_links, attachment_links
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for nav, header, menu tags
        nav_elements = soup.find_all(['nav', 'header', 'menu'])
        
        pattern = re.compile(r'nav|header|menu', re.I)
        extra_elements = soup.find_all(id=pattern) + soup.find_all(class_=pattern)
        
        # Deduplicate elements by object id
        target_elements = list({id(elem): elem for elem in (nav_elements + extra_elements)}.values())
        
        seen_urls = set()
        
        for elem in target_elements:
            for a_tag in elem.find_all('a'):
                href = a_tag.get('href')
                if not href:
                    continue
                
                href_lower = href.lower().strip()
                if href_lower.startswith(('javascript:', 'mailto:', 'tel:', 'sms:')) or href_lower == '#':
                    continue

                # Convert to absolute URL
                absolute_url = urljoin(base_url, href)
                
                # Normalize URL (remove fragment)
                parsed_href = urlparse(absolute_url)
                normalized_url = urlunparse((
                    parsed_href.scheme,
                    parsed_href.netloc,
                    parsed_href.path,
                    parsed_href.params,
                    parsed_href.query,
                    ''
                ))
                
                if normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                
                link_text = a_tag.get_text().strip()
                
                category = classify_url(normalized_url, link_text, is_navigation=True)
                
                if category == "document":
                    _, ext = os.path.splitext(parsed_href.path)
                    ext = ext.lower().lstrip('.')
                    attachment_links.append({
                        "text": link_text or f"{ext.upper()} File",
                        "url": normalized_url,
                        "type": ext or "unknown"
                    })
                else:
                    navigation_links.append({
                        "text": link_text,
                        "url": normalized_url,
                        "category": category
                    })

        return navigation_links, attachment_links

    def fetch_content(self, url, retries=1):
        """Fetch URL content with optional retry on timeout.

        Stage 36: public-sector sites (e.g. gwangju.go.kr) have intermittent
        timeouts.  A single retry with the same timeout usually succeeds.
        """
        last_err = None
        for attempt in range(1 + retries):
            # === If fetch_provider is set, use it ===
            if self.fetch_provider is not None:
                try:
                    result = self.fetch_provider.fetch(url, timeout=self.crawler.timeout)
                    if result.ok:
                        content = result.html or result.markdown or result.text or ""
                        return content, None, result.status_code, result.url or url
                    else:
                        last_err = result.error
                except Exception as e:
                    last_err = str(e)
            else:
                # === Original code path ===
                try:
                    res = requests.get(url, headers=self.crawler.headers, timeout=self.crawler.timeout)
                    if res.status_code >= 400:
                        last_err = f"HTTP Error: {res.status_code}"
                    else:
                        if res.encoding == 'ISO-8859-1':
                            res.encoding = res.apparent_encoding
                        return res.text, None, res.status_code, res.url
                except requests.exceptions.Timeout:
                    last_err = f"Timeout after {self.crawler.timeout}s"
                except Exception as e:
                    last_err = str(e)

        # All attempts exhausted
        return None, last_err, None, url

    def build_map(self, start_url, correlation_id: str | None = None):
        event_logger = get_event_logger(__name__)
        started_at = time.perf_counter()

        def _duration_ms() -> int:
            return int((time.perf_counter() - started_at) * 1000)

        def _log_terminal_event(ok: bool, failure_code: str | None = None) -> None:
            if correlation_id is None:
                return
            kwargs = {}
            if failure_code is not None:
                kwargs["failure_code"] = failure_code
            log_pipeline_event(
                event_logger,
                event="pipeline_stage_end" if ok else "pipeline_stage_fail",
                correlation_id=correlation_id,
                stage="homepage_mapper",
                ok=ok,
                duration_ms=_duration_ms(),
                **kwargs,
            )

        result = {
            "start_url": start_url,
            "base_url": "",
            "sitemap": {
                "candidates": [],
                "found": [],
                "url_count": 0,
                "urls": [],
                "errors": []
            },
            "homepage": {
                "title": "",
                "description": "",
                "navigation_links": [],
                "attachment_links": [],
                "errors": []
            },
            "categories": {
                "menu": [],
                "notice": [],
                "board": [],
                "document": [],
                "apply": [],
                "contact": [],
                "unknown": []
            },
            "stats": {
                "sitemap_url_count": 0,
                "navigation_link_count": 0,
                "attachment_count": 0,
                "category_counts": {
                    "menu": 0,
                    "notice": 0,
                    "board": 0,
                    "document": 0,
                    "apply": 0,
                    "contact": 0,
                    "unknown": 0
                }
            },
            "errors": []
        }

        try:
            # 1. Base URL
            base_url = get_base_url(start_url)
            if not base_url:
                result["errors"].append("Invalid start URL")
                _log_terminal_event(ok=True)
                return result
            result["base_url"] = base_url

            # 2. Sitemap candidates
            candidates = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml"
            ]
        
            # Parse robots.txt for Sitemap directives
            robots_url = f"{base_url}/robots.txt"
            robots_txt, err, _, final_robots_url = self.fetch_content(robots_url)
            if err:
                result["sitemap"]["errors"].append(f"Failed to fetch robots.txt: {err}")
            else:
                robots_sitemaps = parse_robots_txt(robots_txt)
                for sm in robots_sitemaps:
                    if sm not in candidates:
                        candidates.append(sm)

            result["sitemap"]["candidates"] = candidates

            # 3. Retrieve and parse Sitemaps (recursively handling sitemap indexes)
            sitemap_urls_map = {}
            sitemap_queue = list(candidates)
            visited_sitemaps = set()
            sitemaps_processed = 0

            while sitemap_queue and sitemaps_processed < self.max_sitemaps:
                sm_url = sitemap_queue.pop(0)
                if sm_url in visited_sitemaps:
                    continue
                visited_sitemaps.add(sm_url)

                xml_data, err, status_code, final_sm_url = self.fetch_content(sm_url)
                if err:
                    continue

                result["sitemap"]["found"].append(sm_url)
                sitemaps_processed += 1

                parsed = self.sitemap_parser.parse(xml_data)
                if parsed["error"]:
                    result["sitemap"]["errors"].append(f"Error parsing sitemap {sm_url}: {parsed['error']}")
                    continue

                # Queue nested sitemaps
                for sub_sm in parsed["sitemaps"]:
                    sub_sm_abs = urljoin(final_sm_url, sub_sm)
                    if sub_sm_abs not in visited_sitemaps and sub_sm_abs not in sitemap_queue:
                        sitemap_queue.append(sub_sm_abs)

                # Store URLs and filter duplicates
                for url_info in parsed["urls"]:
                    loc_url = url_info["url"]
                    parsed_loc = urlparse(loc_url)
                    normalized_loc = urlunparse((
                        parsed_loc.scheme,
                        parsed_loc.netloc,
                        parsed_loc.path,
                        parsed_loc.params,
                        parsed_loc.query,
                        ''
                    ))

                    if normalized_loc not in sitemap_urls_map:
                        sitemap_urls_map[normalized_loc] = url_info
                    else:
                        existing = sitemap_urls_map[normalized_loc]
                        for key in ["lastmod", "changefreq", "priority"]:
                            if not existing.get(key) and url_info.get(key):
                                existing[key] = url_info[key]

            # Categorize and apply limit
            sitemap_urls_list = []
            for url_loc, info in sitemap_urls_map.items():
                category = classify_url(url_loc, is_navigation=False)
                sitemap_urls_list.append({
                    "url": url_loc,
                    "lastmod": info.get("lastmod", ""),
                    "changefreq": info.get("changefreq", ""),
                    "priority": info.get("priority", ""),
                    "category": category
                })

            sitemap_urls_list = sitemap_urls_list[:self.max_sitemap_urls]
            result["sitemap"]["urls"] = sitemap_urls_list
            result["sitemap"]["url_count"] = len(sitemap_urls_list)

            # 4. Fetch and parse homepage HTML for menu links
            homepage_html, err, _, final_homepage_url = self.fetch_content(start_url)
            if err:
                result["homepage"]["errors"].append(f"Failed to fetch homepage HTML: {err}")
                result["errors"].append(f"Homepage fetch error: {err}")
            else:
                soup = BeautifulSoup(homepage_html, 'html.parser')

                title_tag = soup.title
                if title_tag:
                    result["homepage"]["title"] = title_tag.get_text().strip()

                desc_tag = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
                if desc_tag and desc_tag.get('content'):
                    result["homepage"]["description"] = desc_tag.get('content').strip()
                else:
                    og_desc_tag = soup.find('meta', attrs={'property': 'og:description'})
                    if og_desc_tag and og_desc_tag.get('content'):
                        result["homepage"]["description"] = og_desc_tag.get('content').strip()

                # Extract nav/header/menu links using the actual final URL
                nav_links, att_links = self.extract_menu_links(homepage_html, final_homepage_url)
                result["homepage"]["navigation_links"] = nav_links
                result["homepage"]["attachment_links"] = att_links

            # 5. Build category maps
            unique_urls_categories = {}

            for item in result["sitemap"]["urls"]:
                unique_urls_categories[item["url"]] = item["category"]

            for item in result["homepage"]["navigation_links"]:
                # Navigation links have priority for "menu" categorizations
                unique_urls_categories[item["url"]] = item["category"]

            for item in result["homepage"]["attachment_links"]:
                unique_urls_categories[item["url"]] = "document"

            for url_val, cat_val in unique_urls_categories.items():
                if cat_val in result["categories"]:
                    result["categories"][cat_val].append(url_val)
                else:
                    result["categories"]["unknown"].append(url_val)

            # Sort the category lists for readability
            for cat_val in result["categories"]:
                result["categories"][cat_val].sort()

            # 6. Set stats
            result["stats"]["sitemap_url_count"] = result["sitemap"]["url_count"]
            result["stats"]["navigation_link_count"] = len(result["homepage"]["navigation_links"])
            result["stats"]["attachment_count"] = len(result["homepage"]["attachment_links"])

            for cat_val in result["stats"]["category_counts"]:
                result["stats"]["category_counts"][cat_val] = len(result["categories"][cat_val])

            _log_terminal_event(ok=True)
            return result
        except Exception:
            _log_terminal_event(ok=False, failure_code="homepage_mapper_exception")
            raise
