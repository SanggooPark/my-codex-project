# KNW — 조직 지식 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-KNW |
| 영문명 | Organizational knowledge management process |
| 근거 조항 | ISO 22163:2023 7.1.6.1.2 |
| 구분 | 권고 프로세스 (Annex A.2) |
| 프로세스 오너 | 품질보증 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.support` |
| 프로세스 검토 주기 | 24개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 7.1.6.1.2 의 요구사항을 충족하기 위해 조직 지식 관리 프로세스를 수립·실행·유지한다.

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
| 7.1.6 | shall | ISO 9001:2015 | 조직의 지식 |
| 7.1.6.1.1 | shall | ISO 22163 추가 | 경험 환류(good practice·교훈) 관리 및 지식 이전 |
| 7.1.6.1.2 | should | ISO 22163 추가 | 조직 지식 관리 프로세스 |
| 8.1.3.1.2 | should | ISO 22163 추가 | 에스컬레이션·SWOT 검토·프로젝트 종료 교훈 |
| 9.2.3.1 | shall | ISO 22163 추가 | 내부심사 관리 프로세스(프로그램 관리·심사원 관리·경험환류) |
| 10.1 | shall | ISO 9001:2015 | 개선 — 일반 |
| 10.3 | shall | ISO 9001:2015 | 지속적 개선 |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-021 | audit | major | 심사 프로그램은 모든 필수 프로세스를 3년 내 최소 1회 포함 | 9.2.3.1, 9.2.3.2 |
| CTL-022 | invariant | major | 심사원은 자신의 업무(소속 프로세스)를 심사할 수 없음 | 9.2.2, 9.2.3.1, 9.2.3.2 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-DOC 문서 유효성 준수율 | PI | 유효기간 내 승인 문서 수 / 전체 유효 문서 수 x 100 | 98.0% | quarterly | 품질보증 책임자 | 품질보증 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 승인된 심사 프로그램 | `audit_programme` (조건: `approved_on IS NOT NULL`) |
| 심사 보고서 | `internal_audit` (조건: `report_doc_id IS NOT NULL`) |
| 개선 기록 | `improvement` |
| 교훈·good practice | `lesson_learned` |
| 경영검토 기록 | `management_review` |

## 7. 프로세스 검토 (9.4)

본 프로세스는 24개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 7.1.6
python -m rqms matrix process
python -m rqms check
```
