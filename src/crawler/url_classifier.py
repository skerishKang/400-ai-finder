import os
from urllib.parse import urlparse

CATEGORY_PRIORITY = {
    "document": 7,
    "apply": 6,
    "notice": 5,
    "board": 4,
    "contact": 3,
    "menu": 2,
    "unknown": 1,
}

def classify_url(url, text="", is_navigation=False):
    url_lower = url.lower()
    text_lower = text.lower()

    # 1. document rule
    # Check extension
    parsed = urlparse(url)
    _, ext = os.path.splitext(parsed.path)
    ext = ext.lower().lstrip('.')
    document_extensions = {'pdf', 'hwp', 'hwpx', 'docx', 'xlsx'}

    document_keywords = {'data', 'download', 'file', '자료', '서식', '양식', '첨부', 'document', 'docs'}
    if ext in document_extensions or any(k in url_lower or k in text_lower for k in document_keywords):
        return "document"

    # 2. apply rule
    apply_keywords = {'apply', 'application', 'register', 'registration', '신청', '접수', '등록'}
    if any(k in url_lower or k in text_lower for k in apply_keywords):
        return "apply"

    # 3. notice rule
    notice_keywords = {'notice', 'notices', 'announcement', 'announcements', '공지', '알림', '소식', '공고', '고시공고', '입법예고', '채용공고'}
    if any(k in url_lower or k in text_lower for k in notice_keywords):
        return "notice"

    # 4. board rule
    board_keywords = {'board', 'bbs', '게시판', '게시', '글', 'article'}
    if any(k in url_lower or k in text_lower for k in board_keywords):
        return "board"

    # 5. contact rule
    contact_keywords = {'contact', 'inquiry', 'help', 'support', '문의', '연락', '상담', '조직도', '직원검색', '부서안내', '전화번호', '담당자', '담당업무'}
    if any(k in url_lower or k in text_lower for k in contact_keywords):
        return "contact"

    # 6. location rule
    location_keywords = {'청사', '청사안내', '오시는 길', '오시는길', '찾아오시는길', '주차', '주차안내', '위치', 'parking'}
    if any(k in url_lower or k in text_lower for k in location_keywords):
        return "location"

    # 7. menu rule (only if it is detected inside navigation area and has not matched any of the above)
    if is_navigation:
        return "menu"

    return "unknown"
