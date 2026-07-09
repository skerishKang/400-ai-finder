# MVP chat shell 디자인 레퍼런스 (draft)

이 디렉터리는 `#992` runbook 이후 박사님이 요청하신 `/mvp/` 채팅 쉘 비주얼
교체를 위한 **디자인 레퍼런스**입니다. 실제 소스 CSS(`src/web/static/*.css`)는
아직 건드리지 않았습니다. 이 PR은 레퍼런스 + 방향 합의용 draft입니다.

## 선택된 방향

- **최종 선택: D (ChatGPT톤, 단색)** — `preview-chat-style-d-font.html`
  - 무지개/그라디언트 색 제거 (단색 `#0d0d0f`)
  - 장식 이모지 아이콘 제거
  - 폰트 스택을 ChatGPT 윈도우 폴백과 동일하게
    (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", ...`)
  - 보내기 버튼은 ChatGPT식 빨간 원형/알약 톤
  - Söhne 본체 폰트는 유료라 번들 불가 → 시스템 산세리프로 대체

## 파일

| 파일 | 설명 |
|------|------|
| `preview-chat-style-a.html` | A 정부/공공 세련형 (기각) |
| `preview-chat-style-b.html` | B 글래스모피즘 (기각) |
| `preview-chat-style-c.html` | C 미니멀 라이트 (기각) |
| `preview-chat-style-d-chatgpt.html` | D 초안 (그라디언트 포함, 기각) |
| `preview-chat-style-d-monochrome.html` | D 단색화 (아이콘 제거, 폰트 미정) |
| `preview-chat-style-d-font.html` | **D 최종 — 박사님 승인** |

## 차후 작업 (별도 PR)

실제 적용 시 범위:
- `citizen-copilot-shell.css` / `citizen-first-use-shell.css` 비주얼만 교체
- 로직/퀘스트/메타데이터/동작 변경 없음
- local/static 경계 유지, external request/navigation 추가 없음
- 관련 issue: #1028
