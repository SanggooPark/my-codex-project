# SPP — 특수공정 관리 프로세스

> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서 생성합니다.
> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.

| 항목 | 내용 |
| --- | --- |
| 문서번호 | RQMS-PRC-SPP |
| 영문명 | Process for the management of special processes |
| 근거 조항 | ISO 22163:2023 8.5.1.3 |
| 구분 | 필수 프로세스 (Annex A.1) |
| 프로세스 오너 | 생산 책임자 (5.3.1 b, 5.3.2) |
| 상위 프로세스 | PSP |
| 하위 프로세스 | 없음 |
| 구현 모듈 | `rqms.services.special_processes` |
| 프로세스 검토 주기 | 12개월 (9.4) |

## 1. 목적 및 적용범위

본 프로세스는 ISO 22163:2023 8.5.1.3 의 요구사항을 충족하기 위해 특수공정 관리 프로세스를 수립·실행·유지한다.

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
| 8.4.3.1 | shall | ISO 22163 추가 | 요구사항 전개·개정 식별·특수공정 승인·제품 중요도·출입권 |
| 8.5.1.3 | shall | ISO 22163 추가 | 특수공정 관리 프로세스(식별·표준·리스크평가·인원자격·공정자격) |

## 4. 강제 통제

| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |
| --- | --- | --- | --- | --- |
| CTL-014 | invariant | major | 특수공정은 공정자격·작업자 자격이 모두 유효한 경우에만 실행 | 8.5.1.3 |
| CTL-049 | audit | minor | 구매발주 확인서 수령 및 공급망 정보 최신 유지 | 8.4.3.1, 8.4.4 |

`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는 `python -m rqms check` 로 상태를 점검한다.

## 5. 성과지표 (4.4.1 c, 9.1.1.1)

| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |
| --- | --- | --- | --- | --- | --- | --- |
| PI-INC 내부 부적합률(RFT) | PI | 최종검사 합격 수량 / 최종검사 대상 수량 x 100 | 98.0% | monthly | 생산 책임자, process_owners | 생산 책임자 |
| PI-FAI FAI 일발 합격률 | PI | 무조건 승인 FAI 수 / 실시 FAI 수 x 100 | 80.0% | quarterly | 품질보증 책임자, 생산 책임자 | 품질보증 책임자 |

목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서 조치 필요성을 판단한다.

## 6. 문서화된 정보 (7.5)

| 증거 | 저장 위치 |
| --- | --- |
| 작업자 자격 | `special_process_operator` |
| 구매발주 | `purchase_order` |
| 특수공정 자격 | `special_process` (조건: `qualified_on IS NOT NULL`) |

## 7. 프로세스 검토 (9.4)

본 프로세스는 12개월 주기로 프로세스 오너가 주재하여 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review.hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게 보고되고 경영검토 입력이 된다(9.3.2.1 b).

## 8. 운영 명령

```bash
python -m rqms clause 8.4.3.1
python -m rqms matrix process
python -m rqms check
```
