# Buk-gu live LLM site conversation demo package

## Demo purpose

이 데모는 400-ai-finder가 특정 공식 사이트를 실시간으로 fetch하고, 실제 LLM을 사용해 사용자의 질문에 출처 기반 답변을 생성하는 흐름을 보여준다.

Example target:
- 광주광역시 북구청
- bukgu.gwangju.kr
- site profile: bukgu_gwangju

## Demo status summary

| Item | Status |
|------|--------|
| MVP validation | completed |
| Live fetch + live LLM validation | completed |
| Demo rehearsal | completed |
| Demo-ready decision | yes |
| Provider used in rehearsal | NVIDIA |
| Model used in rehearsal | openai/gpt-oss-120b |
| Fetch provider | requests |
| Firecrawl | not used |

## Presenter opening script

```
오늘 보여드릴 것은 특정 기관 사이트를 AI가 직접 읽고, 사용자의 질문에 맞춰 출처 기반 답변을 생성하는 데모입니다.

예시는 광주광역시 북구청 사이트입니다.

단순히 저장된 답변을 보여주는 것이 아니라, 실제 사이트에서 관련 자료를 가져오고, LLM이 그 자료를 바탕으로 답변을 생성하는 흐름을 확인합니다.

오늘은 공지사항, 민원, 청년·일자리 질문을 중심으로 시연하고, 마지막에는 답변 출처가 북구청 공식 도메인에 근거하는지 확인하겠습니다.
```

## Recommended live demo questions

Use only the strongest three questions from Stage 336:

```
Q1. 북구청에서 최근 공지사항이나 고시공고를 어디에서 확인할 수 있나요?

Q2. 북구청 민원 신청이나 온라인 민원 안내는 어디에서 확인할 수 있나요?

Q3. 북구청 사이트에서 청년 또는 일자리 관련 정보를 찾으려면 어떻게 접근해야 하나요?
```

Important:
- Do not use the previous Q5 as a live demo question.
- Q5 was a domain verification request, not a search query, and may return 0 results.
- Domain verification should be shown by inspecting the sources from Q1~Q3.

## Demo flow

Step-by-step sequence:

```txt
Step 1. Show the target site/profile
- bukgu.gwangju.kr
- bukgu_gwangju

Step 2. Run Q1
- Explain that the system finds notices/announcements or 고시공고-related pages.
- Show answer and source URLs.

Step 3. Run Q2
- Explain civil service / online 민원 flow.
- Show answer and source URLs.

Step 4. Run Q3
- Explain youth/jobs search.
- Mention that municipal sites may use different menu terms such as 청년, 일자리, 채용, 고용, 비즈광주북구.

Step 5. Show source grounding
- Confirm that source URLs come from bukgu.gwangju.kr or relevant official subdomains such as eminwon.bukgu.gwangju.kr.
- If an official external domain appears, explain why it is contextually relevant.
```

## Command template

Safe command template using placeholders only:

```bash
export AI_FINDER_LLM_PROVIDER=nvidia
export NVIDIA_API_KEY="<LOCAL_SECRET_ONLY>"
export AI_FINDER_FETCH_PROVIDER=requests

python scripts/demo_answer.py \
  --allow-live \
  --fetch-provider requests \
  --site-profile bukgu_gwangju \
  --question "북구청에서 최근 공지사항이나 고시공고를 어디에서 확인할 수 있나요?"
```

Important:
- If actual CLI syntax differs, adjust based on existing docs/operator-quickstart.md and argparse definitions.
- Do not run the command during this Stage.
- Do not include real API keys.

## Demo talking points

- 이 프로젝트는 사이트별 profile을 기준으로 특정 기관 사이트를 탐색한다.
- 답변은 LLM 단독 추론이 아니라 fetch된 source에 근거한다.
- 공식 도메인 grounding을 확인할 수 있다.
- 검색어와 기관 사이트 메뉴명이 다르면 WARN이 발생할 수 있다.
- WARN은 반드시 실패가 아니라 운영자가 대체 메뉴명/검색어를 시도해야 하는 신호다.

## Source/domain verification script

```
출처를 보시면 bukgu.gwangju.kr 또는 관련 공식 서브도메인에 근거하고 있습니다.

이 데모에서는 Q5처럼 "도메인을 확인해 달라"는 질문을 별도로 실행하기보다, 실제 질문에 대한 답변 하단의 source URL을 직접 확인하는 방식으로 검증합니다.
```

## Failure backup lines

네트워크 실패 시:
- 이 데모는 실시간 사이트 fetch를 사용하기 때문에 기관 사이트 응답 상태나 네트워크 환경에 영향을 받을 수 있습니다.

LLM/API 실패 시:
- 현재 데모는 외부 LLM API를 사용하므로 provider 상태, API key 설정, rate limit의 영향을 받을 수 있습니다.

검색 결과가 약할 때:
- 일부 공공기관 사이트는 자연어 표현과 실제 메뉴명이 다를 수 있습니다. 이 경우 청년, 일자리, 채용, 고용, 비즈광주북구처럼 공식 메뉴에 가까운 대체 검색어를 사용합니다.

외부 공식 도메인이 포함될 때:
- 복지나 고용 정보는 고용복지플러스센터 같은 공식 외부 도메인이 함께 등장할 수 있습니다. 이 경우 질문 맥락과 공식성을 함께 확인합니다.

## Demo readiness checklist

## Demo readiness checklist

- [ ] API key is set only in local shell env.
- [ ] No API key is written to files, docs, logs, PRs, or issues.
- [ ] `--allow-live` is used intentionally.
- [ ] Fetch provider is `requests`.
- [ ] Firecrawl is not used for the basic demo.
- [ ] Target site/profile is `bukgu_gwangju`.
- [ ] Q1, Q2, Q3 are ready.
- [ ] Source URLs are checked after each answer.
- [ ] Q5-style domain verification is handled by showing sources, not by running it as a search query.
- [ ] Backup lines are prepared for network/API/search weakness.

## Short demo conclusion script

```
이 데모의 핵심은 AI가 단순히 일반 지식을 말하는 것이 아니라, 특정 공공기관 사이트에서 가져온 자료를 바탕으로 답변한다는 점입니다.

북구청 예시에서는 공지사항, 민원, 청년·일자리 질문에 대해 실제 출처 기반 답변을 생성하는 흐름을 확인했습니다.

따라서 400-ai-finder는 특정 사이트를 AI와 대화하면서 탐색하는 MVP를 넘어, 제한된 조건에서 외부 시연 가능한 상태입니다.
```