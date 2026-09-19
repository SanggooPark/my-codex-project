# RAM — RAM(신뢰성·가용성·정비성) 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-RAM |
| 영문명 | RAM management process for products and services |
| 근거 조항 | ISO 22163:2023 8.8.2 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | RAMS 관리자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | LCC |
| 구현 모듈 | `rqms.services.rams` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.8.2 의 요구사항을 충족하기 위해 RAM(신뢰성·가용성·정비성) 관리 프로세스를 수립·실행·유지한다.

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
| 8.2.2.1.1 | shall | ISO 22163 추가 | 기능·비기능·RAMS/LCC·단산·중요특성 요구사항 고려 |
| 8.3.1.1 | shall | ISO 22163 추가 | 신기술 리스크 평가, 제품 아키텍처, RAMS/LCC, IEC 62278 적합 |
| 8.5.5.1 | shall | ISO 22163 추가 | 인도 후 활동 프로세스(기술문서 갱신·문제해결기법·수리지침·예비품) |
| 8.8.1 | shall | ISO 22163 추가 | RAM·안전 프로세스 운영 및 문서화된 정보 보유 |
| 8.8.2 | shall | ISO 22163 추가 | RAM 관리 프로세스(계산·설계반영·현장데이터·환류·목표감시) |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-029 | invariant | major | RAM 목표 미달 시 현장데이터 분석 및 시정조치 등록 | 8.8.2 |
| CTL-046 | audit | major | 요구사항은 기술규격으로 문서화되고 RAMS/LCC·단산·중요특성이 반영됨 | 8.2.2.1.1, 8.2.5, 8.3.4.3 |
| CTL-057 | audit | major | 안전관련 제품은 적용 안전표준 식별 및 안전 케이스 보유 | 8.3.1.1, 8.8.3 |
| CTL-059 | audit | minor | 인도 후 활동의 기술문서 갱신 및 승인된 수리지침 보유 | 8.5.5.1 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-RAM RAM 목표 달성률 | PI | 목표 달성 RAM 항목 수 / 감시 RAM 항목 수 x 100 | 100.0% | quarterly | top_management, 기술개발 책임자 | RAMS 관리자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 설계·개발 계획 | `design` (조건: `plan_doc_id IS NOT NULL`) |
| 현장 데이터 | `field_data` |
| 인도 후 활동 기록 | `post_delivery_activity` |
| RAMS 기록 | `rams_objective` |
| 수리지침 | `post_delivery_activity` (조건: `repair_instruction_doc_id IS NOT NULL`) |
| 요구사항 등록부 | `requirement` |
| 안전 케이스 | `safety_record` (조건: `safety_case_doc_id IS NOT NULL`) |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.2.2.1.1
python -m rqms matrix process
python -m rqms check
```
