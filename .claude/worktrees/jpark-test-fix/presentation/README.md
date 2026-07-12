# AI파인더 발표자료

이 폴더는 400-ai-finder를 외부에 설명하기 위한 발표자료와 소개자료를 보관한다.

## 구성 원칙

AI파인더의 핵심 메시지는 하나로 고정한다.

> AI파인더는 복잡한 홈페이지를 사람 말로 찾아주는 AI 내비게이터다.

다만 대상에 따라 강조점은 달라진다.

## 자료 구성

```text
presentation/
├─ master/
│  ├─ ai-finder-master-brief.md
│  └─ ai-finder-master.html
├─ audience-company-ceo/
│  └─ company-ceo-deck.md
├─ audience-public-institution/
│  └─ public-institution-deck.md
└─ audience-consumer/
   └─ consumer-deck.md
```

## 대상별 메시지

| 대상 | 핵심 질문 | 강조점 |
|---|---|---|
| 회사 대표 | 이 사업이 돈이 되는가? | 시장성, 수익모델, MVP, 확장성 |
| 공기업 및 기관 | 도입하면 업무와 이용자 편의가 좋아지는가? | 민원 감소, 접근성, 보안, 근거 기반 안내 |
| 소비자 | 내가 원하는 정보를 쉽게 찾을 수 있는가? | 쉬움, 바로가기, 절차 안내, 시간 절약 |

## 사용 방식

- `master`는 제품의 기준 설명서다.
- 대상별 자료는 master의 메시지를 각 이해관계자의 언어로 바꾼 것이다.
- HTML 파일은 외부 공유와 시연용으로 사용한다.
- PPT가 필요한 경우 HTML 또는 Markdown을 기반으로 별도 변환한다.
