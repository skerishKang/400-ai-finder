import xml.etree.ElementTree as ET
import re

class SitemapParser:
    def __init__(self, max_sitemaps=10, max_sitemap_urls=500):
        self.max_sitemaps = max_sitemaps
        self.max_sitemap_urls = max_sitemap_urls

    def clean_xml_string(self, xml_content):
        if isinstance(xml_content, bytes):
            try:
                xml_content = xml_content.decode('utf-8', errors='ignore')
            except Exception:
                xml_content = xml_content.decode('latin-1', errors='ignore')
        
        # Remove namespace prefixes from tags (e.g. <xhtml:link ...> -> <link ...>, </xhtml:link> -> </link>)
        xml_content = re.sub(r'<([/]?)[a-zA-Z0-9_.-]+:([a-zA-Z0-9_.-]+)', r'<\1\2', xml_content)
        # Remove default and prefixed namespace definitions
        xml_content = re.sub(r'\sxmlns:[a-zA-Z0-9_.-]+="[^"]+"', '', xml_content)
        xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)
        return xml_content.strip()

    def parse(self, xml_content):
        result = {
            "urls": [],
            "sitemaps": [],
            "error": None
        }

        if not xml_content:
            result["error"] = "Empty XML content"
            return result

        try:
            cleaned_xml = self.clean_xml_string(xml_content)
            root = ET.fromstring(cleaned_xml)
        except ET.ParseError as e:
            result["error"] = f"XML Parse Error: {str(e)}"
            return result
        except Exception as e:
            result["error"] = f"Unexpected Error parsing XML: {str(e)}"
            return result

        root_tag = root.tag.lower()

        # Simple parse for root tags: sitemapindex or urlset
        if root_tag == 'sitemapindex':
            for sitemap_el in root.findall('sitemap'):
                loc_el = sitemap_el.find('loc')
                if loc_el is not None and loc_el.text:
                    result["sitemaps"].append(loc_el.text.strip())
        elif root_tag == 'urlset':
            for url_el in root.findall('url'):
                url_info = {
                    "url": "",
                    "lastmod": "",
                    "changefreq": "",
                    "priority": ""
                }
                
                loc_el = url_el.find('loc')
                if loc_el is not None and loc_el.text:
                    url_info["url"] = loc_el.text.strip()
                    
                lastmod_el = url_el.find('lastmod')
                if lastmod_el is not None and lastmod_el.text:
                    url_info["lastmod"] = lastmod_el.text.strip()
                    
                changefreq_el = url_el.find('changefreq')
                if changefreq_el is not None and changefreq_el.text:
                    url_info["changefreq"] = changefreq_el.text.strip()
                    
                priority_el = url_el.find('priority')
                if priority_el is not None and priority_el.text:
                    url_info["priority"] = priority_el.text.strip()

                if url_info["url"]:
                    result["urls"].append(url_info)
        else:
            # Fallback scan for documents with namespaces still bound or non-standard structures
            urls_found = []
            sitemaps_found = []
            
            for elem in root.iter():
                tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                tag_local = tag_local.lower()
                
                if tag_local == 'url':
                    url_info = {"url": "", "lastmod": "", "changefreq": "", "priority": ""}
                    for child in elem:
                        child_local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        child_local = child_local.lower()
                        if child_local in url_info:
                            url_info[child_local] = child.text.strip() if child.text else ""
                    if url_info["url"]:
                        urls_found.append(url_info)
                        
                elif tag_local == 'sitemap':
                    loc_val = ""
                    for child in elem:
                        child_local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        child_local = child_local.lower()
                        if child_local == 'loc':
                            loc_val = child.text.strip() if child.text else ""
                    if loc_val:
                        sitemaps_found.append(loc_val)
            
            if urls_found:
                result["urls"] = urls_found
            if sitemaps_found:
                result["sitemaps"] = sitemaps_found
                
            if not urls_found and not sitemaps_found:
                result["error"] = f"Unknown XML root tag: {root.tag}"

        return result
