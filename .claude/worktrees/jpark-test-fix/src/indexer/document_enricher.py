import datetime
from src.crawler.url_crawler import URLCrawler

class DocumentEnricher:
    def __init__(self, timeout=15, user_agent=None):
        self.crawler = URLCrawler(timeout=timeout, user_agent=user_agent)

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
                    try:
                        result = self.crawler.analyze(url, max_chars=max_chars)
                        
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
