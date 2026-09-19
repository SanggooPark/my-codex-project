# NCA — 부적합 및 시정조치 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-NCA |
| 영문명 | Process for managing nonconformities and corrective actions |
| 근거 조항 | ISO 22163:2023 10.2.3 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 품질보증 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | 없음 (최상위) |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.capa` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 10.2.3 의 요구사항을 충족하기 위해 부적합 및 시정조치 관리 프로세스를 수립·실행·유지한다.

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
| 8.7.3 | shall | ISO 22163 추가 | 부적합 출력 관리 프로세스(등록부·특채 등록부·만료·고객승인) |
| 9.1.2.1 | shall | ISO 22163 추가 | 고객 불만 관리(기록·공유·접수통보 및 시정조치 소통) |
| 9.1.3.1 | shall | ISO 22163 추가 | 전 데이터 분석·KPI 목표 미달 시 시정조치·추세 제시·이해관계자 공유 |
| 9.3.3.1 | shall | ISO 22163 추가 | 목표달성(품질·안전)·고객만족 관련 결정, 미달 시 시정조치 |
| 10.1 | shall | ISO 9001:2015 | 개선 — 일반 |
| 10.2.1 | shall | ISO 9001:2015 | 부적합 발생 시 대응·원인제거 필요성 평가·조치·효과성 검토 |
| 10.2.2 | shall | ISO 9001:2015 | 부적합의 성격·조치·시정조치 결과 문서화 |
| 10.2.3 | shall | ISO 22163 추가 | 부적합·시정조치 관리 프로세스(평가기준·문제해결기법·감시·에스컬레이션) |
| 10.3 | shall | ISO 9001:2015 | 지속적 개선 |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-018 | invariant | major | 특채의 유효기간 만료 또는 승인수량 초과 시 사용 금지 | 8.7.3 |
| CTL-019 | invariant | major | 고객승인 대상 특채는 인도 전 고객승인 필수, 공급자 특채는 내부승인 선행 | 8.7.3 |
| CTL-020 | invariant | major | KPI 목표 미달 시 시정조치 등록 필수 | 9.1.3.1, 9.3.3.1 |
| CTL-033 | invariant | major | 부적합의 시정조치 필요성 평가 및 에스컬레이션 기준 적용 | 10.2.1, 10.2.3 |
| CTL-053 | invariant | major | 고객 불만은 접수 통보 및 시정조치 연계 관리 | 9.1.2.1 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-CNC 고객 제기 부적합률 | KPI | 고객 클레임 수량 / 인도 수량 x 1000000 (ppm) | 500.0ppm | monthly | top_management, process_owners | 품질보증 책임자 |
| PI-QDC 품질실패비용률 | KPI | (폐기+재작업+수리+변경+지체상금+추가보증비) / 매출액 x 100 | 1.5% | monthly | top_management, process_owners | 품질보증 책임자 |
| PI-NCRT 고객 부적합·불만 응답시간 | PI | 고객 제기 건의 접수~1차 회신 소요시간 평균 | 24.0시간 | monthly | 품질보증 책임자, 영업 책임자 | 품질보증 책임자 |
| PI-RESOL 문제 해결 소요시간 | PI | 종결 건의 개시~종결 소요일수 평균 | 30.0일 | monthly | top_management, process_owners | 품질보증 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 지표 분석 기록 | `indicator_measurement` (조건: `TRIM(analysis) != ''`) |
| 고객 불만 기록 | `complaint` |
| 특채 등록부 | `concession` |
| 시정조치 기록 | `capa` |
| 개선 기록 | `improvement` |
| 경영검토 기록 | `management_review` |
| 부적합 등록부 | `nonconformity` |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.7.3
python -m rqms matrix process
python -m rqms check
```
