"""액션(입력 폼) 레지스트리.

화면의 모든 입력은 `rqms.services.*` 의 업무 함수로 들어간다. 이 모듈은 그 함수의
시그니처를 읽어 폼 필드를 자동 생성하고, 이름만으로는 알 수 없는 정보(한글 라벨,
선택지, 참조 대상 테이블, 사전(dict) 키)를 보강한다.

서비스 함수의 인자가 바뀌면 폼도 따라 바뀌므로 화면과 업무 로직이 어긋나지 않는다.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..db import Database
from ..services import (
    audit,
    calibration,
    capa,
    change,
    competence,
    configuration,
    customer,
    design,
    documents,
    fai,
    governance,
    indicators,
    nonconformity,
    obsolescence,
    post_delivery,
    production,
    projects,
    rams,
    release,
    requirements,
    review,
    risk,
    special_processes,
    suppliers,
    support,
    tender,
    transfer,
)
from ..standard import load_registry

# --------------------------------------------------------------------- 참조 대상
#: 참조(select) 필드의 원천. (테이블, 값 컬럼, 표시 SQL 식, 조건)
REF_SOURCES: dict[str, tuple[str, str, str, str]] = {
    "person": ("person", "id", "name || ' · ' || role", "active = 1"),
    "document": (
        "document",
        "id",
        "doc_no || ' v' || version || ' — ' || title",
        "status = 'approved'",
    ),
    "fai": ("fai", "id", "fai_no || ' — ' || target_ref", ""),
    "capa": ("capa", "id", "capa_no || ' — ' || description", ""),
    "capa_no": ("capa", "capa_no", "capa_no || ' — ' || description", ""),
    "baseline": ("baseline", "id", "name || ' (' || kind || ')'", ""),
    "concession": (
        "concession",
        "id",
        "concession_no || ' — ' || description",
        "status = 'open'",
    ),
    "measuring_resource": (
        "measuring_resource",
        "id",
        "ident || ' — ' || resource_type",
        "",
    ),
    "measuring_resource_ident": ("measuring_resource", "ident", "ident || ' — ' || name", ""),
    "equipment_ident": ("production_equipment", "ident", "ident || ' — ' || name", ""),
    "quality_objective": ("quality_objective", "id", "code || ' — ' || description", ""),
    "rams_objective": ("rams_objective", "id", "product || ' / ' || metric", ""),
    "risk_entry": ("risk_entry", "id", "ref_no || ' — ' || description", ""),
    "obsolescence_risk": ("obsolescence_risk", "id", "part_no || ' — ' || product", ""),
    "requirement": ("requirement", "id", "req_no || ' — ' || text", ""),
    "design_test": ("design_test", "id", "kind || ' #' || id", ""),
    "competence_gap": ("competence_gap", "id", "competence_code || ' #' || id", "closed_on IS NULL"),
    "open_issue": ("open_issue", "id", "description", "closed_on IS NULL"),
    "work_package": ("work_package", "id", "wbs_code || ' — ' || name", ""),
    "governance_record": ("governance_record", "id", "kind || ' ' || COALESCE(ref_year, '')", ""),
    "calibration_record": (
        "calibration_record",
        "id",
        "'교정 #' || id || ' (' || performed_on || ')'",
        "",
    ),
    "supplier_code": ("supplier", "code", "code || ' — ' || name", ""),
    "project_code": ("project", "code", "code || ' — ' || name", ""),
    "special_process_code": ("special_process", "code", "code || ' — ' || name", ""),
    "nc_no": ("nonconformity", "nc_no", "nc_no || ' — ' || description", ""),
    "change_no": ("change_request", "change_no", "change_no || ' — ' || description", ""),
    "po_no": ("purchase_order", "po_no", "po_no || ' — ' || item", ""),
    "order_no": ("production_order", "order_no", "order_no || ' — ' || item", ""),
    "serial_no": ("traceable_item", "serial_no", "serial_no || ' (' || status || ')'", ""),
    "design_no": ("design", "design_no", "design_no || ' — ' || item", ""),
    "tender_no": ("tender", "tender_no", "tender_no || ' — ' || title", ""),
    "audit_no": ("internal_audit", "audit_no", "audit_no || ' — ' || scope", ""),
    "fai_no": ("fai", "fai_no", "fai_no || ' — ' || target_ref", ""),
    "complaint_no": ("complaint", "complaint_no", "complaint_no || ' — ' || customer", ""),
    "concession_no": ("concession", "concession_no", "concession_no || ' — ' || description", ""),
    "transfer_no": ("process_transfer", "transfer_no", "transfer_no || ' — ' || process_code", ""),
    "baseline_name": ("baseline", "name", "name || ' (' || kind || ')'", ""),
    "config_part_no": ("config_item", "part_no", "part_no || ' — ' || name", ""),
    "external_property_ref": (
        "external_property",
        "ref_no",
        "ref_no || ' — ' || description",
        "",
    ),
}

#: 레지스트리(표준 데이터)에서 선택지를 가져오는 참조
REGISTRY_REFS = {"process_code", "indicator_code", "clause_id"}

#: 파라미터 이름 -> 참조 원천. 모듈별로 뜻이 다른 이름은 액션에서 개별 지정한다.
NAME_TO_REF: dict[str, str] = {
    "person_id": "person",
    "owner_id": "person",
    "approver_id": "person",
    "author_id": "person",
    "verifier_id": "person",
    "actor_id": "person",
    "responsible_id": "person",
    "inspector_id": "person",
    "custodian_id": "person",
    "performed_by_id": "person",
    "released_by_id": "person",
    "authorized_by_id": "person",
    "decided_by_id": "person",
    "lead_auditor_id": "person",
    "approved_by_id": "person",
    "disposition_authority_id": "person",
    "authority_id": "person",
    "action_owner_id": "person",
    "top_management_override_by": "person",
    "doc_id": "document",
    "plan_doc_id": "document",
    "itp_doc_id": "document",
    "approved_data_doc_id": "document",
    "report_doc_id": "document",
    "technical_doc_id": "document",
    "repair_instruction_doc_id": "document",
    "application_doc_id": "document",
    "safety_case_doc_id": "document",
    "gate_checklist_doc": "document",
    "description_doc": "document",
    "work_instruction_doc_id": "document",
    "fai_id": "fai",
    "capa_id": "capa",
    "capa_no": "capa_no",
    "baseline_id": "baseline",
    "concession_id": "concession",
    "measuring_resource_id": "measuring_resource",
    "req_id": "requirement",
    "test_id": "design_test",
    "gap_id": "competence_gap",
    "issue_id": "open_issue",
    "work_package_id": "work_package",
    "calibration_record_id": "calibration_record",
    "supplier_code": "supplier_code",
    "project_code": "project_code",
    "nc_no": "nc_no",
    "change_no": "change_no",
    "po_no": "po_no",
    "order_no": "order_no",
    "serial_no": "serial_no",
    "design_no": "design_no",
    "tender_no": "tender_no",
    "audit_no": "audit_no",
    "fai_no": "fai_no",
    "complaint_no": "complaint_no",
    "concession_no": "concession_no",
    "transfer_no": "transfer_no",
    "baseline_name": "baseline_name",
    "config_part_no": "config_part_no",
    "process_code": "process_code",
    "indicator_code": "indicator_code",
    "clause_id": "clause_id",
}

#: 파라미터 이름 -> 한글 라벨
LABELS: dict[str, str] = {
    "acceptance_criteria": "합격기준",
    "achieved": "달성 여부",
    "action": "조치 내용",
    "action_owner_id": "조치 책임자",
    "action_plan": "조치 계획",
    "actor_id": "처리자",
    "actual": "실적",
    "actual_data": "실측 데이터",
    "actual_margin_pct": "실제 매출총이익률(%)",
    "actual_participants": "실제 참석자",
    "activity_kind": "활동 유형",
    "affected_serials": "대상 일련번호",
    "agreed": "고객 합의됨",
    "ambient_suitable": "주위조건 적합",
    "analysis": "분석 내용",
    "applicable_standard": "적용 표준",
    "applicable_standards": "적용 안전표준",
    "application_doc_id": "적용 문서(매뉴얼 등)",
    "approval_method": "승인 방법",
    "approval_scope": "승인 범위",
    "approved_data_doc_id": "승인된 생산 데이터",
    "approver_id": "승인자",
    "architecture_level": "아키텍처 계층",
    "attendees": "참석자",
    "audit_criteria": "심사 기준",
    "audit_no": "심사 번호",
    "audits_performed": "수행 심사 건수",
    "author_id": "작성자",
    "authority_id": "결정 권한자",
    "authorized_by_id": "출하 승인자",
    "baseline_id": "형상 기준선",
    "baseline_name": "형상 기준선명",
    "benefit_note": "기대 효과",
    "budget": "예산",
    "business_env_change": "사업환경 변화",
    "calculated": "산정값",
    "calculated_at_stage": "산정 단계",
    "capa_id": "시정조치",
    "capa_no": "시정조치 번호",
    "cascaded": "하위 전개 완료",
    "cause_analysis": "원인분석",
    "certifications": "보유 인증",
    "change_no": "변경 번호",
    "cleaning": "청정·오염관리",
    "clause_id": "조항",
    "close": "종결 처리",
    "code": "코드",
    "communicated_to": "전달 대상",
    "communicator": "전달 주체",
    "competence_code": "역량 코드",
    "complaint_no": "불만 번호",
    "component": "부품",
    "concession_id": "특채",
    "concession_no": "특채 번호",
    "conditions": "시험 조건",
    "confidentiality": "기밀등급",
    "config_part_no": "형상항목 품번",
    "conflicts_resolved": "상충 입력 해결됨",
    "conformity_evidence": "적합성 증거",
    "consignment_stock": "위탁재고",
    "content": "본문",
    "control_extent": "통제의 유형과 정도",
    "control_measure": "통제 수단",
    "controlled_conditions_met": "관리된 조건 달성",
    "core_team_present": "핵심팀 참석",
    "cost": "비용",
    "cost_account": "원가계정",
    "cost_benefit": "비용편익 분석",
    "countermeasure": "대책",
    "countermeasures": "대책",
    "covers": "포함 항목",
    "criteria": "판정기준",
    "criteria_applied": "적용 기준",
    "criteria_knowledge": "심사기준 지식",
    "criteria_met": "합격기준 충족",
    "criteria_note": "분류 기준",
    "criticality": "제품 중요도",
    "critical_path": "주공정",
    "custodian_id": "관리 담당자",
    "customer": "고객",
    "customer_approval_required": "고객승인 필요",
    "customer_delivery_on": "고객 인도일",
    "customer_impact": "고객 요구사항 영향",
    "customer_informed": "고객 통보함",
    "decided_by_id": "결정권자",
    "decision": "결정",
    "decision_authority_present": "의사결정 권한자 참석",
    "delegated": "위임 검증",
    "deliverable_cost_plan": "인도물 원가 계획",
    "department": "부서",
    "description": "내용",
    "description_doc": "프로세스 기술서",
    "design_feedback": "설계 환류",
    "design_input_complete": "설계 입력 완전성 확인",
    "design_no": "설계 번호",
    "design_requirements_met": "설계요구 충족",
    "detected_at_stage": "검출 단계",
    "development_plan": "개발 조치계획",
    "doc_id": "문서",
    "doc_no": "문서번호",
    "doc_type": "문서 유형",
    "downtime_hours": "비가동 시간",
    "due_on": "기한",
    "duration_days": "기간(일)",
    "effective": "효과적임",
    "effective_from": "발효일",
    "effectiveness_note": "조치 효과성 평가",
    "emp_no": "사번",
    "environment": "환경 조건",
    "equipment_capable": "설비 능력 확인",
    "escalation_level": "에스컬레이션 단계",
    "evaluation_method": "평가 방법",
    "evidence": "증거",
    "exclusions": "비적용 조항",
    "external": "외부 조직으로 이전",
    "fai_id": "FAI",
    "fai_no": "FAI 번호",
    "failure_category": "고장 분류",
    "failure_symptom": "고장 증상",
    "feasibility_study": "타당성 조사",
    "feedback_given": "공급자 피드백 제공",
    "feedback_to_design": "설계 환류",
    "feedback_to_provider": "외부공급자 환류",
    "feedback_to_rqms": "RQMS 환류",
    "field_value": "현장 실적값",
    "fields": "검토 항목",
    "finish_on": "종료일",
    "forecast": "예측",
    "from_failure": "고장에 기인",
    "from_site": "이전 전 사이트",
    "gap_id": "역량 갭",
    "gate_checklist_doc": "게이트 체크리스트",
    "grade": "등급",
    "hazard_log": "위험원 기록",
    "home_processes": "소속 프로세스(자기업무 심사 판정용)",
    "identification_agreed": "식별 방법 고객 합의",
    "identification_method": "식별 방법",
    "ident": "식별번호",
    "impact": "영향도(1~5)",
    "impact_analysis": "영향분석",
    "impact_on_delivered": "기납품 영향",
    "implementation_verified_on": "실행 검증일",
    "inputs": "입력",
    "inspector_id": "검사자",
    "interval_months": "교정 주기(개월)",
    "internal": "내부 교정",
    "is_good_practice": "good practice",
    "is_llru": "LLRU",
    "is_new_or_modified": "신규/변경 EPPPS",
    "is_first_run": "초도 생산",
    "is_tool": "치공구",
    "issue_id": "미결사항",
    "issue_kind": "이슈 유형",
    "item": "품목",
    "itp_doc_id": "검사·시험계획(ITP)",
    "kind": "구분",
    "knowledge_input": "조직 지식 입력",
    "knows_audit_principles": "심사원칙 지식 보유",
    "lead_auditor_id": "선임심사원",
    "lesson_shared": "교훈 공유",
    "level": "수준",
    "likelihood": "발생가능성(1~5)",
    "location": "설치 위치",
    "mandatory_participants": "필수 참석자",
    "marking": "표시·라벨",
    "measured_by_role": "측정 담당",
    "method": "방법",
    "mileage_km": "주행거리(km)",
    "min_level": "최소 역량 수준",
    "mitigation": "완화 조치",
    "monetary_risk_eval": "리스크 금액 평가",
    "multidisciplinary": "다기능 심사",
    "multi_site": "다중 사이트·컨소시엄",
    "name": "명칭",
    "nc_no": "부적합 번호",
    "new_budget": "변경 예산",
    "new_date": "변경 인도일",
    "new_revision": "신규 개정번호",
    "new_technology": "신기술 적용",
    "new_text": "변경 후 내용",
    "new_version": "신규 판번호",
    "note": "비고",
    "objectives": "시험 목적",
    "occurred_on": "발생일",
    "on": "일자",
    "on_critical_path": "주공정 포함",
    "operating_hours": "가동시간",
    "operator_ids": "특수공정 작업자",
    "operational_maturity": "운용 성숙도",
    "order_no": "생산오더 번호",
    "origin": "출처",
    "outputs": "출력",
    "owner_id": "담당자",
    "owner_kind": "소유자 구분",
    "owner_name": "소유자",
    "owner_ref": "대상 참조",
    "owner_scope": "대상 구분",
    "parent_part_no": "상위 품번",
    "part_no": "품번",
    "part_numbers": "포함 형상항목 품번",
    "participants": "참석자",
    "people_infrastructure_processes": "인원·기반구조·프로세스 평가",
    "performance": "성과(계획 대비 실적)",
    "performed_by_id": "실시자",
    "period": "기간",
    "perspective": "관점",
    "phase": "단계",
    "plan_doc_id": "계획 문서",
    "plan_kind": "계획서 종류",
    "planned_extent": "검사 범위",
    "planned_margin_pct": "계획 매출총이익률(%)",
    "planned_on": "계획일",
    "po_no": "발주 번호",
    "predecessors": "선행 작업",
    "preventive_plan": "예방정비 계획",
    "priority": "우선순위",
    "problem_solving_method": "문제해결 기법",
    "procedure_ref": "교정 절차",
    "process_code": "프로세스",
    "process_fmea": "공정 FMEA",
    "process_review_done": "생산공정 검토 완료",
    "product": "제품",
    "product_under_test": "시험 대상품",
    "production_input_verified": "생산 입력 대비 검증",
    "products_services": "대상 제품·서비스",
    "project_code": "프로젝트",
    "proposal_verified": "제안 변경 검증",
    "protection_measure": "보호 조치",
    "purpose": "용도",
    "qty": "수량",
    "qty_authorized": "승인 수량",
    "qualified_until": "자격 유효기한",
    "quality_or_safety_relevant": "품질·안전 관련",
    "ranking": "등급",
    "reason": "사유",
    "recorded_parameters": "기록 파라미터",
    "recorded_on_doc": "적합성 선언서 기재",
    "record_type": "기록 유형",
    "ref": "참조",
    "ref_no": "관리번호",
    "ref_year": "연도",
    "repair_cost": "수리 비용",
    "repair_instruction_doc_id": "수리 지침",
    "repeated": "반복 발생",
    "report_doc_id": "보고서 문서",
    "reported_to": "보고 대상",
    "reported_to_top_management": "최고경영자 보고",
    "representative_serial": "대표 시료",
    "requirement": "요구사항",
    "requirement_owner_ref": "요구사항 대상 참조",
    "requirements_communicated": "전달 요구사항",
    "requirements_text": "위임 요구사항",
    "required_on": "요구 납기",
    "resource_id": "측정자원",
    "resource_note": "종결 자원",
    "resource_plan": "자원 계획",
    "resource_type": "자원 유형",
    "resources": "필요 자원",
    "responsibilities": "책임",
    "responsible_id": "책임자",
    "result": "결과",
    "retention_months": "보존기간(개월)",
    "revalidation_note": "재유효성확인 판단",
    "review_kind": "검토 구분",
    "risk_assessed": "리스크 평가 완료",
    "risk_assessment": "리스크 평가",
    "risk_criteria": "리스크기반 통제기준",
    "risk_entry_ref": "리스크 참조번호",
    "risk_level": "리스크 등급",
    "risk_status": "리스크 현황",
    "risk_updated": "리스크 갱신",
    "role": "직책",
    "root_cause": "근본원인",
    "safety_case_doc_id": "안전 케이스",
    "safety_impact": "안전 영향",
    "safety_related": "안전 관련",
    "score": "점수",
    "scope": "범위",
    "scope_knowledge": "심사범위 지식",
    "scope_ref": "대상 참조",
    "sequence_note": "순서 및 상호작용",
    "serial_no": "일련번호",
    "shared_with": "공유 대상",
    "shelf_life_control": "유효기간·재고 회전",
    "shift": "교대",
    "shifts_covered": "포함 교대",
    "sil_level": "SIL 등급",
    "similar_checked": "유사 부적합 확인",
    "six_m_covered": "6M 작업지침 항목",
    "source": "출처",
    "source_ref": "출처 참조",
    "source_type": "출처 구분",
    "spare_parts_secured": "예비품 확보",
    "special_handling": "특별 취급",
    "special_process_approval": "특수공정 승인",
    "special_process_codes": "특수공정 코드(쉼표 구분)",
    "stakeholders": "이해관계자",
    "start_on": "시작일",
    "statement": "선언 내용",
    "status": "상태",
    "strategy": "완화 전략",
    "submitted_on": "제출일",
    "supplier_acceptance_evidence": "공급자 동의 증거",
    "supplier_code": "외부공급자",
    "support_until": "지원 보장 시점",
    "target": "목표값",
    "target_kind": "대상 구분",
    "target_ref": "대상 참조",
    "target_value": "목표값",
    "targeted": "전략적 목표 공급자",
    "task_code": "업무 코드",
    "team": "심사팀(인원 ID, 쉼표 구분)",
    "technical": "기술 변경",
    "technical_doc_id": "기술 문서",
    "tender_no": "입찰 번호",
    "text": "요구사항 내용",
    "timing": "시점",
    "title": "제목",
    "to_site": "이전 후 사이트",
    "tool_program_list": "치공구·NC 프로그램 목록",
    "top_management_override_by": "최고경영자 승인(미결사항 예외)",
    "topic": "주제",
    "topics": "고려 항목",
    "traceability_method": "추적성 식별 방법",
    "traceability_required": "추적성 요구",
    "transfer_no": "이전 번호",
    "trend": "추세",
    "trigger": "실시 계기",
    "understanding_evidence": "교육 이해 증거",
    "unit": "단위",
    "used_in_special_process": "특수공정 사용",
    "valid_until": "유효기한",
    "validated_before_first_use": "최초 사용 전 유효성확인",
    "validation_method": "유효성확인 방법",
    "value": "측정값",
    "verifiable": "검증 가능",
    "verification_interval_months": "검증 주기(개월)",
    "verification_method": "검증 방법",
    "verified_on": "검증일",
    "version": "판번호",
    "warranty_months": "보증기간(개월)",
    "wbs_code": "WBS 코드",
    "wbs_level": "WBS 검토 수준",
    "won": "낙찰",
    "year": "연도",
}

#: 날짜로 입력받을 파라미터
DATE_FIELDS = {
    "due_on",
    "valid_until",
    "qualified_until",
    "planned_on",
    "start_on",
    "finish_on",
    "customer_delivery_on",
    "required_on",
    "occurred_on",
    "effective_from",
    "support_until",
    "new_date",
    "verified_on",
    "scheduled_start_on",
    "scheduled_finish_on",
    "on",
}

#: 여러 줄 입력이 자연스러운 파라미터
TEXTAREA_FIELDS = {
    "description",
    "analysis",
    "impact_analysis",
    "cause_analysis",
    "root_cause",
    "actions",
    "content",
    "text",
    "evidence",
    "risk_assessment",
    "feasibility_study",
    "action_plan",
    "criteria",
    "resources",
    "inputs",
    "outputs",
    "sequence_note",
    "risk_criteria",
    "performance",
    "forecast",
    "risk_status",
    "open_issue_followup",
    "countermeasures",
    "development_plan",
    "hazard_log",
    "mitigation",
    "feedback_to_rqms",
    "design_feedback",
    "effectiveness_note",
    "conformity_evidence",
    "acceptance_criteria",
    "requirements_text",
    "people_infrastructure_processes",
    "understanding_evidence",
    "statement",
    "benefit_note",
}

#: 선택지가 고정된 파라미터 (액션에서 덮어쓸 수 있다)
CHOICES: dict[str, tuple[str, ...]] = {
    "doc_type": tuple(documents.HIERARCHY),
    "confidentiality": documents.CONFIDENTIALITY,
    "req_type": requirements.REQ_TYPES,
    "operational_maturity": requirements.MATURITY,
    "owner_scope": ("tender", "project", "product"),
    "source": ("customer", "statutory", "organization", "market"),
    "origin": ("external", "internal"),
    "phase": projects.PHASES,
    "plan_kind": ("management", "quality", "hr", "communication", "configuration"),
    "architecture_level": design.LEVELS,
    "classification": suppliers.CLASSIFICATIONS,
    "criticality": ("standard", "safety_critical", "long_lead"),
    "disposition": nonconformity.DISPOSITIONS,
    "escalation_level": tuple(str(k) for k in capa.ESCALATION_TARGETS),
    "target_kind": fai.TARGET_KINDS,
    "trigger": fai.TRIGGERS,
    "metric": rams.METRICS,
    "calculated_at_stage": rams.STAGES,
    "direction": ("higher_is_better", "lower_is_better"),
    "issue_kind": obsolescence.ISSUE_KINDS,
    "strategy": obsolescence.STRATEGIES,
    "activity_kind": post_delivery.KINDS,
    "problem_solving_method": post_delivery.PROBLEM_SOLVING,
    "grade": audit.GRADES,
    "review_kind": ("annual", "extraordinary"),
    "owner_kind": ("customer", "external_provider"),
    "result": ("pass", "fail"),
    "level": ("organization", "process", "project"),
    "min_level": tuple(str(k) for k in competence.LEVELS),
    "priority": ("1", "2", "3", "4", "5"),
    "shift": ("day", "night", "swing"),
    "perspective": ("manufacturer", "operator", "system_integrator"),
}


@dataclass(frozen=True)
class Field:
    """폼 필드 1개."""

    name: str
    label: str
    widget: str  # text|textarea|number|date|bool|choice|ref|dict|pairs|list
    required: bool
    cast: str = "str"  # str|int|float|bool
    choices: tuple[str, ...] = ()
    ref: str | None = None
    dict_keys: tuple[str, ...] = ()
    help: str = ""


@dataclass(frozen=True)
class Action:
    """입력 화면 1개 = 서비스 함수 1개."""

    id: str
    label: str
    section: str
    clause: str
    func: Callable[..., Any]
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    note: str = ""
    #: 이 액션이 **새로 만드는** 식별자 파라미터. 기존 기록을 고르는 참조가 아니라
    #: 자유 입력이어야 한다(예: 부적합 등록의 nc_no).
    creates: tuple[str, ...] = ()

    @property
    def fields(self) -> tuple[Field, ...]:
        overrides = dict(self.overrides)
        for name in self.creates:
            merged = dict(overrides.get(name, {}))
            merged["ref"] = None
            merged.setdefault("widget", "text")
            overrides[name] = merged
        return build_fields(self.func, overrides)

    def call(self, db: Database, values: dict[str, Any]) -> Any:
        """서비스 함수를 호출한다 — 통제는 서비스 계층이 강제한다.

        위치인자 오정렬을 피하기 위해 모든 인자를 키워드로 전달한다
        (대상 함수의 위치 파라미터는 모두 POSITIONAL_OR_KEYWORD 이다).
        """
        known = set(inspect.signature(self.func).parameters)
        kwargs = {k: v for k, v in values.items() if k in known and k != "db"}
        return self.func(db, **kwargs)


def _annotation(param: inspect.Parameter) -> str:
    return "" if param.annotation is inspect.Parameter.empty else str(param.annotation)


def build_fields(
    func: Callable[..., Any], overrides: dict[str, dict[str, Any]] | None = None
) -> tuple[Field, ...]:
    """서비스 함수 시그니처에서 폼 필드를 만든다."""
    overrides = overrides or {}
    fields: list[Field] = []
    for name, param in inspect.signature(func).parameters.items():
        if name == "db":
            continue
        override = overrides.get(name, {})
        if override.get("skip"):
            continue
        ann = _annotation(param)
        optional = "None" in ann
        required = param.default is inspect.Parameter.empty and not optional

        cast = "str"
        widget = "text"
        if ann.startswith("bool") or ann == "bool":
            widget, cast = "bool", "bool"
        elif "int" in ann and "dict" not in ann and "list" not in ann:
            widget, cast = "number", "int"
        elif "float" in ann:
            widget, cast = "number", "float"
        elif ann.startswith("dict"):
            widget = "dict"
        elif ann.startswith("list"):
            widget = "list"

        ref = override.get("ref", NAME_TO_REF.get(name))
        if ref and widget in ("text", "number"):
            widget = "ref"
        if name in DATE_FIELDS and widget == "text":
            widget = "date"
        if name in TEXTAREA_FIELDS and widget == "text":
            widget = "textarea"

        choices = tuple(override.get("choices", CHOICES.get(name, ())))
        if choices:
            widget = "choice"
            cast = override.get("cast", cast)

        if override.get("widget"):
            widget = override["widget"]
        if widget == "pairs":
            cast = "str"

        fields.append(
            Field(
                name=name,
                label=override.get("label", LABELS.get(name, name)),
                widget=widget,
                required=override.get("required", required),
                cast=override.get("cast", cast),
                choices=choices,
                ref=ref if widget == "ref" else None,
                dict_keys=tuple(override.get("dict_keys", ())),
                help=override.get("help", ""),
            )
        )
    return tuple(fields)


def ref_options(db: Database, ref: str) -> list[tuple[str, str]]:
    """참조 필드의 선택지를 DB 또는 표준 레지스트리에서 읽는다."""
    if ref == "process_code":
        return [
            (p.code, f"{p.code} — {p.name_ko}") for p in load_registry().processes
        ]
    if ref == "indicator_code":
        return [
            (i.code, f"{i.code} — {i.title_ko}") for i in load_registry().indicators
        ]
    if ref == "clause_id":
        return [(c.id, f"{c.id} — {c.title_ko}") for c in load_registry().clauses]
    if ref == "special_process_code":
        rows = db.query("SELECT code, name FROM special_process ORDER BY code")
        return [(r["code"], f"{r['code']} — {r['name']}") for r in rows]

    source = REF_SOURCES.get(ref)
    if source is None:
        return []
    table, value_col, label_expr, where = source
    sql = f"SELECT {value_col} AS v, {label_expr} AS t FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += f" ORDER BY {value_col} LIMIT 500"
    try:
        rows = db.query(sql)
    except Exception:  # 테이블이 비었거나 컬럼이 없을 때도 화면은 떠야 한다.
        return []
    return [(str(r["v"]), str(r["t"])) for r in rows]


# --------------------------------------------------------------------- 섹션
@dataclass(frozen=True)
class Section:
    """좌측 내비게이션 한 항목 = 등록부 + 액션 묶음."""

    key: str
    title: str
    chapter: str
    clause: str
    registers: tuple[tuple[str, str], ...]  # (테이블, 표시명)


SECTIONS: tuple[Section, ...] = (
    Section("governance", "프로세스·거버넌스", "4~5장", "4.1~5.3", (
        ("process_instance", "프로세스 등록부"),
        ("governance_record", "거버넌스 기록(사업계획·방침·범위)"),
        ("context_entry", "상황·이해관계자 등록부"),
        ("stop_authority", "공정 정지 권한자"),
        ("process_training", "프로세스 교육 기록"),
    )),
    Section("risk", "리스크·목표·사업연속성", "6장", "6.1~6.3", (
        ("risk_entry", "리스크·기회 등록부"),
        ("quality_objective", "품질목표"),
    )),
    Section("documents", "문서화된 정보", "7.5", "7.5.1~7.5.3.3", (
        ("document", "문서 등록부"),
        ("document_event", "문서 이력"),
    )),
    Section("people", "인원·역량", "7.1~7.3", "7.1.2, 7.2", (
        ("person", "인원 명부"),
        ("competence_requirement", "필요역량 정의"),
        ("competence", "역량 보유 기록"),
        ("task_assignment", "업무 배정"),
        ("competence_gap", "역량 갭"),
    )),
    Section("calibration", "측정자원 교정", "7.1.5", "7.1.5.1~7.1.5.3", (
        ("measuring_resource", "측정자원 등록부"),
        ("calibration_record", "교정·검증 기록"),
    )),
    Section("support", "자원·지식·의사소통·혁신", "7.1/7.4/8.1.1.1", "7.1.1.1, 7.1.6, 7.4", (
        ("lesson_learned", "교훈·good practice"),
        ("communication_entry", "의사소통 계획·기록"),
        ("innovation", "혁신 등록부"),
    )),
    Section("tender", "입찰 관리", "8.1.2", "8.1.2", (
        ("tender", "입찰 등록부"),
    )),
    Section("requirements", "요구사항 관리", "8.2", "8.2.1~8.2.5", (
        ("requirement", "요구사항 등록부"),
    )),
    Section("projects", "프로젝트 관리", "8.1.3", "8.1.3.1~8.1.3.11", (
        ("project", "프로젝트 등록부"),
        ("project_plan", "프로젝트 계획서"),
        ("work_package", "작업분할구조"),
        ("phase_review", "단계검토(게이트)"),
        ("open_issue", "미결사항"),
        ("project_review", "프로젝트 검토"),
        ("project_cost", "프로젝트 원가"),
    )),
    Section("configuration", "형상관리", "8.1.4.1", "8.1.4.1", (
        ("config_item", "형상항목(PBS)"),
        ("baseline", "형상 기준선"),
        ("baseline_item", "기준선 구성"),
        ("config_status_record", "형상상태 기록"),
    )),
    Section("change", "변경관리", "8.1.4.2", "8.1.4.2", (
        ("change_request", "변경요청 등록부"),
    )),
    Section("transfer", "프로세스 이전", "8.1.1.2", "8.1.1.2", (
        ("process_transfer", "이전 등록부"),
    )),
    Section("design", "설계 및 개발", "8.3", "8.3.1~8.3.6", (
        ("design", "설계 등록부"),
        ("design_review", "설계검토 기록"),
        ("design_test", "검증·유효성확인 시험"),
    )),
    Section("suppliers", "외부공급 관리", "8.4", "8.4.1~8.4.4", (
        ("supplier", "승인 공급자 등록부"),
        ("purchase_order", "구매발주"),
        ("incoming_inspection", "인수검사"),
        ("eppps_release", "EPPPS 출시 승인"),
        ("verification_delegation", "검증 위임 등록부"),
    )),
    Section("production", "생산 및 서비스 제공", "8.5", "8.5.1~8.5.4", (
        ("production_order", "생산 오더"),
        ("traceable_item", "추적 품목"),
        ("inspection", "검사·시험 기록"),
        ("production_equipment", "생산설비"),
        ("equipment_maintenance", "설비 정비 기록"),
        ("external_property", "고객·공급자 소유물"),
        ("preservation_spec", "보존 규격"),
    )),
    Section("special_processes", "특수공정", "8.5.1.3", "8.5.1.3", (
        ("special_process", "특수공정 등록부"),
        ("special_process_operator", "작업자 자격"),
    )),
    Section("release", "출하 및 인도", "8.6", "8.6, 8.6.1", (
        ("release_record", "출하 기록"),
    )),
    Section("nonconformity", "부적합·특채", "8.7", "8.7.1~8.7.3", (
        ("nonconformity", "부적합 등록부"),
        ("concession", "특채 등록부"),
    )),
    Section("capa", "시정조치·개선", "10장", "10.1~10.3", (
        ("capa", "시정조치 등록부"),
        ("improvement", "개선 등록부"),
    )),
    Section("rams", "RAMS·안전·LCC", "8.8", "8.8.1~8.8.4", (
        ("rams_objective", "RAM 목표"),
        ("field_data", "현장 데이터"),
        ("safety_record", "안전 기록"),
        ("lcc_record", "LCC 기록"),
    )),
    Section("fai", "초도품 검사", "8.9", "8.9.1~8.9.3", (
        ("fai", "FAI 등록부"),
    )),
    Section("obsolescence", "단산 관리", "8.10", "8.10", (
        ("obsolescence_plan", "단산 관리계획"),
        ("obsolescence_risk", "단산 리스크"),
    )),
    Section("post_delivery", "인도 후 활동", "8.5.5", "8.5.5.1", (
        ("post_delivery_activity", "인도 후 활동 기록"),
    )),
    Section("indicators", "성과지표", "9.1.1", "9.1.1.1", (
        ("indicator_measurement", "지표 측정 기록"),
    )),
    Section("customer", "고객만족·불만", "9.1.2", "8.2.1, 9.1.2.1", (
        ("complaint", "고객 불만 등록부"),
        ("customer_satisfaction", "고객만족 측정"),
    )),
    Section("audit", "내부심사", "9.2", "9.2.1~9.2.3.3", (
        ("audit_programme", "심사 프로그램"),
        ("auditor", "심사원 명부"),
        ("internal_audit", "내부심사 등록부"),
        ("audit_finding", "심사 발견사항"),
    )),
    Section("review", "경영검토·프로세스 검토", "9.3~9.4", "9.3.1~9.4", (
        ("management_review", "경영검토 기록"),
        ("process_review", "프로세스 검토 기록"),
    )),
)

SECTION_BY_KEY = {s.key: s for s in SECTIONS}


def _a(
    action_id: str,
    label: str,
    section: str,
    clause: str,
    func: Callable[..., Any],
    overrides: dict[str, dict[str, Any]] | None = None,
    note: str = "",
    creates: tuple[str, ...] = (),
) -> Action:
    return Action(action_id, label, section, clause, func, overrides or {}, note, creates)


#: 사전(dict) 필드의 키 목록
_MR_INPUT_KEYS = review.MR_INPUTS_ISO9001 + review.MR_INPUTS_SUPPLEMENTAL

ACTIONS: tuple[Action, ...] = (
    # ------------------------------------------------------------ 4~5장 거버넌스
    _a("governance.register_process", "프로세스 등록·오너 임명", "governance",
       "4.4.1, 4.4.3, 5.3.1 b)", governance.register_process,
       {"code": {"ref": "process_code", "label": "프로세스"}},
       "4.4.1 a)~e) 와 리스크기반 통제기준이 모두 있어야 등록됩니다(CTL-038, CTL-039)."),
    _a("governance.record_process_training", "프로세스 교육 기록", "governance",
       "4.4.3 c), 7.2.1.1 d)", governance.record_process_training),
    _a("governance.exclude_process", "프로세스 비적용 선언", "governance", "4.3.1",
       governance.exclude_process, {"code": {"ref": "process_code", "label": "프로세스"}},
       "Annex A.1 필수 프로세스는 비적용으로 선언할 수 없습니다(CTL-037)."),
    _a("governance.record_business_plan", "요약 사업계획 등록", "governance", "4.1.1.1",
       governance.record_business_plan,
       {"topics": {"dict_keys": governance.BUSINESS_PLAN_TOPICS}},
       "4.1.1.1 a)~l) 항목을 모두 채워야 등록됩니다(CTL-036)."),
    _a("governance.record_scope", "RQMS 적용범위 등록", "governance", "4.3, 4.3.1",
       governance.record_scope,
       {"exclusions": {"widget": "pairs", "help": "한 줄에 '조항=정당화 사유' 형식"}},
       "정당화 사유 없는 비적용은 거부됩니다(CTL-037)."),
    _a("governance.record_quality_policy", "품질방침 등록", "governance", "5.2.1, 5.2.3",
       governance.record_quality_policy,
       {"topics": {"dict_keys": governance.POLICY_TOPICS}},
       "고장예방·고객기대·안전 측면을 모두 담아야 합니다(CTL-040)."),
    _a("governance.record_social_responsibility", "사회적 책임 선언", "governance", "4.1.2",
       governance.record_social_responsibility),
    _a("governance.record_context_issue", "내·외부 이슈 등록", "governance", "4.1",
       governance.record_context_issue),
    _a("governance.record_interested_party", "이해관계자 등록", "governance", "4.2",
       governance.record_interested_party),
    _a("governance.appoint_stop_authority", "공정 정지 권한자 임명", "governance", "5.3.1 d)",
       governance.appoint_stop_authority,
       {"independent_of": {"label": "독립 대상 조직(부서명)"}},
       "정지 대상 조직과 같은 소속은 임명할 수 없습니다(CTL-031)."),
    # ------------------------------------------------------------------ 6장 기획
    _a("risk.register", "리스크·기회 등록", "risk", "6.1.1, 6.1.2, 6.1.3.1", risk.register,
       {"kind": {"choices": ("risk", "opportunity")},
        "scope": {"choices": ("organization", "process", "project", "tender",
                              "supply_chain", "design", "production")},
        "method": {"choices": risk.METHODS}},
       f"등급(발생가능성×영향도) {risk.ACTION_THRESHOLD} 이상이면 조치·책임자·기한이 필수입니다."),
    _a("risk.review", "리스크 검토·종결", "risk", "6.1.3.1 b), e)", risk.review,
       {"risk_id": {"ref": "risk_entry", "label": "리스크·기회"}},
       "조치 효과성 평가 없이는 종결할 수 없습니다(CTL-042)."),
    _a("risk.record_continuity_plan", "사업연속성 계획 등록", "risk", "6.1.4",
       risk.record_continuity_plan,
       {"topics": {"dict_keys": risk.CONTINUITY_TOPICS}},
       "6.1.4 NOTE 1 의 리스크 범주를 모두 다루어야 합니다(CTL-034)."),
    _a("risk.verify_continuity_plan", "사업연속성 계획 검증", "risk", "6.1.4 a)",
       risk.verify_continuity_plan,
       {"record_id": {"ref": "governance_record", "label": "사업연속성 계획"}}),
    _a("governance.set_quality_objective", "품질목표 수립", "risk", "6.2.1, 6.2.2",
       governance.set_quality_objective,
       {"indicator_code": {"ref": "indicator_code"}},
       "자원·책임자·기한·평가방법이 모두 있어야 합니다(CTL-043)."),
    _a("governance.evaluate_objective", "품질목표 달성 평가", "risk", "9.3.3.1 a)",
       governance.evaluate_objective,
       {"objective_id": {"ref": "quality_objective", "label": "품질목표"}},
       "미달로 기록하면 경영검토 전에 시정조치가 필요합니다(CTL-020)."),
    # ------------------------------------------------------------------- 7.5 문서
    _a("documents.create", "문서 기안", "documents", "7.5.2", documents.create,
       {"content": {"help": "본문 또는 원본 파일 경로·링크"}},
       "기록(record)은 기록 유형과 보존기간이 필수입니다(CTL-003)."),
    _a("documents.submit_for_review", "검토 요청", "documents", "7.5.3.3 c)",
       documents.submit_for_review,
       {"doc_id": {"ref": "document_any", "label": "문서"},
        "verifier_id": {"ref": "person", "label": "검토자"}}),
    _a("documents.approve", "문서 승인", "documents", "7.5.2 c), 7.5.3.2",
       documents.approve, {"doc_id": {"ref": "document_any", "label": "문서"}},
       "검토를 거쳐야 하고 작성자는 승인자가 될 수 없습니다. "
       "승인 시 무결성 봉인이 생성됩니다(CTL-001, CTL-002)."),
    _a("documents.revise", "문서 개정", "documents", "7.5.3.2 c)", documents.revise,
       {"doc_id": {"ref": "document", "label": "개정 대상 문서"}}),
    _a("documents.dispose", "기록 폐기", "documents", "7.5.3.2 d), 7.5.3.3 d)",
       documents.dispose, {"doc_id": {"ref": "document_any", "label": "문서"}},
       "보존기간 만료 전에는 폐기할 수 없습니다(CTL-003)."),
    # ----------------------------------------------------------------- 7.1~7.3
    _a("competence.add_person", "인원 등록", "people", "7.1.2", competence.add_person),
    _a("competence.define_requirement", "필요역량 정의", "people", "7.2 a)",
       competence.define_requirement),
    _a("competence.record_competence", "역량 보유 기록", "people", "7.2 b), d)",
       competence.record_competence),
    _a("competence.assign_task", "업무 배정", "people", "7.2", competence.assign_task,
       None,
       "필요역량을 충족하지 않으면 배정이 거부되고 역량 갭이 자동 등록됩니다(CTL-026)."),
    _a("competence.plan_gap_action", "역량 갭 조치 계획", "people", "7.2.1.1 c)",
       competence.plan_gap_action),
    _a("competence.close_gap", "역량 갭 종결", "people", "7.2.1.1 c)", competence.close_gap),
    # ------------------------------------------------------------------ 7.1.5
    _a("calibration.register_resource", "측정자원 등록", "calibration", "7.1.5.3",
       calibration.register_resource),
    _a("calibration.record_calibration", "교정·검증 실시", "calibration", "7.1.5.3 e)~h)",
       calibration.record_calibration,
       {"resource_id": {"ref": "measuring_resource", "label": "측정자원"}},
       "기준기와 절차가 필수이고, 부적합 판정 시 자원은 사용 불가가 됩니다(CTL-025)."),
    _a("calibration.assess_retrospective_impact", "소급 영향평가", "calibration", "7.1.5.2",
       calibration.assess_retrospective_impact,
       {"calibration_record_id": {"ref": "calibration_record", "label": "교정 기록"},
        "finding": {"label": "영향평가 결과", "widget": "textarea"}}),
    # ------------------------------------------------------------------- 7.1/7.4
    _a("support.record_resource_plan", "자원 계획 등록", "support", "7.1.1.1",
       support.record_resource_plan,
       {"topics": {"dict_keys": support.RESOURCE_PLAN_TOPICS}}),
    _a("support.record_work_environment", "작업환경 기록", "support", "7.1.4",
       support.record_work_environment),
    _a("support.capture_lesson", "교훈·good practice 등록", "support", "7.1.6.1.1 a)",
       support.capture_lesson,
       {"source_type": {"choices": support.EXPERIENCE_SOURCES}}),
    _a("support.plan_communication", "의사소통 계획 등록", "support", "7.4 a)~e)",
       support.plan_communication),
    _a("support.record_communication", "의사소통 실시 기록", "support", "7.4",
       support.record_communication),
    _a("support.propose_innovation", "혁신 제안", "support", "8.1.1.1",
       support.propose_innovation),
    # ------------------------------------------------------------------ 8.1.2 입찰
    _a("tender.open_tender", "입찰 개설", "tender", "8.1.2", tender.open_tender, creates=("tender_no",)),
    _a("tender.complete_review", "입찰 검토 완료", "tender", "8.1.2 a)~f)",
       tender.complete_review, None,
       "요구사항 조항별 검토가 완료되어야 합니다(CTL-008)."),
    _a("tender.approve_offer", "견적 승인", "tender", "8.1.2 g)", tender.approve_offer),
    _a("tender.submit", "입찰서 제출", "tender", "8.1.2", tender.submit, None,
       "승인되지 않은 입찰은 제출할 수 없습니다(CTL-008)."),
    _a("tender.record_outcome", "낙찰 결과 기록", "tender", "8.1.2", tender.record_outcome),
    # -------------------------------------------------------------------- 8.2 요구
    _a("requirements.register", "요구사항 등록", "requirements", "8.2.2, 8.2.2.1.1",
       requirements.register),
    _a("requirements.review_clause_by_clause", "조항별 요구사항 검토", "requirements",
       "8.2.3.1, 8.2.5 e)", requirements.review_clause_by_clause,
       {"result": {"label": "검토 결과", "widget": "textarea"}},
       "기술 요구사항은 검증·유효성확인 방법이 정의되어야 합니다(CTL-008)."),
    _a("requirements.document_specification", "기술규격 확정", "requirements", "8.2.5 e) 6)",
       requirements.document_specification, None,
       "기능·비기능·RAMS·중요특성 범주가 모두 있어야 확정됩니다(CTL-046)."),
    _a("requirements.mark_verified", "요구사항 검증 완료", "requirements", "8.3.4.3",
       requirements.mark_verified),
    _a("requirements.mark_validated", "요구사항 유효성확인 완료", "requirements", "8.3.4.4",
       requirements.mark_validated),
    _a("requirements.apply_change", "승인된 변경 반영", "requirements", "8.2.4, 8.2.5 e) 7)",
       requirements.apply_change),
    # ----------------------------------------------------------------- 8.1.3 프로젝트
    _a("projects.create", "프로젝트 개설", "projects", "8.1.3.1.1", projects.create),
    _a("projects.attach_plan", "프로젝트 계획서 등록", "projects",
       "8.1.3.2, .6, .7, .8", projects.attach_plan,
       {"covers": {"widget": "pairs",
                   "help": "한 줄에 '항목키=내용'. 관리계획서는 8.1.3.2 a)~g)"
                           " (다중사이트는 h)~k) 추가), 품질계획서는"
                           " quality_assurance / quality_control 필요"}},
       "필수 항목 누락 시 등록이 거부됩니다(CTL-044)."),
    _a("projects.add_work_package", "작업패키지 등록", "projects", "8.1.3.3 c), d)",
       projects.add_work_package),
    _a("projects.verify_work_package", "작업패키지 검증", "projects", "8.1.3.3 e)",
       projects.verify_work_package),
    _a("projects.set_schedule", "프로젝트 일정 확정", "projects", "8.1.3.4 d), e)",
       projects.set_schedule, None, "주공정이 정의되어야 합니다."),
    _a("projects.record_cost", "프로젝트 원가 기록", "projects", "8.1.3.5 b), c)",
       projects.record_cost),
    _a("projects.plan_phase_review", "단계검토 계획", "projects", "8.1.3.1.1 d), e)",
       projects.plan_phase_review),
    _a("projects.raise_open_issue", "미결사항 등록", "projects", "8.1.3.1.1 g)",
       projects.raise_open_issue),
    _a("projects.close_open_issue", "미결사항 종결", "projects", "8.1.3.1.1 g)",
       projects.close_open_issue),
    _a("projects.hold_phase_review", "단계검토 실시(게이트)", "projects", "8.1.3.1.3 d)",
       projects.hold_phase_review,
       {"decision": {"choices": projects.DECISIONS}},
       "이전 단계 미결사항이 남아 있으면 통과가 거부되며, 최고경영자 승인 시에만 예외입니다(CTL-004)."),
    _a("projects.hold_project_review", "프로젝트 검토 실시", "projects", "8.1.3.11",
       projects.hold_project_review, None,
       "성과·예측·리스크·미결사항 네 항목이 모두 필요합니다(CTL-045)."),
    _a("projects.change_scope", "프로젝트 범위 변경", "projects", "8.1.3.3",
       projects.change_scope, None, "승인된 변경요청이 필요합니다(CTL-005)."),
    _a("projects.change_customer_delivery", "고객 인도일 변경", "projects", "8.1.3.4",
       projects.change_customer_delivery, None,
       "승인된 변경요청과 고객 통보가 필요합니다(CTL-005, CTL-028)."),
    _a("projects.increase_budget", "프로젝트 예산 변경", "projects", "8.1.3.5",
       projects.increase_budget, None, "증액은 승인된 변경요청이 필요합니다(CTL-005)."),
    _a("projects.close", "프로젝트 종료", "projects", "8.1.3.1.1 g)", projects.close,
       None, "미종결 미결사항이 있으면 종료할 수 없습니다(CTL-004)."),
    # ----------------------------------------------------------------- 8.1.4 형상
    _a("configuration.add_item", "형상항목 등록", "configuration", "8.1.4.1.1 b), c), g)",
       configuration.add_item, None,
       "안전관련 항목은 추적성 식별 방법이 필수입니다(CTL-007)."),
    _a("configuration.establish_baseline", "형상 기준선 설정", "configuration", "8.1.4.1.1 d)",
       configuration.establish_baseline,
       {"kind": {"choices": configuration.BASELINE_KINDS},
        "part_numbers": {"help": "품번을 줄바꿈 또는 쉼표로 구분"}}),
    _a("configuration.revise_item_in_baseline", "기준선 형상항목 개정", "configuration",
       "8.1.4.1.1 e), f)", configuration.revise_item_in_baseline,
       {"part_no": {"ref": "config_part_no", "label": "형상항목 품번"}},
       "동결된 기준선은 승인된 변경요청 없이 변경할 수 없습니다(CTL-006)."),
    # ----------------------------------------------------------------- 8.1.4.2 변경
    _a("change.raise_change", "변경요청 등록", "change", "8.1.4.2 b), c)",
       change.raise_change,
       {"scope": {"choices": change.SCOPES}, "origin": {"choices": change.ORIGINS}}, creates=("change_no",)),
    _a("change.analyse_impact", "변경 영향분석", "change", "8.1.4.2 d), e), l)~o)",
       change.analyse_impact, None,
       "기술 변경은 기납품 영향·재유효성확인 판단·대상 일련번호가 필요합니다(CTL-027)."),
    _a("change.notify_customer", "고객 통보·합의", "change", "8.1.4.2 f)",
       change.notify_customer),
    _a("change.notify_provider", "외부공급자 통보", "change", "8.1.4.2 f)",
       change.notify_provider),
    _a("change.approve", "변경 승인", "change", "8.1.4.2 g), h)", change.approve, None,
       "영향분석 완료 및 고객 합의(영향 있는 경우)가 선행되어야 합니다(CTL-027, CTL-028)."),
    _a("change.implement", "변경 실행", "change", "8.1.4.2 i)", change.implement, None,
       "승인 전에는 실행할 수 없습니다(CTL-027)."),
    _a("change.verify_implementation", "실행 검증·효과성 확인", "change", "8.1.4.2 j)",
       change.verify_implementation),
    # ---------------------------------------------------------------- 8.1.1.2 이전
    _a("transfer.plan", "프로세스 이전 계획", "transfer", "8.1.1.2 a)~c)", transfer.plan,
       None, "타당성조사·리스크평가·조치계획이 모두 필요합니다(CTL-035).", creates=("transfer_no",)),
    _a("transfer.communicate_to_customer", "고객 통보", "transfer", "8.1.1.2 d)",
       transfer.communicate_to_customer),
    _a("transfer.link_fai", "FAI 연결", "transfer", "8.1.1.2 e)", transfer.link_fai),
    _a("transfer.link_change", "변경관리 연계", "transfer", "8.1.4.2", transfer.link_change),
    _a("transfer.approve", "이전 승인", "transfer", "8.1.1.2", transfer.approve, None,
       "FAI 승인·변경관리 연계(외부 이전은 고객 통보까지)가 필요합니다(CTL-035)."),
    # -------------------------------------------------------------------- 8.3 설계
    _a("design.create", "설계 건 개설", "design", "8.3.1, 8.3.1.1", design.create, None,
       "안전관련 설계는 적용 안전표준(IEC 62278 등)을 식별해야 합니다(CTL-057).", creates=("design_no",)),
    _a("design.confirm_inputs", "설계 입력 확정", "design", "8.3.3, 8.3.3.1.1",
       design.confirm_inputs, None, "상충 입력이 해결되어야 합니다(CTL-060)."),
    _a("design.hold_design_review", "설계검토 실시", "design", "8.3.4.2",
       design.hold_design_review,
       {"decision": {"choices": ("accepted", "conditional", "rejected")},
        "level": {"choices": design.LEVELS}},
       "승인기준·필수참석자·의사결정 권한이 필요합니다(CTL-058)."),
    _a("design.plan_test", "검증·유효성확인 시험계획", "design", "8.3.4.5 a), b)",
       design.plan_test, {"kind": {"choices": ("verification", "validation")}},
       "8.3.4.5 a) 1)~8) 항목과 형상 기준선이 모두 필요합니다(CTL-047)."),
    _a("design.record_test_result", "시험 결과 기록", "design", "8.3.4.5 c)",
       design.record_test_result,
       {"test_id": {"ref": "design_test", "label": "시험"}}),
    _a("design.complete_verification", "설계검증 완료", "design", "8.3.4.3",
       design.complete_verification),
    _a("design.complete_validation", "설계 유효성확인 완료", "design", "8.3.4.4 a)",
       design.complete_validation),
    _a("design.agree_validation_control_plan", "고객 합의 관리계획 등록", "design",
       "8.3.4.4 b)", design.agree_validation_control_plan),
    _a("design.release_outputs", "설계 출력 출시", "design", "8.3.5.1.1",
       design.release_outputs, None,
       "검증 완료·생산입력 대비 검증이 필요하며, "
       "안전관련 설계는 안전 케이스가 필수입니다(CTL-009, CTL-057)."),
    # -------------------------------------------------------------------- 8.4 공급
    _a("suppliers.register", "공급자 등록", "suppliers", "8.4.1", suppliers.register),
    _a("suppliers.classify", "공급자 분류", "suppliers", "8.4.1.1.2", suppliers.classify),
    _a("suppliers.evaluate", "공급자 평가", "suppliers", "8.4.1.1.3 a), b)",
       suppliers.evaluate),
    _a("suppliers.approve", "공급자 승인", "suppliers", "8.4.1.1.4 a), c)",
       suppliers.approve, None, "분류·평가가 선행되어야 합니다(CTL-048)."),
    _a("suppliers.revoke_approval", "공급자 승인 철회", "suppliers", "8.4.1.1.4 b)",
       suppliers.revoke_approval),
    _a("suppliers.select_offer", "견적 선정 분석", "suppliers", "8.4.1.1.5.1",
       suppliers.select_offer,
       {"analysis": {"dict_keys": suppliers.OFFER_ANALYSIS_TOPICS}}),
    _a("suppliers.issue_purchase_order", "구매발주 발행", "suppliers", "8.4.3, 8.4.3.1",
       suppliers.issue_purchase_order,
       {"requirements_communicated": {"dict_keys": suppliers.REQUIRED_COMMUNICATION}},
       "승인된 공급자만 발주 가능하며 요구사항 12개 항목을 모두 전달해야 합니다(CTL-011, CTL-049).",
       creates=("po_no",)),
    _a("suppliers.acknowledge_order", "발주 확인서 수령", "suppliers", "8.4.4 a)",
       suppliers.acknowledge_order),
    _a("suppliers.approve_release", "EPPPS 출시 승인", "suppliers", "8.4.2.1.1",
       suppliers.approve_release, None,
       "FAI 승인·최초 사용 전 유효성확인·형상 기준선이 필요합니다(CTL-016)."),
    _a("suppliers.delegate_verification", "검증 위임", "suppliers", "8.4.2.2",
       suppliers.delegate_verification, None,
       "공급자 동의 증거와 통제수단이 필요합니다(CTL-013)."),
    _a("suppliers.record_incoming_inspection", "인수검사 기록", "suppliers", "8.4.2.2",
       suppliers.record_incoming_inspection),
    _a("suppliers.review_performance", "공급자 성과검토", "suppliers", "8.4.2.3",
       suppliers.review_performance),
    # -------------------------------------------------------------------- 8.5 생산
    _a("production.create_order", "생산 오더 생성", "production", "8.5.1.1.2",
       production.create_order, None,
       "승인된 생산데이터·ITP·리스크평가·치공구 목록이 필요합니다(CTL-050).", creates=("order_no",)),
    _a("production.verify_process", "생산공정 검증", "production", "8.5.1.1.3",
       production.verify_process),
    _a("production.validate_process", "생산공정 유효성확인", "production", "8.5.1.1.4.1",
       production.validate_process, None, "FAI 승인이 전제입니다(CTL-016)."),
    _a("production.release_serial_production", "양산 출시", "production", "8.9.3 a)",
       production.release_serial_production, None,
       "FAI 승인과 공정 유효성확인이 없으면 거부됩니다(CTL-016)."),
    _a("production.start_order", "생산 착수", "production", "8.5.1.1.2, 8.5.1.3",
       production.start_order,
       {"operator_ids": {"widget": "pairs",
                         "help": "한 줄에 '특수공정코드=작업자 인원ID'"}},
       "특수공정 포함 시 공정·작업자 자격이 유효해야 합니다(CTL-014)."),
    _a("production.create_item", "추적 품목 생성", "production", "8.5.2, 8.5.2.1",
       production.create_item, None,
       "추적성 요구 품목은 식별 방법과 보증기간이 필요합니다(CTL-032).", creates=("serial_no",)),
    _a("production.record_inspection", "검사·시험 기록", "production", "8.6.1 d)~f)",
       production.record_inspection,
       {"measuring_resource_id": {"ref": "measuring_resource", "label": "사용 측정자원"}},
       "교정 주기가 경과한 측정자원은 사용할 수 없습니다(CTL-025)."),
    _a("production.register_equipment", "생산설비 등록", "production", "8.5.1.4.1",
       production.register_equipment),
    _a("production.validate_equipment_before_first_use", "설비 최초 사용 전 유효성확인",
       "production", "8.5.1.4.1 b) 2)", production.validate_equipment_before_first_use,
       {"ident": {"ref": "equipment_ident", "label": "설비"}}),
    _a("production.record_maintenance", "설비 정비 기록", "production", "8.5.1.4.1 g)",
       production.record_maintenance,
       {"ident": {"ref": "equipment_ident", "label": "설비"},
        "kind": {"choices": ("preventive", "corrective", "predictive", "verification")}}),
    _a("production.receive_external_property", "고객·공급자 소유물 인수", "production",
       "8.5.3, 8.5.3.1", production.receive_external_property),
    _a("production.report_property_issue", "소유물 분실·손상 보고", "production", "8.5.3.1",
       production.report_property_issue,
       {"ref_no": {"label": "소유물", "ref": "external_property_ref"},
        "status": {"choices": ("lost", "damaged")}}),
    _a("production.return_property", "소유물 반환", "production", "8.5.3.1",
       production.return_property,
       {"ref_no": {"label": "소유물", "ref": "external_property_ref"}}),
    _a("production.define_preservation", "보존 규격 정의", "production", "8.5.4.1",
       production.define_preservation),
    # -------------------------------------------------------------- 8.5.1.3 특수공정
    _a("special_processes.register", "특수공정 등록", "special_processes", "8.5.1.3 a), b)",
       special_processes.register,
       {"six_m_covered": {"dict_keys": special_processes.SIX_M}},
       "적용 표준이 없으면 6M 을 다루는 작업지침이 필요합니다(CTL-014)."),
    _a("special_processes.qualify_process", "특수공정 자격부여", "special_processes",
       "8.5.1.3 b) 7)", special_processes.qualify_process,
       {"code": {"ref": "special_process_code", "label": "특수공정"}}),
    _a("special_processes.qualify_operator", "작업자 자격부여", "special_processes",
       "8.5.1.3 b) 5)", special_processes.qualify_operator,
       {"code": {"ref": "special_process_code", "label": "특수공정"}}),
    _a("special_processes.revalidate", "변경 후 재유효성확인", "special_processes",
       "8.5.1.3 b) 9)", special_processes.revalidate,
       {"code": {"ref": "special_process_code", "label": "특수공정"}}),
    # -------------------------------------------------------------------- 8.6 출하
    _a("release.release_item", "제품 출하", "release", "8.6, 8.6.1", release.release_item,
       None,
       "계획된 검사·시험이 완료되지 않으면 고객 특채가 필요합니다(CTL-017)."),
    _a("release.deliver_item", "고객 인도", "release", "8.3.4.4 b), 8.6",
       release.deliver_item, None,
       "출하 기록과 설계 유효성확인이 필요합니다(CTL-010, CTL-017)."),
    # ------------------------------------------------------------- 8.7 부적합·특채
    _a("nonconformity.raise_nonconformity", "부적합 등록", "nonconformity", "8.7.1, 8.7.3 b)",
       nonconformity.raise_nonconformity,
       {"source": {"choices": nonconformity.SOURCES}}, creates=("nc_no",)),
    _a("nonconformity.quarantine_unknown_item", "상태 불명 품목 격리", "nonconformity",
       "8.5.2.1", nonconformity.quarantine_unknown_item),
    _a("nonconformity.evaluate_capa_need", "시정조치 필요성 평가", "nonconformity",
       "10.2.3 b), e)", nonconformity.evaluate_capa_need, None,
       "안전영향·고객출처·반복·고비용 중 하나라도 해당하면 시정조치가 필수가 됩니다."),
    _a("nonconformity.decide_disposition", "부적합 처리 결정", "nonconformity",
       "8.7.1, 8.7.2 d)", nonconformity.decide_disposition),
    _a("nonconformity.verify_correction", "시정 후 적합성 재검증", "nonconformity", "8.7.1",
       nonconformity.verify_correction),
    _a("nonconformity.link_capa", "시정조치 연결", "nonconformity", "10.2",
       nonconformity.link_capa),
    _a("nonconformity.close", "부적합 종결", "nonconformity", "8.7.2, 10.2.1",
       nonconformity.close, None,
       "필요성 평가 없이, 또는 필요한 시정조치가 종결되지 않으면 종결할 수 없습니다(CTL-033)."),
    _a("nonconformity.raise_concession", "특채 신청", "nonconformity", "8.7.3 d)",
       nonconformity.raise_concession,
       {"kind": {"choices": ("internal", "customer", "external_provider")}},
       "승인수량과 유효기간이 필수입니다(CTL-018).", creates=("concession_no",)),
    _a("nonconformity.approve_concession_internally", "특채 내부 승인", "nonconformity",
       "8.7.3 c) 2)", nonconformity.approve_concession_internally),
    _a("nonconformity.approve_concession_by_customer", "특채 고객 승인", "nonconformity",
       "8.7.3 g)", nonconformity.approve_concession_by_customer, None,
       "식별 방법 합의와 적합성 선언서 기재가 선행되어야 합니다(CTL-019)."),
    # --------------------------------------------------------------- 10장 시정조치
    _a("capa.open_capa", "시정조치 개시", "capa", "10.2.1, 10.2.3", capa.open_capa,
       {"source_type": {"choices": capa.SOURCE_TYPES},
        "method": {"choices": capa.METHODS},
        "escalation_level": {"cast": "int"}}, creates=("capa_no",)),
    _a("capa.record_analysis", "원인분석·조치 등록", "capa", "10.2.1 b), c)",
       capa.record_analysis, None,
       "유사 부적합 확인 없이는 확정할 수 없습니다(CTL-033)."),
    _a("capa.escalate", "에스컬레이션", "capa", "10.2.3 e)", capa.escalate,
       {"level": {"choices": tuple(str(k) for k in capa.ESCALATION_TARGETS), "cast": "int"}}),
    _a("capa.close_capa", "시정조치 종결", "capa", "10.2.1 d)", capa.close_capa, None,
       "효과적이지 않은 시정조치는 종결할 수 없습니다(CTL-033)."),
    _a("capa.record_improvement", "개선 등록", "capa", "10.1, 10.3",
       capa.record_improvement, {"kind": {"choices": capa.IMPROVEMENT_KINDS}}),
    # ------------------------------------------------------------------- 8.8 RAMS
    _a("rams.set_objective", "RAM 목표 설정", "rams", "8.8.2 a), b)", rams.set_objective),
    _a("rams.collect_field_data", "현장 데이터 수집", "rams", "8.8.2 c)",
       rams.collect_field_data,
       {"severity": {"choices": ("minor", "major", "critical")}}),
    _a("rams.evaluate_objective", "RAM 목표 평가", "rams", "8.8.2 d)~g)",
       rams.evaluate_objective,
       {"objective_id": {"ref": "rams_objective", "label": "RAM 목표"}},
       "목표 미달 시 분석·시정조치·설계 환류가 모두 필요합니다(CTL-029)."),
    _a("rams.record_safety_case", "안전 케이스 등록", "rams", "8.8.3",
       rams.record_safety_case, None,
       "IEC 62278/62425/62279 등 적용 표준 식별이 필요합니다(CTL-057)."),
    _a("rams.record_lcc", "LCC 기록", "rams", "8.8.4", rams.record_lcc),
    # -------------------------------------------------------------------- 8.9 FAI
    _a("fai.plan", "FAI 계획", "fai", "8.9.1 a), b), 8.9.2", fai.plan, creates=("fai_no",)),
    _a("fai.confirm_preconditions", "사전조건 평가", "fai", "8.9.2 a)",
       fai.confirm_preconditions),
    _a("fai.perform_inspection", "FAI 검사 실시", "fai", "8.9.1 c)",
       fai.perform_inspection),
    _a("fai.decide", "FAI 결정", "fai", "8.9.1 d), e)", fai.decide,
       {"decision": {"choices": fai.DECISIONS}},
       "조건부·거부 시 시정조치 연계가 필수입니다(CTL-016)."),
    _a("fai.invalidate", "FAI 무효화", "fai", "8.9.3 b) 2)", fai.invalidate),
    # ------------------------------------------------------------------- 8.10 단산
    _a("obsolescence.create_plan", "단산 관리계획 수립", "obsolescence", "8.10 b)",
       obsolescence.create_plan),
    _a("obsolescence.assess_risk", "단산 리스크 평가", "obsolescence", "8.10 a)",
       obsolescence.assess_risk,
       {"risk_level": {"choices": ("high", "medium", "low")}},
       "고위험 항목은 완화조치가 필수이며 관리계획이 선행되어야 합니다(CTL-030)."),
    _a("obsolescence.communicate_to_customer", "고객 의사소통", "obsolescence", "8.10 c)",
       obsolescence.communicate_to_customer,
       {"risk_id": {"ref": "obsolescence_risk", "label": "단산 리스크"}}),
    _a("obsolescence.close_risk", "단산 리스크 종결", "obsolescence", "8.10",
       obsolescence.close_risk,
       {"risk_id": {"ref": "obsolescence_risk", "label": "단산 리스크"}}),
    # ---------------------------------------------------------------- 8.5.5 인도후
    _a("post_delivery.record", "인도 후 활동 기록", "post_delivery", "8.5.5.1",
       post_delivery.record, None,
       "보증·정비 활동은 승인된 수리지침과 RQMS 환류가 필요합니다(CTL-059)."),
    # -------------------------------------------------------------------- 9.1 지표
    _a("indicators.record_measurement", "지표 측정값 기록", "indicators", "9.1.1, 9.1.3.1",
       indicators.record_measurement, None,
       "KPI 목표 미달 시 시정조치 연결이 필수이고, 분석 결과는 공유 대상을 기록해야 합니다(CTL-020)."),
    _a("indicators.record_failure_data", "내·외부 실패 데이터 기록", "indicators",
       "9.1.1.1.1", indicators.record_failure_data),
    # ------------------------------------------------------------------ 9.1.2 고객
    _a("customer.record_communication", "고객 의사소통 기록", "customer", "8.2.1",
       customer.record_communication),
    _a("customer.notify_delay", "납기 지연 통보", "customer", "8.2.1.1, 8.1.3.8",
       customer.notify_delay, None, "영향과 대책을 함께 전달해야 합니다(CTL-028)."),
    _a("customer.receive_complaint", "고객 불만 접수", "customer", "9.1.2.1 a)",
       customer.receive_complaint, creates=("complaint_no",)),
    _a("customer.acknowledge", "접수 통보", "customer", "9.1.2.1 b)", customer.acknowledge),
    _a("customer.link_capa", "불만-시정조치 연계", "customer", "9.1.2.1 b)",
       customer.link_capa),
    _a("customer.respond", "고객 회신", "customer", "9.1.2.1", customer.respond, None,
       "접수 통보와 시정조치 연계가 선행되어야 합니다(CTL-053)."),
    _a("customer.record_satisfaction", "고객만족 측정 기록", "customer", "9.1.2",
       customer.record_satisfaction),
    # -------------------------------------------------------------------- 9.2 심사
    _a("audit.create_programme", "심사 프로그램 생성", "audit", "9.2.2 a)",
       audit.create_programme),
    _a("audit.approve_programme", "심사 프로그램 승인", "audit", "9.2.3.2",
       audit.approve_programme),
    _a("audit.register_auditor", "심사원 등록", "audit", "9.2.3.3.1",
       audit.register_auditor,
       {"home_processes": {"help": "쉼표로 구분한 프로세스 코드 — 자기업무 심사 금지 판정에 사용"}},
       "심사원칙·범위·조항·기준 지식이 모두 필요합니다(CTL-055)."),
    _a("audit.plan_audit", "심사 계획", "audit", "9.2.2 b), 9.2.3.2 d)", audit.plan_audit,
       None,
       "자기 소속 프로세스는 심사할 수 없고, 선임심사원은 경험 요건을 충족해야 합니다(CTL-022, CTL-055).",
       creates=("audit_no",)),
    _a("audit.perform_audit", "심사 실시·보고", "audit", "9.2.2 d), f)",
       audit.perform_audit),
    _a("audit.record_finding", "발견사항 등록", "audit", "9.2.2 e)", audit.record_finding,
       None, "중·경부적합은 시정조치 연계가 필수입니다(CTL-021)."),
    # ------------------------------------------------------------------- 9.3~9.4
    _a("review.hold_management_review", "경영검토 실시", "review",
       "9.3.1.1, 9.3.2, 9.3.2.1, 9.3.3.1", review.hold_management_review,
       {"inputs": {"dict_keys": _MR_INPUT_KEYS},
        "outputs": {"dict_keys": review.MR_OUTPUTS}},
       "입력·출력 항목 누락 시 거부되며, "
       "미달 목표에는 시정조치가 연계되어야 합니다(CTL-054, CTL-023, CTL-020)."),
    _a("review.hold_process_review", "프로세스 검토 실시", "review", "9.4",
       review.hold_process_review,
       {"fields": {"dict_keys": review.PROCESS_REVIEW_FIELDS}},
       "프로세스 오너가 주재하고 최고경영자에게 보고해야 합니다(CTL-024)."),
)

ACTION_BY_ID = {a.id: a for a in ACTIONS}

# 문서 선택 시 승인 문서만 보이면 곤란한 액션(검토요청·승인·폐기)을 위한 전체 문서 참조
REF_SOURCES["document_any"] = (
    "document",
    "id",
    "doc_no || ' v' || version || ' [' || status || '] ' || title",
    "",
)


def actions_for(section: str) -> tuple[Action, ...]:
    return tuple(a for a in ACTIONS if a.section == section)
