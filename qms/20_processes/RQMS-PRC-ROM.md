# ROM — 리스크 및 기회 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-ROM |
| 영문명 | Risk and opportunity management process |
| 근거 조항 | ISO 22163:2023 6.1.3.1 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 품질보증 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.risk` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 6.1.3.1 의 요구사항을 충족하기 위해 리스크 및 기회 관리 프로세스를 수립·실행·유지한다.

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
| 4.1 | shall | ISO 9001:2015 | 조직과 그 상황의 이해 |
| 4.1.1.1 | shall | ISO 22163 추가 | 사업계획 수립 및 연간 검토 |
| 4.1.1.2 | should | ISO 22163 추가 | 사업계획 추가 고려사항 |
| 4.1.2 | should | ISO 22163 추가 | 사회적 책임 |
| 4.2 | shall | ISO 9001:2015 | 이해관계자의 니즈와 기대 이해 |
| 6.1.1 | shall | ISO 9001:2015 | 리스크와 기회의 결정 |
| 6.1.2 | shall | ISO 9001:2015 | 리스크와 기회에 대한 조치 기획 |
| 6.1.3.1 | shall | ISO 22163 추가 | 리스크 및 기회 관리 프로세스 |
| 6.1.3.2 | should | ISO 22163 추가 | 고객·외부공급자 참여 및 다기능 리스크 검토 |
| 6.1.4 | shall | ISO 22163 추가 | 사업연속성 |
| 8.1.3.9.1 | shall | ISO 22163 추가 | 프로젝트 리스크·기회 등록부(비용편익 분석 포함) |
| 8.1.3.9.2 | should | ISO 22163 추가 | 라인관리자 참여·운용성숙도 고려·기회 관리 |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-034 | audit | major | 사업연속성 계획 수립·검증 및 연간 검토 | 6.1.4 |
| CTL-036 | audit | major | 요약 사업계획 문서화 및 연간 검토 | 4.1.1.1 |
| CTL-042 | audit | major | 리스크·기회의 정기 검토 및 조치 효과성 평가 수행 | 6.1.3.1, 8.1.3.9.1 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-QDC 품질실패비용률 | KPI | (폐기+재작업+수리+변경+지체상금+추가보증비) / 매출액 x 100 | 1.5% | monthly | top_management, process_owners | 품질보증 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 사업연속성 계획 | `governance_record` (조건: `kind = 'business_continuity_plan'`) |
| 요약 사업계획 | `governance_record` (조건: `kind = 'business_plan'`) |
| 내·외부 이슈 등록부 | `context_entry` (조건: `kind = 'issue'`) |
| 이해관계자 등록부 | `context_entry` (조건: `kind = 'interested_party'`) |
| 리스크 조치 | `risk_entry` (조건: `TRIM(action) != ''`) |
| 리스크·기회 등록부 | `risk_entry` |
| 리스크 검토 기록 | `risk_entry` (조건: `reviewed_on IS NOT NULL`) |
| 사회적 책임 선언 | `governance_record` (조건: `kind = 'social_responsibility'`) |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 4.1
python -m rqms matrix process
python -m rqms check
```
