# Stage #863-B — Buk-gu Visual Fidelity Correction Report

## 1. 개요
* **목표**: 첫 시안에 제공되었던 피드백을 기반으로 디자인 보정을 완료하였습니다.
* **디자인 보정 사항**:
  - `BUK-GU OFFICE` 등 임의의 영문 브랜딩을 완전 배제하고, 실제 **"광주광역시 북구"**의 한국어 로고와 GNB 구조를 적용하였습니다.
  - 모니터 받침대, 디바이스 목업(모니터, 노트북 샷 등), PPT 제품 프레임 등을 모두 제거하고 오직 **플랫한 2D 웹 브라우저 뷰포트 자체**로 렌더링되도록 디자인을 통일했습니다.
  - 지나치게 둥근 앱 카드 형태(border-radius: 12px~20px)를 전면 교체하여, 실제 공공기관 포털 특유의 **각지고 컴팩트하며 정보 밀도가 높은 플랫한 UI**로 수정하였습니다.
  - 우측 AI 비서 하단의 입력 전송 버튼 텍스트를 영문 `Send`에서 한글 **`보내기`**로 수정하였습니다.
  - 민원 최종 접수 단계(State 3)에서 최종 제출 버튼을 **비활성화(Disabled)** 처리하고, 시연 안전 중지를 직관적으로 보여주는 **[⚠️ 제출 전 안전 중지 (Safety Stop)]** 경고 팝업 오버레이를 구현하였습니다.
  - **우측 첫 화면 대화창 수정**: 첫 환영 상태에서 사용자의 실제 질문 및 AI 비서의 연동 안내 답변 3개 턴이 기본 렌더링되게 개선하여 ChatGPT/Tabbit식의 대화식 시나리오 개연성을 제공합니다.

---

## 2. 실제 북구청 캡처 이미지 기반 좌측 화면

### 2.1 Capture Metadata

| 항목 | bukgu_home.png | bukgu_menu.png | bukgu_intake.png |
|------|---------------|---------------|-----------------|
| **파일명** | `bukgu_home.png` | `bukgu_menu.png` | `bukgu_intake.png` |
| **URL** | bukgu.gwangju.kr (메인 홈페이지) | bukgu.gwangju.kr (종합민원 > 전자민원창구 > 청원24) | bukgu.gwangju.kr (종합민원 > 민원서식) |
| **캡처 시각** | 2026-07-04 22:44 KST | 2026-07-04 22:44 KST | 2026-07-04 22:44 KST |
| **Viewport** | 1497×2608 px | 1497×2593 px | 1497×1600 px |
| **브라우저 Chrome 포함** | ❌ 없음 | ❌ 없음 | ❌ 없음 |
| **Crop 여부** | 전체 페이지 캡처 (crop 없음) | 전체 페이지 캡처 (crop 없음) | 전체 페이지 캡처 (crop 없음) |
| **저장 위치** | `src/web/static/images/bukgu_home.png` | `src/web/static/images/bukgu_menu.png` | `src/web/static/images/bukgu_intake.png` |

### 2.2 이미지별 화면 설명

| 이미지 | 설명 | 주요 UI 요소 |
|--------|------|-------------|
| `bukgu_home.png` | 광주광역시 북구청 메인 홈페이지 | GNB 메뉴(종합민원, 소통광장 등), 검색창, 바로가기 아이콘, 분야별 정보 |
| `bukgu_menu.png` | 종합민원 > 전자민원창구 > 청원24 안내 페이지 | 좌측 사이드바 메뉴(민원처리공개, 민원상담, 정부24, 청원24 등), 본문 안내 |
| `bukgu_intake.png` | 종합민원 > 민원서식 게시판 | 검색 필터, 민원서식 목록 테이블(번호, 민원사무명, 작성부서, 첨부파일), 페이지네이션 |

---

## 3. Transparent Overlay Target 정의

### 3.1 home route (bukgu_home.png)

| Target ID | Label | top | left | width | height | data-demo-route |
|-----------|-------|-----|------|-------|--------|-----------------|
| `nav-civil-service` | 민원 신청하기 (종합민원 GNB) | 2% | 18% | 7% | 2.5% | civil-service |

### 3.2 complaint-category route (bukgu_menu.png)

| Target ID | Label | top | left | width | height | data-demo-route |
|-----------|-------|-----|------|-------|--------|-----------------|
| `complaint-category-illegal-parking` | 불법 주정차 신고 | 22% | 3% | 45% | 3% | complaint-intake |
| `complaint-category-public-parking-inconvenience` | 공용주차장 불편 | 27% | 3% | 45% | 3% | complaint-intake |
| `complaint-category-residential-parking` | 공동주택 주차 관련 | 32% | 3% | 45% | 3% | complaint-intake |
| `complaint-category-traffic-or-facility-safety` | 교통·시설 안전 | 37% | 3% | 45% | 3% | complaint-intake |
| `complaint-category-other-or-unsure` | 기타 | 42% | 3% | 45% | 3% | complaint-intake |

### 3.3 complaint-intake route (bukgu_intake.png)

| Target ID | Label | top | left | width | height | data-demo-route |
|-----------|-------|-----|------|-------|--------|-----------------|
| `complaint-draft-review` | 검토용 초안 작성 | 40% | 5% | 50% | 3% | complaint-review |

### 3.4 Review Mode

- **활성화**: `?review=true` URL 파라미터 추가
- **동작**: 모든 transparent overlay target에 빨간색 테두리(`border: 2px solid #e74c3c`)와 `data-label`을 라벨로 표시
- **좌표 표시**: overlay 하단에 `data-coords` (top / left) 값 표시
- **일반 모드**: overlay는 완전 투명(transparent) 유지, hover 시에만 미세한 배경색 변화

---

## 4. 구현 구조

```
실제 북구청 캡처 이미지 (src/web/static/images/bukgu_*.png)
→ canvas-page--image-based CSS background-image
→ .canvas-image-overlay (position: absolute, transparent button)
→ data-action-target + data-demo-route 속성
→ click event delegation
→ route navigation + AI narration
```

---

## 5. 검증 결과
* **오프라인 테스트 결과**: **232 Passed / 0 Failed** (성공)
* **Git Diff 및 코드 위생**: `git diff --check` 무오류 통과. 모든 Trailing Whitespace 수정 완료.
* **제한 준수**: cursor/click animation, state machine 변경 등의 기능 추가가 일절 없음.
* **Browser Chrome 중복 확인**: 3개 이미지 모두 Chrome UI 미포함 확인 → 이중 브라우저 현상 없음.
* **Overlay 좌표 검증**: `?review=true` 모드에서 각 overlay 위치를 시각적으로 확인 가능.
* **Non-persistence 검증**: Network/Storage/Console 모두 clean 확인.
