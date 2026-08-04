---
name: Bug report
about: 기능·데이터·출처·UI·배포 회귀를 보고합니다
title: "bug: "
labels: ""
assignees: ""
---

## 문제

<!-- 실제 결과와 기대결과를 구분하세요. -->

## 영향받는 product track

- [ ] 북구 golden clone
- [ ] 근거 기반 AI 시민안내
- [ ] 공식정보 freshness
- [ ] Python crawler·operator runtime
- [ ] Cloudflare citizen runtime
- [ ] Page Agent comparison
- [ ] Multi-site platform
- [ ] Authorized first-party integration
- [ ] Repository·documentation governance

## 환경과 exact refs

- URL / route:
- Environment: local / CI / preview / production
- Commit / deployed SHA:
- Browser / OS / viewport:
- Locale:
- Provider / model:
- Site ID:

## 재현절차

1.
2.
3.

## 기대결과


## 실제결과


## Source·data·freshness

- Source URL:
- Snapshot ID / checksum:
- Captured / verified / source updated time:
- Freshness state:
- 실제 데이터나 개인정보는 첨부하지 않았는가: Yes / No

## 안전영향

- [ ] 실제 submit·login·payment 가능성
- [ ] 개인정보·secret 노출
- [ ] 공식근거 없는 고위험 행정정보
- [ ] 잘못된 외부 URL·endpoint
- [ ] 무제한 비용·abuse
- [ ] Golden route·DOM·state regression
- [ ] 접근성·mobile blocker
- [ ] 없음

## Network mode

- [ ] Offline / fixture
- [ ] Controlled read-only live
- [ ] Provider staging
- [ ] Production

## Evidence

- Sanitized log:
- Screenshot / trace:
- Request ID:
- CI run:

민감한 key·PII·공격 payload 원문은 공개 issue에 붙이지 마세요. 보안문제는 `SECURITY.md`를 따르세요.

## 임시 완화


## 완료조건

- [ ] 재현 테스트 추가
- [ ] 원인 수정
- [ ] 관련 golden·source·locale·browser 계약 통과
- [ ] 보안·개인정보 검토
- [ ] rollback 또는 deployment verification
