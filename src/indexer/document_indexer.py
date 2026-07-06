import os
import json
from urllib.parse import urlparse, urlunparse

def make_canonical_url(url):
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        
    query = parsed.query
    params = parsed.params
    
    return urlunparse((scheme, netloc, path, params, query, ''))

def get_last_segment(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1]

from src.crawler.url_classifier import CATEGORY_PRIORITY

class DocumentIndexer:
    def __init__(self):
        pass

    def build_index(self, homepage_map):
        base_url = homepage_map.get("base_url", "")
        merged_docs = {}

        def get_or_create_doc(url, canonical_url):
            if canonical_url not in merged_docs:
                merged_docs[canonical_url] = {
                    "id": "",
                    "url": url,
                    "canonical_url": canonical_url,
                    "title": "",
                    "category": "unknown",
                    "source_types": set(),
                    "content_type": "page",
                    "text": "",
                    "summary": "",
                    "metadata": {
                        "base_url": base_url,
                        "lastmod": "",
                        "changefreq": "",
                        "priority": "",
                        "link_texts": set(),
                        "file_type": "",
                        "discovered_from": set()
                    },
                    "_title_priority": 0
                }
            return merged_docs[canonical_url]

        # 1. Process Sitemap URLs
        sitemap_section = homepage_map.get("sitemap", {})
        sitemap_urls = sitemap_section.get("urls", []) if sitemap_section else []
        for item in sitemap_urls:
            url = item.get("url", "")
            if not url:
                continue
            canonical = make_canonical_url(url)
            doc = get_or_create_doc(url, canonical)
            
            doc["source_types"].add("sitemap")
            doc["metadata"]["discovered_from"].add("sitemap")
            
            for k in ["lastmod", "changefreq", "priority"]:
                if item.get(k) and not doc["metadata"][k]:
                    doc["metadata"][k] = item[k]
                    
            cat = item.get("category", "unknown")
            if CATEGORY_PRIORITY.get(cat, 1) > CATEGORY_PRIORITY.get(doc["category"], 1):
                doc["category"] = cat
                
            # Title priority 1: URL path last segment
            if doc["_title_priority"] < 1:
                last_seg = get_last_segment(url)
                if last_seg:
                    doc["title"] = last_seg
                    doc["_title_priority"] = 1

        # 2. Process Homepage Navigation Links
        homepage_section = homepage_map.get("homepage", {})
        nav_links = homepage_section.get("navigation_links", []) if homepage_section else []
        for item in nav_links:
            url = item.get("url", "")
            if not url:
                continue
            canonical = make_canonical_url(url)
            doc = get_or_create_doc(url, canonical)
            
            doc["source_types"].add("navigation")
            doc["metadata"]["discovered_from"].add("navigation")
            
            text = item.get("text", "").strip()
            if text:
                doc["metadata"]["link_texts"].add(text)
                
            cat = item.get("category", "unknown")
            if CATEGORY_PRIORITY.get(cat, 1) > CATEGORY_PRIORITY.get(doc["category"], 1):
                doc["category"] = cat
                
            # Title priority 3: navigation link text
            if text and doc["_title_priority"] < 3:
                doc["title"] = text
                doc["_title_priority"] = 3
            elif not text and doc["_title_priority"] < 1:
                last_seg = get_last_segment(url)
                if last_seg:
                    doc["title"] = last_seg
                    doc["_title_priority"] = 1

        # 3. Process Homepage Attachment Links
        att_links = homepage_section.get("attachment_links", []) if homepage_section else []
        for item in att_links:
            url = item.get("url", "")
            if not url:
                continue
            canonical = make_canonical_url(url)
            doc = get_or_create_doc(url, canonical)
            
            doc["source_types"].add("attachment")
            doc["metadata"]["discovered_from"].add("attachment")
            doc["content_type"] = "attachment"
            
            text = item.get("text", "").strip()
            if text:
                doc["metadata"]["link_texts"].add(text)
                
            file_type = item.get("type", "").lower()
            if file_type:
                doc["metadata"]["file_type"] = file_type
                
            # Attachment links always take "document" category as highest priority
            doc["category"] = "document"
            
            # Title priority 2: attachment link text
            if text and doc["_title_priority"] < 2:
                doc["title"] = text
                doc["_title_priority"] = 2
            elif not text and doc["_title_priority"] < 1:
                last_seg = get_last_segment(url)
                if last_seg:
                    doc["title"] = last_seg
                    doc["_title_priority"] = 1

        # 4. Sort by canonical_url and Post-process sets to sorted lists
        sorted_docs = sorted(merged_docs.values(), key=lambda x: x["canonical_url"])
        
        for idx, doc in enumerate(sorted_docs, start=1):
            doc["id"] = f"doc-{idx:06d}"
            doc["source_types"] = sorted(list(doc["source_types"]))
            doc["metadata"]["discovered_from"] = sorted(list(doc["metadata"]["discovered_from"]))
            doc["metadata"]["link_texts"] = sorted(list(doc["metadata"]["link_texts"]))
            
            # Clean temporary property
            del doc["_title_priority"]
            
        return sorted_docs
