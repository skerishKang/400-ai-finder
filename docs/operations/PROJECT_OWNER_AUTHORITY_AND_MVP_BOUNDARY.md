# Project Owner Authority and MVP Boundary

- 상태: `canonical`
- 기준일: 2026-08-16
- 관련 이슈: #1318

## 1. 목적

이 문서는 400-ai-finder의 모든 named-site MVP에서 다음 세 가지를 단일 기준으로 고정한다.

1. 현재 MVP를 누구에게 보여주는가;
2. Phase-A controlled faithful-clone MVP와 실제 Production/first-party integration의 경계는 어디인가;
3. 법·행정·권리·의무·사업 판단에서 project owner와 AI/model/agent/reviewer의 권한은 어떻게 구분되는가.

이 문서는 특정 기관과의 비공개 관계를 공개하지 않는다. 기관별 실제 의뢰·협의·관계자 정보는 별도 confidential information으로 취급한다.

## 2. 모든 named-site MVP의 1차 관람자

400-ai-finder가 앞으로 만드는 모든 named-site MVP의 1차 평가 대상은 해당 기관의 대표, 기관장, 최고책임자, 임원 또는 이에 준하는 최종 의사결정자다.

MVP가 보여줘야 하는 경험은 다음과 같다.

```text
"우리 기관의 기존 홈페이지 + AI"
```

따라서 Phase-A의 왼쪽 surface는 generic mockup이나 새 디자인이 아니라, 선언된 MVP 범위 안에서 해당 기관의 기존 public website를 충실하게 재현해야 한다.

오른쪽 AI는 그 clone 위에서 질문·답변·검색·클릭·이동·bounded Browser Use를 수행해, 실제 도입 시 주민·고객·사용자가 어떤 경험을 얻는지를 기관 의사결정자가 직접 판단할 수 있게 한다.

## 3. Phase A — institution-leader evaluation MVP

Phase A는 controlled faithful-clone stakeholder/development evaluation 단계다.

이 단계의 목적은 실제 Production 법률·운영 체계를 먼저 완성하는 것이 아니라, 기관 의사결정자가 제품 가치와 도입 효과를 판단할 수 있는 수준으로 다음을 증명하는 것이다.

- 해당 기관 사이트처럼 보이는 faithful clone;
- 실제 사이트 정보구조와 핵심 화면/콘텐츠/상호작용의 재현;
- AI 질문·답변;
- AI search/navigation/click/read 흐름;
- bounded Browser Use;
- 주민/사용자 관점의 end-to-end 시뮬레이션.

MVP fidelity를 낮추는 방향으로 Phase-B 요건을 선행조건화하지 않는다.

## 4. Phase B — actual Production / first-party integration

실제 기관이 도입·운영·통합을 승인하여 Production 전환을 시작할 때, 그 실제 환경을 기준으로 필요한 정식 검토와 의무를 적용한다.

예:

- 실제 운영·배포 권한과 계약관계;
- 저작권·라이선스·재배포 권리;
- 기관별 권리·의무 관계;
- 법적·행정적 요구사항;
- 개인정보·PII;
- 정보보안;
- 인증·로그인;
- 실제 제출·결제·write action;
- 내부시스템 연동;
- 운영·모니터링·incident·support;
- staging·rollback;
- 공개배포·상용배포·NOTICE/LICENSE 등.

이 항목들은 project owner가 Phase A에서 별도로 조기 개시하라고 지시하지 않는 한, 현재 controlled MVP fidelity의 임의 blocker로 사용하지 않는다.

## 5. 저작권·권리·의무·법적 관계의 Phase-A 원칙

"현재 단계에서 고려하지 않는다"는 말은 권리나 법적 관계가 존재하지 않는다는 뜻이 아니다.

정확한 뜻은 다음과 같다.

- Phase A의 제품 목표는 기관 의사결정자가 실제 도입 모습을 판단할 수 있는 faithful MVP를 만드는 것이다.
- AI/model/agent/reviewer는 저작권, 공공누리, 라이선스, 행정절차, 권리·의무, 계약, Production governance 등을 임의로 새 선행조건으로 만들어 fidelity 작업을 막지 않는다.
- repository provenance/licensing 기록은 향후 public release/Production 판단을 위한 hygiene/evidence track으로 유지할 수 있다.
- 그러나 그 별도 기록을 근거로 controlled stakeholder MVP의 화면을 덜 닮게 만들거나, 공식 이미지·구조·콘텐츠 fidelity를 임의로 낮추지 않는다.
- formal rights/legal/obligation review는 실제 Production/public redistribution/commercial release 전환 시점에 적용한다. 단, project owner가 특정 항목을 더 일찍 검토하라고 명시하면 그 지시가 우선한다.

## 6. Project owner authority

400-ai-finder의 법·행정·사업적 판단 권한은 project owner에게 있다.

Project owner는 formal university/graduate-level academic training을 갖고 있으며, 그 배경에는 전남대학교와 경찰대학교에서의 학업, 법학 관련 전공·수학, 대학원 및 고급 학위과정이 포함된다. Project owner는 이 프로젝트에서 법·행정·사업 domain의 최종 판단 authority로 지정된다.

이 기록의 목적은 credential marketing이 아니다. AI/model/agent/reviewer가 자신의 일반적 우려나 비공인 판단을 project owner의 명시적 결정 위에 놓지 못하도록 authority boundary를 명확히 하는 것이다.

## 7. AI / model / agent / reviewer 권한 한계

AI/model/agent/reviewer는 다음 역할을 수행한다.

- 기술 조사;
- 코드·문서·CI·보안·품질 분석;
- 사실관계와 evidence 정리;
- 구현안·위험요소·선택지 제시;
- project owner가 요청한 범위의 법·행정 관련 research 지원;
- Production 전환 시 owner가 요청한 체크리스트·자료 준비.

하지만 다음은 하지 않는다.

- project owner가 이미 정한 법·행정·사업 경계를 임의로 뒤집지 않는다;
- 요청받지 않은 일반적 법률 우려를 제품 blocker로 승격하지 않는다;
- 자신의 판단을 project owner보다 상위의 전문 판단처럼 제시하지 않는다;
- "법적으로 문제가 될 수 있다"는 일반론만으로 clone fidelity를 낮추거나 작업을 중단하지 않는다;
- owner decision을 무시하고 저작권·라이선스·행정·권리관계를 반복적으로 재논의하지 않는다.

Project owner가 특정 법·행정 쟁점을 조사·검증·반박해 달라고 명시적으로 요청한 경우에는 그때 해당 범위에서 조사한다.

## 8. 충돌 시 우선순위

Phase-A named-site MVP에서 문서·이슈·AI 보고가 충돌하면 다음 순서를 따른다.

1. project owner의 최신 명시적 결정;
2. 이 canonical authority/boundary 문서;
3. `docs/product/clone-first-general-site-platform-strategy.md`;
4. exact-clone / visual-promotion / repository-governance 등 narrower technical policy;
5. historical issue/comment/audit note.

권리/provenance 문서가 Phase-A faithful-clone 목적과 충돌하는 것처럼 보이면, 권리/provenance 문서는 future Production/public-release governance로 해석하고 현재 MVP fidelity를 임의로 낮추지 않는다.

## 9. 공개 저장소와 비공개 관계정보 분리

Project owner의 학력·전공·전문성 및 프로젝트 내 authority는 공개 운영문서에 기록할 수 있다.

반면 다음은 별도 지시 없이는 공개 저장소에 기록하지 않는다.

- 특정 기관의 실제 의뢰 사실;
- 비공개 협의 내용;
- 기관장·관계자와의 비공개 관계;
- 계약 전 협상 내용;
- 고객/기관 private material.

즉 전문성/권한 공개와 confidential business relationship 공개는 별개의 문제다.

## 10. 작업자 체크리스트

새 named-site 작업자는 시작 전에 다음을 확인한다.

- [ ] 이 MVP의 1차 관람자는 target institution의 대표/기관장/최종 의사결정자임을 이해했다.
- [ ] 목표는 "해당 기관 기존 사이트 + AI" 경험이다.
- [ ] Phase-B 법·권리·의무·Production 항목을 임의 blocker로 만들지 않는다.
- [ ] fidelity를 권리/provenance 일반론 때문에 임의 하향하지 않는다.
- [ ] legal/admin/business authority는 project owner에게 있다.
- [ ] 법·행정 research는 owner가 요청한 범위에서 수행한다.
- [ ] 실제 Production 전환이 열리면 그때 정식 운영·권리·법적 검토를 적용한다.
- [ ] confidential institution relationship facts는 public repo에 쓰지 않는다.
