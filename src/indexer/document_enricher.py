import datetime
from src.crawler.url_crawler import URLCrawler


class DocumentEnricher:
    def __init__(self, timeout=15, user_agent=None, acquisition_policy=None):
        # #1294: when set, the frozen acquisition policy is propagated to the
        # URLCrawler (which forwards it to the fetch provider for redirect
        # host containment) and used to reject out-of-scope record URLs before
        # any crawler/network dispatch. None preserves the historical
        # unrestricted behavior for non-acquisition callers.
        self.acquisition_policy = acquisition_policy
        self.crawler = URLCrawler(
            timeout=timeout,
            user_agent=user_agent,
            acquisition_policy=acquisition_policy,
        )

    def _enrich_page(self, new_doc, url, max_chars):
        # #1294: a page record whose host is outside the active-site
        # acquisition scope is never dispatched to the crawler/provider —
        # no network call, no trusted enriched page.
        if self.acquisition_policy is not None and not self.acquisition_policy.is_authorized(url):
            new_doc["metadata"]["fetch_status"] = "out_of_scope"
            new_doc["metadata"]["fetch_error"] = (
                "URL host is outside the active-site acquisition scope"
            )
            new_doc["metadata"]["fetched_at"] = ""
            new_doc["metadata"]["http_status"] = ""
            new_doc["metadata"]["response_content_type"] = ""
            return new_doc

        try:
            result = self.crawler.analyze(url, max_chars=max_chars)

            # #1294: the observable final/effective URL after the fetch must
            # also stay in-scope; content served from an undeclared host is
            # never trusted as active-site enrichment.
            final_url = result.get("url") or url
            if (
                self.acquisition_policy is not None
                and not self.acquisition_policy.is_authorized(final_url)
            ):
                new_doc["metadata"]["fetch_status"] = "out_of_scope"
                new_doc["metadata"]["fetch_error"] = (
                    "Effective fetch URL is outside the active-site acquisition scope"
                )
                new_doc["metadata"]["fetched_at"] = ""
                new_doc["metadata"]["http_status"] = result.get("status_code")
                new_doc["metadata"]["response_content_type"] = result.get("content_type")
                return new_doc

            fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            new_doc["metadata"]["fetched_at"] = fetched_at
            new_doc["metadata"]["http_status"] = result.get("status_code")
            new_doc["metadata"]["response_content_type"] = result.get("content_type")

            errors = result.get("errors", [])
            if errors:
                new_doc["metadata"]["fetch_status"] = "error"
                new_doc["metadata"]["fetch_error"] = "; ".join(errors)
                if result.get("title"):
                    new_doc["title"] = result["title"]
                if result.get("text"):
                    new_doc["text"] = result["text"]
                if result.get("description"):
                    new_doc["metadata"]["description"] = result["description"]
            else:
                new_doc["metadata"]["fetch_status"] = "fetched"
                new_doc["metadata"]["fetch_error"] = ""
                if result.get("title"):
                    new_doc["title"] = result["title"]
                new_doc["text"] = result.get("text", "")
                new_doc["metadata"]["description"] = result.get("description", "")

        except Exception as e:
            new_doc["metadata"]["fetch_status"] = "error"
            new_doc["metadata"]["fetch_error"] = str(e)

        return new_doc

    def enrich_records(self, docs, max_chars=12000, limit=None):
        pages_processed = 0
        enriched_docs = []

        for doc in docs:
            new_doc = dict(doc)
            new_doc["metadata"] = dict(doc.get("metadata", {}))

            content_type = new_doc.get("content_type", "")

            if content_type == "page":
                if limit is not None and pages_processed >= limit:
                    new_doc["metadata"]["fetch_status"] = "not_processed"
                else:
                    url = new_doc.get("url")
                    new_doc = self._enrich_page(new_doc, url, max_chars)
                    pages_processed += 1

            elif content_type == "attachment":
                new_doc["metadata"]["fetch_status"] = "skipped"
                new_doc["metadata"]["fetch_error"] = "attachment fetching is not implemented in Stage 4"
                new_doc["metadata"]["fetched_at"] = ""
                new_doc["metadata"]["http_status"] = ""
                new_doc["metadata"]["response_content_type"] = ""
            else:
                new_doc["metadata"]["fetch_status"] = "skipped"
                new_doc["metadata"]["fetch_error"] = f"unsupported content_type: {content_type}"
                new_doc["metadata"]["fetched_at"] = ""
                new_doc["metadata"]["http_status"] = ""
                new_doc["metadata"]["response_content_type"] = ""

            enriched_docs.append(new_doc)

        return enriched_docs
