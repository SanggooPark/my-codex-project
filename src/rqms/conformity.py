"""적합성 평가 및 추적성 매트릭스.

ISO 22163:2023 의 각 조항에 대해
    1) 구현 모듈이 존재하는지,
    2) 강제 통제가 연결되어 있고 위반이 없는지,
    3) 요구되는 문서화된 정보(증거)가 실제로 존재하는지
를 평가하여 조항-통제-증거 추적 매트릭스와 갭 목록을 생성한다.

이 보고서는 내부심사(9.2)와 인증심사에서 적합성 주장의 근거로 사용된다.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field

from .checks import Finding, run_checks
from .db import Database, today
from .standard import Clause, load_registry

#: 증거 키 -> (테이블, 추가 조건, 설명)
#: 조항이 요구하는 문서화된 정보가 시스템에 실제로 존재하는지 판정하는 근거다.
EVIDENCE_SOURCES: dict[str, tuple[str, str, str]] = {
    "analysis_record": ("indicator_measurement", "TRIM(analysis) != ''", "지표 분석 기록"),
    "applicability_justification": (
        "governance_record",
        "kind = 'rqms_scope'",
        "비적용 조항 정당화",
    ),
    "audit_programme": ("audit_programme", "approved_on IS NOT NULL", "승인된 심사 프로그램"),
    "audit_report": ("internal_audit", "report_doc_id IS NOT NULL", "심사 보고서"),
    "auditor_qualification_record": ("auditor", "", "심사원 자격 기록"),
    "business_continuity_plan": (
        "governance_record",
        "kind = 'business_continuity_plan'",
        "사업연속성 계획",
    ),
    "business_plan": ("governance_record", "kind = 'business_plan'", "요약 사업계획"),
    "calibration_record": ("calibration_record", "", "교정·검증 기록"),
    "change_impact_analysis": (
        "change_request",
        "TRIM(impact_analysis) != ''",
        "변경 영향분석",
    ),
    "change_request": ("change_request", "", "변경요청"),
    "communication_plan": ("communication_entry", "kind = 'plan'", "의사소통 계획"),
    "communication_record": ("communication_entry", "kind = 'record'", "의사소통 기록"),
    "competence_matrix": ("competence_requirement", "", "역량 요구 정의(역량 매트릭스)"),
    "competence_record": ("competence", "", "역량 보유 기록"),
    "complaint_record": ("complaint", "", "고객 불만 기록"),
    "concession_register": ("concession", "", "특채 등록부"),
    "configuration_audit_record": ("config_status_record", "", "형상 감사/상태 기록"),
    "configuration_baseline": ("baseline", "", "형상 기준선"),
    "configuration_management_plan": (
        "project_plan",
        "plan_kind = 'configuration'",
        "형상관리 계획서",
    ),
    "configuration_status_record": ("config_status_record", "", "형상상태 기록"),
    "context_issue_register": ("context_entry", "kind = 'issue'", "내·외부 이슈 등록부"),
    "corrective_action_record": ("capa", "", "시정조치 기록"),
    "customer_communication_record": (
        "communication_entry",
        "kind = 'record'",
        "고객 의사소통 기록",
    ),
    "customer_property_register": ("external_property", "", "고객·공급자 소유물 등록부"),
    "customer_satisfaction_record": ("customer_satisfaction", "", "고객만족 측정 기록"),
    "delegation_register": ("verification_delegation", "", "검증 위임 등록부"),
    "design_input": ("design", "inputs_complete = 1", "설계 입력"),
    "design_output": ("design", "output_released_on IS NOT NULL", "설계 출력"),
    "design_plan": ("design", "plan_doc_id IS NOT NULL", "설계·개발 계획"),
    "design_review_record": ("design_review", "", "설계검토 기록"),
    "document_hierarchy": ("document", "hierarchy_level IS NOT NULL", "문서 계층"),
    "document_register": ("document", "", "문서 등록부"),
    "eppps_release_approval": ("eppps_release", "", "EPPPS 출시 승인"),
    "equipment_register": ("production_equipment", "", "설비 등록부"),
    "fai_record": ("fai", "", "FAI 기록"),
    "failure_data_record": ("nonconformity", "", "내·외부 실패 데이터"),
    "field_data_record": ("field_data", "", "현장 데이터"),
    "gate_checklist": ("phase_review", "gate_checklist_doc IS NOT NULL", "게이트 체크리스트"),
    "improvement_record": ("improvement", "", "개선 기록"),
    "incoming_inspection_record": ("incoming_inspection", "", "인수검사 기록"),
    "innovation_record": ("innovation", "", "혁신 기록"),
    "inspection_record": ("inspection", "", "검사·시험 기록"),
    "inspection_test_plan": ("production_order", "itp_doc_id IS NOT NULL", "검사·시험계획"),
    "interested_party_register": (
        "context_entry",
        "kind = 'interested_party'",
        "이해관계자 등록부",
    ),
    "kpi_definition": ("__registry_kpi__", "", "KPI 정의(레지스트리)"),
    "lcc_record": ("lcc_record", "", "LCC 기록"),
    "lesson_learned": ("lesson_learned", "", "교훈·good practice"),
    "maintenance_record": ("equipment_maintenance", "", "설비 정비 기록"),
    "management_review_record": ("management_review", "", "경영검토 기록"),
    "master_production_schedule": (
        "production_order",
        "scheduled_start_on IS NOT NULL",
        "기준생산계획",
    ),
    "measurement_record": ("indicator_measurement", "", "PI 측정 기록"),
    "measuring_resource_register": ("measuring_resource", "", "측정자원 등록부"),
    "nonconformity_record": ("nonconformity", "", "부적합 등록부"),
    "obsolescence_management_plan": ("obsolescence_plan", "", "단산 관리계획"),
    "obsolescence_risk_record": ("obsolescence_risk", "", "단산 리스크 기록"),
    "offer_selection_record": (
        "governance_record",
        "kind = 'offer_selection'",
        "견적 선정 분석",
    ),
    "operational_plan": ("production_order", "", "운용 계획(생산 오더)"),
    "operator_qualification": ("special_process_operator", "", "작업자 자격"),
    "phase_review_record": ("phase_review", "held_on IS NOT NULL", "단계검토 기록"),
    "po_acknowledgement": ("purchase_order", "acknowledged_on IS NOT NULL", "발주 확인서"),
    "post_delivery_record": ("post_delivery_activity", "", "인도 후 활동 기록"),
    "preservation_specification": ("preservation_spec", "", "보존 규격"),
    "process_description": ("process_instance", "description_doc IS NOT NULL", "프로세스 기술서"),
    "process_hierarchy": ("process_instance", "", "프로세스 계층구조"),
    "process_record": ("document", "doc_type = 'record'", "프로세스 실행 기록"),
    "process_review_record": ("process_review", "", "프로세스 검토 기록"),
    "process_training_record": ("process_training", "", "프로세스 교육 기록"),
    "process_validation_record": (
        "production_order",
        "process_validated_on IS NOT NULL",
        "생산공정 유효성확인",
    ),
    "process_verification_record": (
        "production_order",
        "process_verified_on IS NOT NULL",
        "생산공정 검증",
    ),
    "production_data_approval": (
        "production_order",
        "approved_data_doc_id IS NOT NULL",
        "승인된 생산 데이터",
    ),
    "production_order": ("production_order", "", "생산 오더"),
    "project_communication_plan": (
        "project_plan",
        "plan_kind = 'communication'",
        "프로젝트 의사소통 계획서",
    ),
    "project_cost_record": ("project_cost", "", "프로젝트 원가 기록"),
    "project_hr_plan": ("project_plan", "plan_kind = 'hr'", "프로젝트 인력계획서"),
    "project_management_plan": (
        "project_plan",
        "plan_kind = 'management'",
        "프로젝트 관리계획서",
    ),
    "project_quality_plan": ("project_plan", "plan_kind = 'quality'", "프로젝트 품질계획서"),
    "project_record": ("project", "", "프로젝트 기록"),
    "project_review_record": ("project_review", "", "프로젝트 검토 기록"),
    "project_schedule": ("project", "TRIM(critical_path) != ''", "프로젝트 일정(주공정)"),
    "purchase_order": ("purchase_order", "", "구매발주"),
    "quality_objective": ("quality_objective", "", "품질목표"),
    "quality_policy": ("governance_record", "kind = 'quality_policy'", "품질방침"),
    "rams_record": ("rams_objective", "", "RAMS 기록"),
    "release_record": ("release_record", "", "출하 기록"),
    "repair_instruction": (
        "post_delivery_activity",
        "repair_instruction_doc_id IS NOT NULL",
        "수리지침",
    ),
    "requirement_register": ("requirement", "", "요구사항 등록부"),
    "requirement_review_record": ("requirement", "reviewed = 1", "요구사항 검토 기록"),
    "resource_plan": ("governance_record", "kind = 'resource_plan'", "자원 계획"),
    "retention_schedule": ("document", "retention_months IS NOT NULL", "보존기간 표"),
    "risk_action": ("risk_entry", "TRIM(action) != ''", "리스크 조치"),
    "risk_register": ("risk_entry", "", "리스크·기회 등록부"),
    "risk_review_record": ("risk_entry", "reviewed_on IS NOT NULL", "리스크 검토 기록"),
    "role_assignment": ("person", "", "역할·책임 배정"),
    "rqms_scope": ("governance_record", "kind = 'rqms_scope'", "RQMS 적용범위"),
    "safety_case": ("safety_record", "safety_case_doc_id IS NOT NULL", "안전 케이스"),
    "safety_standard_register": (
        "safety_record",
        "TRIM(applicable_standards) != ''",
        "적용 안전표준",
    ),
    "social_responsibility_statement": (
        "governance_record",
        "kind = 'social_responsibility'",
        "사회적 책임 선언",
    ),
    "special_process_qualification": (
        "special_process",
        "qualified_on IS NOT NULL",
        "특수공정 자격",
    ),
    "stop_authority_appointment": ("stop_authority", "", "정지 권한자 임명"),
    "supplier_control_plan": ("supplier", "TRIM(approval_scope) != ''", "공급자 관리 범위"),
    "supplier_evaluation_record": ("supplier", "evaluated_on IS NOT NULL", "공급자 평가 기록"),
    "supplier_performance_review": (
        "supplier",
        "performance_reviewed_on IS NOT NULL",
        "공급자 성과검토",
    ),
    "supplier_register": ("supplier", "", "공급자 등록부"),
    "technical_specification": ("requirement", "spec_doc_id IS NOT NULL", "기술규격"),
    "tender_approval": ("tender", "approved_on IS NOT NULL", "입찰 승인"),
    "tender_record": ("tender", "", "입찰 기록"),
    "test_plan": ("design_test", "plan_doc_id IS NOT NULL", "시험계획"),
    "test_record": ("design_test", "performed_on IS NOT NULL", "시험 기록"),
    "traceability_record": ("traceable_item", "", "추적성 기록"),
    "training_record": ("process_training", "", "교육 기록"),
    "transfer_record": ("process_transfer", "", "프로세스 이전 기록"),
    "validation_record": ("design", "validated_on IS NOT NULL", "유효성확인 기록"),
    "verification_record": ("design", "verified_on IS NOT NULL", "검증 기록"),
    "work_breakdown_structure": ("work_package", "", "작업분할구조"),
    "work_environment_record": (
        "governance_record",
        "kind = 'work_environment'",
        "작업환경 기록",
    ),
}

#: 조항 평가 상태
CONFORMANT = "conformant"
GAP = "gap"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ClauseAssessment:
    """조항 1건에 대한 적합성 평가."""

    clause: Clause
    status: str
    missing_evidence: tuple[str, ...] = ()
    missing_modules: tuple[str, ...] = ()
    control_findings: tuple[Finding, ...] = ()
    note: str = ""

    @property
    def is_gap(self) -> bool:
        return self.status == GAP


@dataclass(frozen=True)
class ConformityReport:
    """전체 적합성 보고서."""

    as_of: str
    assessments: tuple[ClauseAssessment, ...]
    findings: tuple[Finding, ...]
    excluded: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ 집계
    @property
    def total(self) -> int:
        return len(self.assessments)

    @property
    def applicable(self) -> tuple[ClauseAssessment, ...]:
        return tuple(a for a in self.assessments if a.status != NOT_APPLICABLE)

    @property
    def gaps(self) -> tuple[ClauseAssessment, ...]:
        return tuple(a for a in self.assessments if a.is_gap)

    @property
    def conformant(self) -> tuple[ClauseAssessment, ...]:
        return tuple(a for a in self.assessments if a.status == CONFORMANT)

    def rate(self, *, mandatory_only: bool = False) -> float:
        pool = [
            a
            for a in self.applicable
            if not mandatory_only or a.clause.is_mandatory
        ]
        if not pool:
            return 0.0
        ok = sum(1 for a in pool if a.status == CONFORMANT)
        return round(ok / len(pool) * 100, 1)

    def summary(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "clauses_total": self.total,
            "clauses_applicable": len(self.applicable),
            "clauses_not_applicable": self.total - len(self.applicable),
            "conformant": len(self.conformant),
            "gaps": len(self.gaps),
            "conformity_rate_pct": self.rate(),
            "mandatory_conformity_rate_pct": self.rate(mandatory_only=True),
            "control_findings": len(self.findings),
            "major_findings": sum(1 for f in self.findings if f.severity == "major"),
            "minor_findings": sum(1 for f in self.findings if f.severity == "minor"),
        }


def evidence_present(db: Database, key: str) -> bool:
    """증거 키에 해당하는 문서화된 정보가 존재하는지 확인한다."""
    source = EVIDENCE_SOURCES.get(key)
    if source is None:
        return False
    table, where, _ = source
    if table == "__registry_kpi__":
        return bool(load_registry().kpis())
    sql = f"SELECT 1 FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return db.one(sql + " LIMIT 1") is not None


def module_available(path: str) -> bool:
    """구현 모듈이 임포트 가능한지 확인한다."""
    try:
        importlib.import_module(path)
    except Exception:
        return False
    return True


def assess(
    db: Database, *, as_of: str | None = None, excluded: dict[str, str] | None = None
) -> ConformityReport:
    """전체 적합성을 평가한다."""
    registry = load_registry()
    reference = as_of or today()
    if excluded is None:
        from .services.governance import excluded_clauses

        excluded = excluded_clauses(db)

    findings = run_checks(db, as_of=as_of)
    findings_by_control: dict[str, list[Finding]] = {}
    for finding in findings:
        findings_by_control.setdefault(finding.control_id, []).append(finding)

    assessments: list[ClauseAssessment] = []
    for clause in registry.clauses:
        if clause.id in excluded:
            assessments.append(
                ClauseAssessment(
                    clause=clause,
                    status=NOT_APPLICABLE,
                    note=f"비적용 정당화: {excluded[clause.id]}",
                )
            )
            continue

        missing_evidence = tuple(
            key for key in clause.documented_info if not evidence_present(db, key)
        )
        missing_modules = tuple(
            path for path in clause.modules if not module_available(path)
        )
        clause_findings = tuple(
            f for cid in clause.controls for f in findings_by_control.get(cid, ())
        )

        status = CONFORMANT
        if missing_evidence or missing_modules or clause_findings:
            status = GAP
        assessments.append(
            ClauseAssessment(
                clause=clause,
                status=status,
                missing_evidence=missing_evidence,
                missing_modules=missing_modules,
                control_findings=clause_findings,
            )
        )

    return ConformityReport(
        as_of=reference,
        assessments=tuple(assessments),
        findings=tuple(findings),
        excluded=dict(excluded),
    )


def traceability_matrix(db: Database) -> list[dict[str, object]]:
    """조항 - 프로세스 - 통제 - 구현 모듈 - 증거 추적 매트릭스."""
    registry = load_registry()
    rows: list[dict[str, object]] = []
    for clause in registry.clauses:
        rows.append(
            {
                "clause": clause.id,
                "title": clause.title_ko,
                "obligation": clause.obligation,
                "source": clause.source,
                "processes": list(clause.processes),
                "controls": list(clause.controls),
                "modules": list(clause.modules),
                "evidence": [
                    {
                        "key": key,
                        "label": EVIDENCE_SOURCES.get(key, ("", "", key))[2],
                        "present": evidence_present(db, key),
                    }
                    for key in clause.documented_info
                ],
            }
        )
    return rows


def control_matrix(db: Database, *, as_of: str | None = None) -> list[dict[str, object]]:
    """통제 - 조항 - 위반 현황 매트릭스."""
    registry = load_registry()
    findings = run_checks(db, as_of=as_of)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.control_id] = counts.get(finding.control_id, 0) + 1
    return [
        {
            "control": control.id,
            "kind": control.kind,
            "severity": control.severity,
            "title": control.title,
            "clauses": list(control.clauses),
            "violations": counts.get(control.id, 0),
        }
        for control in registry.controls
    ]


def process_matrix(db: Database) -> list[dict[str, object]]:
    """Annex A 프로세스 - 조항 - 지표 - 오너 - 검토 현황."""
    registry = load_registry()
    rows: list[dict[str, object]] = []
    for process in registry.processes:
        instance = db.find("process_instance", code=process.code)
        last_review = db.scalar(
            "SELECT MAX(held_on) FROM process_review WHERE process_code = ?",
            (process.code,),
        )
        last_audit = db.scalar(
            "SELECT MAX(performed_on) FROM internal_audit WHERE process_code = ?",
            (process.code,),
        )
        owner = None
        if instance is not None and instance["owner_id"] is not None:
            owner = db.fetch("person", int(instance["owner_id"]))["name"]
        rows.append(
            {
                "code": process.code,
                "name": process.name_ko,
                "clause": process.clause,
                "obligation": process.obligation,
                "level": process.level,
                "parent": process.parent,
                "registered": instance is not None,
                "applicable": bool(instance["applicable"]) if instance else True,
                "owner": owner,
                "indicators": [
                    i.code for i in registry.indicators_for_process(process.code)
                ],
                "clauses": [c.id for c in registry.clauses_for_process(process.code)],
                "last_process_review": last_review,
                "last_internal_audit": last_audit,
            }
        )
    return rows


def gap_report(db: Database, *, as_of: str | None = None) -> list[dict[str, object]]:
    """갭 목록 — 시정조치 계획 수립의 입력으로 사용한다."""
    report = assess(db, as_of=as_of)
    out: list[dict[str, object]] = []
    for assessment in report.gaps:
        out.append(
            {
                "clause": assessment.clause.id,
                "title": assessment.clause.title_ko,
                "obligation": assessment.clause.obligation,
                "missing_evidence": [
                    EVIDENCE_SOURCES.get(k, ("", "", k))[2]
                    for k in assessment.missing_evidence
                ],
                "missing_modules": list(assessment.missing_modules),
                "control_findings": [str(f) for f in assessment.control_findings],
            }
        )
    return out
