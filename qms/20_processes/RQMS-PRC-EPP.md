# EPP — 외부공급 프로세스·제품·서비스(EPPPS) 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-EPP |
| 영문명 | Process for externally provided processes, products and services |
| 근거 조항 | ISO 22163:2023 8.4.1.1.1 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 구매 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.suppliers` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.4.1.1.1 의 요구사항을 충족하기 위해 외부공급 프로세스·제품·서비스(EPPPS) 관리 프로세스를 수립·실행·유지한다.

## 2. 프로세스 정의 (4.4.1 a~e)

프로세스의 입력·출력, 순서 및 상호작용, 판정기준과 성과지표, 필요자원, 책임과 권한은 RQMS 데이터베이스의 `process_instance` 레코드에 등록되어 있으며, 등록 없이는 프로세스를 운영할 수 없다(CTL-038, CTL-039).

| 4.4.1 항목 | 등록 위치 |
| --- | --- |
| a) 입력·출력 | `process_instance.inputs` / `.outputs` |
| b) 순서 및 상호작용 | `process_instance.sequence_note` |
| c) 판정기준·측정·성과지표 | `process_instance.criteria` 및 아래 5장 성과지표 |
| d) 필요 자원 | `process_instance.resources` |
| e) 책임 및 권한 | `process_instance.owner_id` (프로세스 오너) |
| 4.4.3 f) 리스크기반 통제기준 | `process_instance.risk_criteria` |

## 3. 관련 요구사항

| 조항 | 의무 | 출처 | 요구사항 |
| --- | --- | --- | --- |
| 8.1.3.10 | shall | ISO 22163 추가 | 프로젝트 조달 관리(8.4 요구사항 적용) |
| 8.4.1 | shall | ISO 9001:2015 | 외부에서 제공되는 프로세스·제품·서비스의 관리 — 일반 |
| 8.4.1.1.1 | shall | ISO 22163 추가 | EPPPS 프로세스(분류·평가·승인·선정·정보·출시승인·검증·성과감시) |
| 8.4.1.1.2 | shall | ISO 22163 추가 | 외부공급자 및 EPPPS 분류(핵심 공급자 식별·정기 재검토) |
| 8.4.1.1.3 | shall | ISO 22163 추가 | 외부공급자 평가(인원·기반구조·프로세스·인증 보유) |
| 8.4.1.1.4 | shall | ISO 22163 추가 | 외부공급자 승인(기준·거부권한·승인 공급자 등록부), 승인자만 공급 |
| 8.4.1.1.5.1 | shall | ISO 22163 추가 | 견적 선정 분석(조항별 적합성·총소유비용/LCC·과거 QCD 성과·분류) |
| 8.4.1.1.5.2 | should | ISO 22163 추가 | 리스크 분석 결과·운용성숙도 고려, 발주 전 기술요구사항 상호확인 |
| 8.4.2 | shall | ISO 9001:2015 | 관리의 유형과 정도 |
| 8.4.2.1.1 | shall | ISO 22163 추가 | 신규/변경 EPPPS 출시승인(FAI·유효성확인·형상기준선) |
| 8.4.2.1.2 | should | ISO 22163 추가 | 양산 전 검토 및 최초 시스템 통합 고려 |
| 8.4.2.2 | shall | ISO 22163 추가 | 출시 후 EPPPS 검증(미검증 사용금지·검사계획·위임 등록부) |
| 8.4.2.3 | shall | ISO 22163 추가 | 외부공급자 성과 감시·재평가·등급화 및 개발 조치계획 |
| 8.4.3 | shall | ISO 9001:2015 | 외부공급자에 대한 정보 |
| 8.4.3.1 | shall | ISO 22163 추가 | 요구사항 전개·개정 식별·특수공정 승인·제품 중요도·출입권 |
| 8.4.4 | shall | ISO 22163 추가 | 공급망 관리(발주 확인서 수령·변경요청 문서화·납기 예측 공유) |
| 8.9.3 | shall | ISO 22163 추가 | FAI 적용 대상(내부제품·EPPPS, 신제품/중대변경 후 대표품) |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-011 | invariant | major | EPPPS는 승인된 외부공급자에게만 발주 | 8.4.1.1.1, 8.4.1.1.4, 8.1.3.10 |
| CTL-012 | invariant | major | 인수검증 미완료 EPPPS의 사용·투입 금지(승인된 특채 시 예외) | 8.4.2.2 |
| CTL-013 | audit | minor | 검증활동 위임은 위임 등록부 등록 및 공급자 동의 증거 보유 | 8.4.2.2 |
| CTL-016 | invariant | major | FAI 승인 전 양산 출시·공정 유효성확인 완료 금지 | 8.4.2.1.1, 8.5.1.1.4.1, 8.9.1, 8.9.3 |
| CTL-048 | audit | major | 외부공급자 분류·평가·성과감시 및 핵심 공급자 식별 유지 | 8.4.1.1.2, 8.4.1.1.3, 8.4.1.1.5.1, 8.4.2.3 |
| CTL-049 | audit | minor | 구매발주 확인서 수령 및 공급망 정보 최신 유지 | 8.4.3.1, 8.4.4 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-ENC 외부공급자 부적합률 | PI | 부적합 외부공급 수량 / 총 구매 수량 x 1000000 (ppm) | 1000.0ppm | monthly | 구매 책임자, process_owners | 구매 책임자 |
| PI-EOTD 외부공급자 납기준수율 | PI | 적시 입고 수량 / 외부공급자 납입 수량 x 100 | 95.0% | monthly | 구매 책임자, process_owners | 구매 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 검증 위임 등록부 | `verification_delegation` |
| EPPPS 출시 승인 | `eppps_release` |
| FAI 기록 | `fai` |
| 인수검사 기록 | `incoming_inspection` |
| 견적 선정 분석 | `governance_record` (조건: `kind = 'offer_selection'`) |
| 발주 확인서 | `purchase_order` (조건: `acknowledged_on IS NOT NULL`) |
| 구매발주 | `purchase_order` |
| 공급자 관리 범위 | `supplier` (조건: `TRIM(approval_scope) != ''`) |
| 공급자 평가 기록 | `supplier` (조건: `evaluated_on IS NOT NULL`) |
| 공급자 성과검토 | `supplier` (조건: `performance_reviewed_on IS NOT NULL`) |
| 공급자 등록부 | `supplier` |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.1.3.10
python -m rqms matrix process
python -m rqms check
```
