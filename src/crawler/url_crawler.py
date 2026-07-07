import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse, urljoin

from src.fetch import FetchProvider, get_fetch_provider
from src.crawler.crawl_path_filter import should_crawl_url
from src.observability import get_event_logger, log_pipeline_event


class URLCrawler:
    def __init__(self, timeout=15, user_agent=None, fetch_provider=None, crawl_filters: dict | None = None):
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {"User-Agent": self.user_agent}
        self.attachment_extensions = {'pdf', 'hwp', 'hwpx', 'docx', 'xlsx'}
        self.fetch_provider = self._resolve_fetch_provider(fetch_provider)
        self.crawl_filters = crawl_filters

    @staticmethod
    def _resolve_fetch_provider(fp):
        """Resolve fetch_provider from a name, instance, or None."""
        if fp is None:
            return None  # keep original behavior
        if isinstance(fp, FetchProvider):
            return fp
        if isinstance(fp, str):
            return get_fetch_provider(fp)
        return None

    def is_internal(self, base_url, target_url):
        base_parsed = urlparse(base_url)
        target_parsed = urlparse(target_url)
        
        base_host = base_parsed.netloc.lower()
        target_host = target_parsed.netloc.lower()
        
        if not target_host:
            return True
            
        # www. 제거하고 호스트 비교
        base_domain = base_host.replace("www.", "")
        target_domain = target_host.replace("www.", "")
        
        if base_domain == target_domain:
            return True
        if target_domain.endswith("." + base_domain):
            return True
        return False

    def get_extension(self, url):
        parsed = urlparse(url)
        path = parsed.path
        _, ext = os.path.splitext(path)
        return ext.lower().lstrip('.')

    def clean_text(self, soup):
        # script, style, noscript 태그 제거
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
            
        raw_text = soup.get_text(separator='\n')
        lines = [line.strip() for line in raw_text.splitlines()]
        clean_lines = [line for line in lines if line]
        return '\n'.join(clean_lines)

    def extract_links(self, soup, base_url):
        internal_links = []
        external_links = []
        attachments = []

        for a_tag in soup.find_all('a'):
            href = a_tag.get('href')
            if not href:
                continue
            
            href_lower = href.lower().strip()
            # mailto:, javascript: 등 특수 프로토콜 제거
            if href_lower.startswith(('javascript:', 'mailto:', 'tel:', 'sms:')):
                continue

            if href_lower == '#':
                continue

            # 상대 경로를 절대 경로로 변환
            absolute_url = urljoin(base_url, href)
            
            # URL 정규화 (fragment 제거)
            parsed_href = urlparse(absolute_url)
            normalized_url = urlunparse((
                parsed_href.scheme,
                parsed_href.netloc,
                parsed_href.path,
                parsed_href.params,
                parsed_href.query,
                ''
            ))
            
            link_text = a_tag.get_text().strip()
            
            # 첨부파일 여부 확인
            ext = self.get_extension(normalized_url)
            if ext in self.attachment_extensions:
                attachments.append({
                    "text": link_text or f"{ext.upper()} File",
                    "url": normalized_url,
                    "type": ext
                })
            else:
                if self.is_internal(base_url, normalized_url):
                    if should_crawl_url(normalized_url, self.crawl_filters):
                        internal_links.append({
                            "text": link_text,
                            "url": normalized_url
                        })
                else:
                    external_links.append({
                        "text": link_text,
                        "url": normalized_url
                    })

        # 중복 제거 (URL 기준, 텍스트가 존재하는 쪽 선호)
        def deduplicate(links_list):
            seen = {}
            for item in links_list:
                url = item['url']
                text = item['text']
                if url not in seen:
                    seen[url] = text
                else:
                    if not seen[url] and text:
                        seen[url] = text
            return [{"text": text, "url": url} for url, text in seen.items()]

        def deduplicate_attachments(att_list):
            seen = {}
            for item in att_list:
                url = item['url']
                text = item['text']
                ext_type = item['type']
                if url not in seen:
                    seen[url] = (text, ext_type)
                else:
                    if not seen[url][0] and text:
                        seen[url] = (text, ext_type)
            return [{"text": text, "url": url, "type": ext_type} for url, (text, ext_type) in seen.items()]

        return {
            "internal": deduplicate(internal_links),
            "external": deduplicate(external_links),
            "attachments": deduplicate_attachments(attachments)
        }

    def analyze(self, url, max_chars=8000, correlation_id: str | None = None):
        started_at = time.perf_counter()

        # === If fetch_provider is set, use it ===
        if self.fetch_provider is not None:
            result = self._analyze_with_provider(url, max_chars)
        else:
            # === Original code path (no fetch_provider) ===
            result = self._analyze_original(url, max_chars)

        if correlation_id is not None:
            ok = not result["errors"]
            event_name = "pipeline_stage_end" if ok else "pipeline_stage_fail"
            kwargs = {}
            if not ok:
                kwargs["failure_code"] = "url_crawler_result_error"
            log_pipeline_event(
                get_event_logger(__name__),
                event=event_name,
                correlation_id=correlation_id,
                stage="url_crawler",
                ok=ok,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                **kwargs,
            )

        return result

    # ------------------------------------------------------------------
    # Original analyze path (unchanged)
    # ------------------------------------------------------------------

    def _analyze_original(self, url, max_chars):
        result = {
            "url": url,
            "status_code": None,
            "content_type": None,
            "title": "",
            "description": "",
            "text": "",
            "links": {
                "internal": [],
                "external": [],
                "attachments": []
            },
            "stats": {
                "text_length": 0,
                "internal_link_count": 0,
                "external_link_count": 0,
                "attachment_count": 0
            },
            "errors": []
        }

        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            result["errors"].append("Invalid URL: Scheme and domain are required.")
            return result

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            result["status_code"] = response.status_code
            result["url"] = response.url  # 리디렉션 반영 최종 URL
            
            content_type = response.headers.get('Content-Type', '')
            result["content_type"] = content_type
            
            if response.status_code >= 400:
                result["errors"].append(f"HTTP Error: Status code {response.status_code}")
            
            # HTML 여부 검사
            if 'text/html' not in content_type.lower():
                result["errors"].append(f"Response content type is not HTML: {content_type}")
                return result
                
            # 인코딩 문제 처리 (특히 한글)
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding
                
        except requests.exceptions.Timeout:
            result["errors"].append(f"Request timeout after {self.timeout} seconds.")
            return result
        except requests.exceptions.RequestException as e:
            result["errors"].append(f"Network error: {str(e)}")
            return result

        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # title 추출
            title_tag = soup.title
            if title_tag:
                result["title"] = title_tag.get_text().strip()
                
            # meta description 추출
            desc_tag = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
            if desc_tag and desc_tag.get('content'):
                result["description"] = desc_tag.get('content').strip()
            else:
                # og:description fallback
                og_desc_tag = soup.find('meta', attrs={'property': 'og:description'})
                if og_desc_tag and og_desc_tag.get('content'):
                    result["description"] = og_desc_tag.get('content').strip()

            # 본문 텍스트 정리
            clean_txt = self.clean_text(soup)
            result["text"] = clean_txt[:max_chars]
            
            # 링크 추출 및 분류
            links = self.extract_links(soup, result["url"])
            result["links"] = links
            
            # 통계 데이터
            result["stats"]["text_length"] = len(clean_txt)
            result["stats"]["internal_link_count"] = len(links["internal"])
            result["stats"]["external_link_count"] = len(links["external"])
            result["stats"]["attachment_count"] = len(links["attachments"])
            
        except Exception as e:
            result["errors"].append(f"HTML parsing error: {str(e)}")

        return result

    # ------------------------------------------------------------------
    # FetchProvider analyze path (opt-in)
    # ------------------------------------------------------------------

    def _analyze_with_provider(self, url, max_chars):
        result = {
            "url": url,
            "status_code": None,
            "content_type": None,
            "title": "",
            "description": "",
            "text": "",
            "links": {
                "internal": [],
                "external": [],
                "attachments": []
            },
            "stats": {
                "text_length": 0,
                "internal_link_count": 0,
                "external_link_count": 0,
                "attachment_count": 0
            },
            "errors": []
        }

        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            result["errors"].append("Invalid URL: Scheme and domain are required.")
            return result

        # Use fetch_provider
        try:
            fetch_result = self.fetch_provider.fetch(url, timeout=self.timeout)
        except Exception as e:
            result["errors"].append(f"Fetch provider error: {str(e)}")
            return result

        # Populate basic fields
        result["url"] = fetch_result.url or url
        result["status_code"] = fetch_result.status_code
        result["content_type"] = fetch_result.content_type
        result["title"] = fetch_result.title
        result["description"] = fetch_result.description

        if not fetch_result.ok:
            result["errors"].append(fetch_result.error or "Fetch provider returned error")
            return result

        # --- Parse HTML with BeautifulSoup if available ---
        html_source = fetch_result.html or ""
        if html_source:
            try:
                soup = BeautifulSoup(html_source, 'html.parser')

                # Title from HTML if we didn't get it from the provider
                if not result["title"]:
                    title_tag = soup.title
                    if title_tag:
                        result["title"] = title_tag.get_text().strip()

                # Description from HTML if we didn't get it
                if not result["description"]:
                    desc_tag = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
                    if desc_tag and desc_tag.get('content'):
                        result["description"] = desc_tag.get('content').strip()
                    else:
                        og_desc_tag = soup.find('meta', attrs={'property': 'og:description'})
                        if og_desc_tag and og_desc_tag.get('content'):
                            result["description"] = og_desc_tag.get('content').strip()

                # Clean text from HTML
                clean_txt = self.clean_text(soup)
                result["text"] = clean_txt[:max_chars]

                # Links from BeautifulSoup
                links = self.extract_links(soup, result["url"])
                result["links"] = links

                # Stats
                result["stats"]["text_length"] = len(clean_txt)
                result["stats"]["internal_link_count"] = len(links["internal"])
                result["stats"]["external_link_count"] = len(links["external"])
                result["stats"]["attachment_count"] = len(links["attachments"])

            except Exception as e:
                result["errors"].append(f"HTML parsing error: {str(e)}")

        else:
            # No HTML available — use text/markdown and links from FetchResult
            text_content = fetch_result.markdown or fetch_result.text or ""
            result["text"] = text_content[:max_chars]
            result["stats"]["text_length"] = len(text_content)

            # Convert flat links from FetchResult to classified links
            internal_links = []
            external_links = []
            attachments = []
            for link in fetch_result.links:
                link_url = link.get("url", "")
                text = link.get("text", "")
                if not link_url:
                    continue
                ext = self.get_extension(link_url)
                if ext in self.attachment_extensions:
                    attachments.append({"text": text or f"{ext.upper()} File", "url": link_url, "type": ext})
                elif self.is_internal(result["url"], link_url):
                    if should_crawl_url(link_url, self.crawl_filters):
                        internal_links.append({"text": text, "url": link_url})
                else:
                    external_links.append({"text": text, "url": link_url})

            result["links"] = {
                "internal": internal_links,
                "external": external_links,
                "attachments": attachments,
            }
            result["stats"]["internal_link_count"] = len(internal_links)
            result["stats"]["external_link_count"] = len(external_links)
            result["stats"]["attachment_count"] = len(attachments)

        return result
