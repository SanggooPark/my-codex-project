# PSP — 생산 및 서비스 제공 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-PSP |
| 영문명 | Process for production and service provision |
| 근거 조항 | ISO 22163:2023 8.5.1.1.1 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 생산 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | SPP |
| 구현 모듈 | `rqms.services.production` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.5.1.1.1 의 요구사항을 충족하기 위해 생산 및 서비스 제공 프로세스를 수립·실행·유지한다.

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
| 7.1.3 | shall | ISO 9001:2015 | 기반구조 |
| 7.1.4 | shall | ISO 9001:2015 | 프로세스 운영 환경 |
| 8.1 | shall | ISO 9001:2015 | 운용 기획 및 관리 |
| 8.3.3.1.2 | should | ISO 22163 추가 | 생산·routine test 요구사항 및 보존 요구사항 고려 |
| 8.3.5.1.1 | shall | ISO 22163 추가 | 출력의 출시 전 검증·승인, 생산입력 대비 검증, 관련 문서·교육 포함 |
| 8.5.1 | shall | ISO 9001:2015 | 생산 및 서비스 제공의 관리 |
| 8.5.1.1.1 | shall | ISO 22163 추가 | 생산 및 서비스 제공 프로세스 |
| 8.5.1.1.2 | shall | ISO 22163 추가 | 관리된 조건(승인된 생산데이터·전 교대 감시·리스크평가·재작업 통제) |
| 8.5.1.1.3 | shall | ISO 22163 추가 | 생산공정 검증(설계출력 대비 입력 완전성·설비능력·공정FMEA) |
| 8.5.1.1.4.1 | shall | ISO 22163 추가 | 생산공정 유효성확인(FAI 완료·고객 인계 전 완료·변경 시 재확인) |
| 8.5.1.1.4.2 | should | ISO 22163 추가 | 측정능력·공정능력 연구 및 공차 분석 |
| 8.5.1.2.1 | shall | ISO 22163 추가 | 생산 일정계획(단·중·장기, 소프트웨어 지원, 애로공정 식별) |
| 8.5.1.2.2 | should | ISO 22163 추가 | 리스크분석·과거경험·효율 측정 고려 및 개선계획 |
| 8.5.1.4.1 | shall | ISO 22163 추가 | 생산설비 관리(예방정비·검증·최초사용 전 유효성확인·개별식별·주기점검) |
| 8.5.1.4.2 | should | ISO 22163 추가 | 생산설비에 설계개발 프로세스 적용 및 예측정비 |
| 8.5.2 | shall | ISO 9001:2015 | 식별 및 추적성 |
| 8.5.2.1 | shall | ISO 22163 추가 | 보증종료까지 추적성 유지, 상태불명 제품은 부적합품 처리 |
| 8.5.3 | shall | ISO 9001:2015 | 고객 또는 외부공급자의 소유물 |
| 8.5.3.1 | shall | ISO 22163 추가 | 소유물의 인도/반환 시점까지 추적성 관리 |
| 8.5.4 | shall | ISO 9001:2015 | 보존 |
| 8.5.4.1 | shall | ISO 22163 추가 | 보존 규격 문서화(표시·취급·청정·유효기간·환경조건) |
| 8.5.6 | shall | ISO 9001:2015 | 변경의 관리(생산·서비스 제공) |
| 8.9.3 | shall | ISO 22163 추가 | FAI 적용 대상(내부제품·EPPPS, 신제품/중대변경 후 대표품) |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-009 | invariant | major | 설계 출력은 검증·승인 후에만 출시 | 8.3.5, 8.3.5.1.1 |
| CTL-015 | invariant | major | 식별 또는 상태가 불명한 품목은 부적합품으로 처리 | 8.5.2.1 |
| CTL-016 | invariant | major | FAI 승인 전 양산 출시·공정 유효성확인 완료 금지 | 8.4.2.1.1, 8.5.1.1.4.1, 8.9.1, 8.9.3 |
| CTL-027 | invariant | major | 변경은 영향분석·승인 후에만 실행하며 실행 후 검증 필수 | 6.3, 8.1.4.2, 8.2.4, 8.3.6, 8.5.6 |
| CTL-032 | audit | major | 추적성 요구 품목은 보증종료 시점까지 추적성 유지 | 8.5.2, 8.5.2.1 |
| CTL-050 | invariant | major | 승인된 생산데이터가 없으면 생산 착수 금지(관리된 조건) | 8.5.1.1.2, 8.5.1.1.3, 8.5.1.2.1 |
| CTL-051 | audit | major | 생산설비 개별식별·예방정비·최초 사용 전 유효성확인 및 주기 재검증 | 8.5.1.4.1 |
| CTL-052 | audit | minor | 보존 규격 문서화 및 고객·공급자 소유물 추적성 관리 | 8.5.3.1, 8.5.4.1 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-COTD 고객 납기준수율 | KPI | 적시 인도된 고객 인도물 수 / 전체 계약 고객 인도물 수 x 100 | 95.0% | monthly | top_management, process_owners | 운영 총괄 |
| PI-INC 내부 부적합률(RFT) | PI | 최종검사 합격 수량 / 최종검사 대상 수량 x 100 | 98.0% | monthly | 생산 책임자, process_owners | 생산 책임자 |
| PI-CAP 생산능력 가동률(예측 포함) | PI | 계획 부하 / 가용 생산능력 x 100 | 90.0% | monthly | 운영 총괄 | 생산 책임자 |
| PI-EQDT 생산설비 비가동률 | PI | 비가동 시간 / 계획 가동시간 x 100 | 3.0% | monthly | 생산 책임자 | 설비 정비 관리자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 변경요청 | `change_request` |
| 고객·공급자 소유물 등록부 | `external_property` |
| 설계 입력 | `design` (조건: `inputs_complete = 1`) |
| 설계 출력 | `design` (조건: `output_released_on IS NOT NULL`) |
| 설비 등록부 | `production_equipment` |
| FAI 기록 | `fai` |
| 검사·시험 기록 | `inspection` |
| 설비 정비 기록 | `equipment_maintenance` |
| 기준생산계획 | `production_order` (조건: `scheduled_start_on IS NOT NULL`) |
| 운용 계획(생산 오더) | `production_order` |
| 보존 규격 | `preservation_spec` |
| 생산공정 유효성확인 | `production_order` (조건: `process_validated_on IS NOT NULL`) |
| 생산공정 검증 | `production_order` (조건: `process_verified_on IS NOT NULL`) |
| 승인된 생산 데이터 | `production_order` (조건: `approved_data_doc_id IS NOT NULL`) |
| 생산 오더 | `production_order` |
| 추적성 기록 | `traceable_item` |
| 작업환경 기록 | `governance_record` (조건: `kind = 'work_environment'`) |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 7.1.3
python -m rqms matrix process
python -m rqms check
```
