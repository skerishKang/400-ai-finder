from pathlib import Path

path = Path("docs/operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md")
text = path.read_text(encoding="utf-8")
old = """- [ ] 서버측 rate limit
- [ ] Turnstile production site key·encrypted secret·allowed hostname 설정 및 staging 검증
- [x] request body·question limit
- [x] provider·전체 timeout
- [ ] concurrency limit
- [ ] 일·월 비용상한
- [ ] privacy warning
- [ ] 최소 DLP·redaction 정책 전체범위
- [x] raw transcript 기본 비보관 정책
"""
new = """- [ ] 서버측 rate limit
- [x] Turnstile bot-defense code·offline contract
- [ ] Turnstile production site key·encrypted secret·allowed hostname 설정 및 staging 검증
- [x] request body·question limit
- [x] provider·전체 timeout
- [ ] concurrency limit
- [ ] 일·월 비용상한
- [x] privacy warning
- [x] 최소 DLP·redaction baseline (resident-ID fail-closed + phone/email/precise-address redaction)
- [ ] 확장 DLP (외국인등록번호·카드/계좌·자유서술 민감정보)
- [x] raw transcript 기본 비보관 정책
"""
if old not in text:
    raise SystemExit("security checklist anchor not found exactly once")
if text.count(old) != 1:
    raise SystemExit(f"security checklist anchor count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("#1224-B security checklist closeout applied")
