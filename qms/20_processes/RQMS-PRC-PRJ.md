# PRJ — 프로젝트 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-PRJ |
| 영문명 | Project management process |
| 근거 조항 | ISO 22163:2023 8.1.3.1.1 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 사업관리(PMO) 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.projects` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.1.3.1.1 의 요구사항을 충족하기 위해 프로젝트 관리 프로세스를 수립·실행·유지한다.

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
| 8.1 | shall | ISO 9001:2015 | 운용 기획 및 관리 |
| 8.1.3.1.1 | shall | ISO 22163 추가 | 프로젝트 관리 프로세스(단계·게이트·마일스톤·미결사항) |
| 8.1.3.1.2 | should | ISO 22163 추가 | 에스컬레이션·SWOT 검토·프로젝트 종료 교훈 |
| 8.1.3.1.3 | shall | ISO 22163 추가 | 프로젝트 문서화된 정보 및 단계검토(미결사항 종결 요건) |
| 8.1.3.2 | shall | ISO 22163 추가 | 프로젝트 관리계획서 |
| 8.1.3.3 | shall | ISO 22163 추가 | 프로젝트 범위 관리(WBS·작업패키지·승인 없는 범위변경 금지) |
| 8.1.3.4 | shall | ISO 22163 추가 | 프로젝트 일정 관리(주공정·고객 인도일 변경 통제) |
| 8.1.3.5 | shall | ISO 22163 추가 | 프로젝트 원가 관리(원가계정구조·EAC·예산 증액 통제) |
| 8.1.3.6 | shall | ISO 22163 추가 | 프로젝트 품질계획서 |
| 8.1.3.7 | shall | ISO 22163 추가 | 프로젝트 인적자원 관리 및 인력계획서 |
| 8.1.3.8 | shall | ISO 22163 추가 | 프로젝트 의사소통 관리 및 의사소통계획서 |
| 8.1.3.9.1 | shall | ISO 22163 추가 | 프로젝트 리스크·기회 등록부(비용편익 분석 포함) |
| 8.1.3.9.2 | should | ISO 22163 추가 | 라인관리자 참여·운용성숙도 고려·기회 관리 |
| 8.1.3.10 | shall | ISO 22163 추가 | 프로젝트 조달 관리(8.4 요구사항 적용) |
| 8.1.3.11 | shall | ISO 22163 추가 | 프로젝트 검토 관리(정기 진도검토·이탈 대책) |
| 8.2.1.1 | shall | ISO 22163 추가 | 불가피한 지연 발생 시 고객 통보 |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-004 | invariant | major | 이전 단계검토의 미결사항 미종결 시 단계검토 통과 금지(최고경영자 승인 시 예외) | 8.1.3.1.1, 8.1.3.1.3 |
| CTL-005 | invariant | major | 프로젝트 범위·일정·예산 변경은 승인된 변경요청에 의해서만 가능 | 8.1.3.3, 8.1.3.4, 8.1.3.5 |
| CTL-011 | invariant | major | EPPPS는 승인된 외부공급자에게만 발주 | 8.4.1.1.1, 8.4.1.1.4, 8.1.3.10 |
| CTL-028 | invariant | major | 고객·외부공급자 요구사항에 영향을 주는 변경 및 불가피한 지연은 통보·합의 필요 | 8.1.4.2, 8.2.1.1 |
| CTL-042 | audit | major | 리스크·기회의 정기 검토 및 조치 효과성 평가 수행 | 6.1.3.1, 8.1.3.9.1 |
| CTL-044 | audit | major | 프로젝트는 관리계획서·품질계획서·인력계획서·의사소통계획서를 보유 | 8.1.3.2, 8.1.3.6, 8.1.3.7, 8.1.3.8 |
| CTL-045 | audit | minor | 진행 중 프로젝트의 정기 프로젝트 검토 실시 | 8.1.3.11 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-CSAT 고객만족도 | KPI | 고객만족 설문 핵심문항 점수 평균 (0~100 환산) | 85.0점 | semiannual | top_management, 영업 책임자, process_owners | 영업 책임자 |
| PI-COTD 고객 납기준수율 | KPI | 적시 인도된 고객 인도물 수 / 전체 계약 고객 인도물 수 x 100 | 95.0% | monthly | top_management, process_owners | 운영 총괄 |
| PI-PC 프로젝트 원가 편차 | KPI | 실제 매출총이익률 - 입찰 시 계획 매출총이익률 (%p) | 0.0%p | monthly | top_management, 사업관리(PMO) 책임자 | 사업관리(PMO) 책임자 |
| PI-RESOL 문제 해결 소요시간 | PI | 종결 건의 개시~종결 소요일수 평균 | 30.0일 | monthly | top_management, process_owners | 품질보증 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 고객 의사소통 기록 | `communication_entry` (조건: `kind = 'record'`) |
| 게이트 체크리스트 | `phase_review` (조건: `gate_checklist_doc IS NOT NULL`) |
| 교훈·good practice | `lesson_learned` |
| 운용 계획(생산 오더) | `production_order` |
| 단계검토 기록 | `phase_review` (조건: `held_on IS NOT NULL`) |
| 프로젝트 의사소통 계획서 | `project_plan` (조건: `plan_kind = 'communication'`) |
| 프로젝트 원가 기록 | `project_cost` |
| 프로젝트 인력계획서 | `project_plan` (조건: `plan_kind = 'hr'`) |
| 프로젝트 관리계획서 | `project_plan` (조건: `plan_kind = 'management'`) |
| 프로젝트 품질계획서 | `project_plan` (조건: `plan_kind = 'quality'`) |
| 프로젝트 기록 | `project` |
| 프로젝트 검토 기록 | `project_review` |
| 프로젝트 일정(주공정) | `project` (조건: `TRIM(critical_path) != ''`) |
| 구매발주 | `purchase_order` |
| 리스크·기회 등록부 | `risk_entry` |
| 작업분할구조 | `work_package` |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.1
python -m rqms matrix process
python -m rqms check
```
