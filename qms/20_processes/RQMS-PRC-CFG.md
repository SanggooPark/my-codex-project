# CFG — 형상 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-CFG |
| 영문명 | Configuration management process |
| 근거 조항 | ISO 22163:2023 8.1.4.1.1 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 형상관리 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.configuration` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.1.4.1.1 의 요구사항을 충족하기 위해 형상 관리 프로세스를 수립·실행·유지한다.

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
| 8.1.4.1.1 | shall | ISO 22163 추가 | 형상관리 프로세스(PBS·형상항목·기준선·형상상태기록) |
| 8.1.4.1.2 | should | ISO 22163 추가 | 형상감사·외부공급자 형상관리 연계·툴 지원 |
| 8.3.2.1.1 | shall | ISO 22163 추가 | 단계 목표·아키텍처·형상관리·계층별 설계검토/검증/유효성확인 |
| 8.3.4.5 | shall | ISO 22163 추가 | 검증·유효성확인 시험 요구사항(재현성·형상기준선·합격기준) |
| 8.4.2.1.1 | shall | ISO 22163 추가 | 신규/변경 EPPPS 출시승인(FAI·유효성확인·형상기준선) |
| 8.5.2 | shall | ISO 9001:2015 | 식별 및 추적성 |
| 8.5.2.1 | shall | ISO 22163 추가 | 보증종료까지 추적성 유지, 상태불명 제품은 부적합품 처리 |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-006 | invariant | major | 형상 기준선 변경은 승인된 변경요청에 의해서만 가능 | 8.1.4.1.1 |
| CTL-007 | audit | major | 안전관련 형상항목의 식별 및 표시 | 8.1.4.1.1 |
| CTL-015 | invariant | major | 식별 또는 상태가 불명한 품목은 부적합품으로 처리 | 8.5.2.1 |
| CTL-016 | invariant | major | FAI 승인 전 양산 출시·공정 유효성확인 완료 금지 | 8.4.2.1.1, 8.5.1.1.4.1, 8.9.1, 8.9.3 |
| CTL-032 | audit | major | 추적성 요구 품목은 보증종료 시점까지 추적성 유지 | 8.5.2, 8.5.2.1 |
| CTL-047 | invariant | major | 검증·유효성확인 시험은 시험계획(목적·조건·합격기준)과 형상기준선 기록 필요 | 8.3.2.1.1, 8.3.4.5 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-CHG 변경 적시 처리율 | PI | 목표 리드타임 내 종결 변경 수 / 종결 변경 수 x 100 | 90.0% | monthly | 형상관리 책임자, 사업관리(PMO) 책임자 | 형상관리 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 형상 감사/상태 기록 | `config_status_record` |
| 형상 기준선 | `baseline` |
| 형상관리 계획서 | `project_plan` (조건: `plan_kind = 'configuration'`) |
| 형상상태 기록 | `config_status_record` |
| 설계·개발 계획 | `design` (조건: `plan_doc_id IS NOT NULL`) |
| EPPPS 출시 승인 | `eppps_release` |
| 시험계획 | `design_test` (조건: `plan_doc_id IS NOT NULL`) |
| 시험 기록 | `design_test` (조건: `performed_on IS NOT NULL`) |
| 추적성 기록 | `traceable_item` |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.1.4.1.1
python -m rqms matrix process
python -m rqms check
```
