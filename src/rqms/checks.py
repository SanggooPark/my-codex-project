"""상태 점검형 통제(kind=audit) 검증.

쓰기 시점에 강제되는 invariant 통제와 달리, 여기의 통제는 시스템 전체 상태를 대상으로
주기적으로 점검한다. 내부심사(9.2)와 프로세스 검토(9.4)의 객관적 증거로 사용된다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from .db import Database, today
from .services import (
    audit,
    calibration,
    change,
    competence,
    configuration,
    customer,
    documents,
    indicators,
    obsolescence,
    post_delivery,
    production,
    projects,
    review,
    risk,
    suppliers,
)
from .services._base import add_months, is_past
from .services.governance import (
    BUSINESS_PLAN_TOPICS,
    POLICY_TOPICS,
    PROCESS_DESCRIPTION_FIELDS,
)
from .standard import load_registry


@dataclass(frozen=True)
class Finding:
    """통제 점검 결과 1건."""

    control_id: str
    severity: str
    title: str
    clauses: tuple[str, ...]
    detail: str

    def __str__(self) -> str:
        return f"[{self.control_id}/{self.severity}] {self.title} — {self.detail}"


#: 점검 함수 시그니처: (db, as_of) -> 위반 상세 문자열 목록
#: 이 별칭은 애노테이션이 아니라 런타임에 평가되므로, Python 3.9 를 지원하기 위해
#: PEP 604 (`str | None`) 대신 `Optional[str]` 을 쓴다.
CheckFn = Callable[[Database, Optional[str]], list[str]]


# ------------------------------------------------------------------- 4장 / 5장
def _ctl_036(db: Database, as_of: str | None) -> list[str]:
    """요약 사업계획 문서화 및 연간 검토 (4.1.1.1)."""
    row = db.one(
        "SELECT * FROM governance_record WHERE kind = 'business_plan' "
        "ORDER BY ref_year DESC LIMIT 1"
    )
    if row is None:
        return ["문서화된 요약 사업계획이 없습니다."]
    out = []
    payload = json.loads(row["payload"])
    missing = [t for t in BUSINESS_PLAN_TOPICS if not payload.get(t)]
    if missing:
        out.append(f"{row['ref_year']}년 사업계획 누락 고려사항: {', '.join(missing)}")
    if not row["reviewed_on"] or is_past(add_months(row["reviewed_on"], 12), as_of=as_of):
        out.append(f"사업계획 연간 검토 기한 경과(최근 검토 {row['reviewed_on']}).")
    return out


def _ctl_037(db: Database, as_of: str | None) -> list[str]:
    """RQMS 적용범위 문서화 및 비적용 정당화 (4.3, 4.3.1)."""
    row = db.one(
        "SELECT * FROM governance_record WHERE kind = 'rqms_scope' "
        "ORDER BY ref_year DESC LIMIT 1"
    )
    if row is None:
        return ["문서화된 RQMS 적용범위가 없습니다."]
    out = []
    payload = json.loads(row["payload"])
    if not payload.get("products_services"):
        out.append("적용범위에 대상 제품·서비스 유형이 기술되지 않았습니다.")
    for clause_id, reason in dict(payload.get("exclusions", {})).items():
        if not reason:
            out.append(f"비적용 조항 {clause_id} 의 정당화 사유가 없습니다.")
    registry = load_registry()
    for process in registry.mandatory_processes():
        registered = db.find("process_instance", code=process.code)
        if registered is not None and not registered["applicable"]:
            out.append(f"필수 프로세스 {process.code} 가 비적용으로 선언되어 있습니다.")
    return out


def _ctl_038(db: Database, as_of: str | None) -> list[str]:
    """프로세스 기술서 최소항목 및 계층구조 (4.4.1, 4.4.3, 7.1.1.1)."""
    out = []
    registry = load_registry()
    for process in registry.processes:
        row = db.find("process_instance", code=process.code)
        if row is None:
            if process.is_mandatory:
                out.append(f"필수 프로세스 {process.code} 가 등록되지 않았습니다.")
            continue
        if not row["applicable"]:
            continue
        if row["description_doc"] is None:
            out.append(f"프로세스 {process.code}: 기술서 문서가 연결되지 않았습니다.")
        missing = [f for f in PROCESS_DESCRIPTION_FIELDS if not (row[f] or "").strip()]
        if missing:
            out.append(f"프로세스 {process.code}: 기술서 누락 항목 {', '.join(missing)}")
        if not (row["risk_criteria"] or "").strip():
            out.append(f"프로세스 {process.code}: 리스크기반 통제 기준 미정의(4.4.3 f).")
    if not db.one(
        "SELECT 1 FROM governance_record WHERE kind = 'resource_plan' LIMIT 1"
    ):
        out.append("자원 계획(7.1.1.1)이 등록되지 않았습니다.")
    return out


def _ctl_039(db: Database, as_of: str | None) -> list[str]:
    """프로세스 오너 임명 및 프로세스 교육 (4.4.3, 5.3.2)."""
    out = []
    for process in load_registry().processes:
        row = db.find("process_instance", code=process.code)
        if row is None or not row["applicable"]:
            continue
        if row["owner_id"] is None:
            out.append(f"프로세스 {process.code}: 오너가 임명되지 않았습니다.")
        trained = db.count(
            "SELECT COUNT(*) FROM process_training WHERE process_code = ?",
            (process.code,),
        )
        if trained == 0:
            out.append(f"프로세스 {process.code}: 프로세스 교육 기록이 없습니다.")
    return out


def _ctl_040(db: Database, as_of: str | None) -> list[str]:
    """품질방침 필수 주제 (5.2.1, 5.2.3)."""
    row = db.one(
        "SELECT * FROM governance_record WHERE kind = 'quality_policy' "
        "ORDER BY ref_year DESC LIMIT 1"
    )
    if row is None:
        return ["문서화된 품질방침이 없습니다."]
    payload = json.loads(row["payload"])
    missing = [t for t in POLICY_TOPICS if not payload.get(t)]
    return [f"품질방침 누락 주제: {', '.join(missing)}"] if missing else []


def _ctl_031(db: Database, as_of: str | None) -> list[str]:
    """공정·생산 정지 권한을 가진 독립 대표자 (5.3.1 d)."""
    rows = db.query("SELECT * FROM stop_authority")
    if not rows:
        return ["공정·생산 정지 권한을 가진 독립 대표자가 임명되지 않았습니다."]
    out = []
    for row in rows:
        person = db.fetch("person", int(row["person_id"]))
        if person["department"] == row["independent_of"]:
            out.append(
                f"{person['name']}: 정지 대상 조직({row['independent_of']})과 동일 소속이므로"
                " 독립성이 확보되지 않았습니다."
            )
    return out


def _ctl_041(db: Database, as_of: str | None) -> list[str]:
    """최고경영자 지정 KPI 존재 (5.3.1 a, 9.1.1.1.1)."""
    registry = load_registry()
    if not registry.kpis():
        return ["RQMS 운영·통제를 위한 KPI 가 지정되지 않았습니다(5.3.1 a)."]
    out = []
    for kpi in registry.kpis():
        if not db.one(
            "SELECT 1 FROM indicator_measurement WHERE indicator_code = ? LIMIT 1",
            (kpi.code,),
        ):
            out.append(f"KPI {kpi.code}: 측정 기록이 없습니다.")
    return out


def _ctl_042(db: Database, as_of: str | None) -> list[str]:
    """리스크·기회 정기 검토 및 효과성 평가 (6.1.3.1)."""
    out = []
    if not db.one("SELECT 1 FROM risk_entry LIMIT 1"):
        out.append("리스크·기회 등록부가 비어 있습니다.")
    for row in risk.overdue_reviews(db, as_of=as_of):
        out.append(f"{row['ref_no']}: 정기 검토 기한 경과(최근 {row['reviewed_on']}).")
    for row in db.query(
        "SELECT * FROM risk_entry WHERE status = 'closed' "
        "AND TRIM(effectiveness_note) = ''"
    ):
        out.append(f"{row['ref_no']}: 종결되었으나 조치 효과성 평가가 없습니다.")
    return out


def _ctl_043(db: Database, as_of: str | None) -> list[str]:
    """품질목표 측정가능·달성기획 (6.2)."""
    rows = db.query("SELECT * FROM quality_objective")
    if not rows:
        return ["품질목표가 수립되지 않았습니다."]
    out = []
    for row in rows:
        if row["target_value"] is None:
            out.append(f"품질목표 {row['code']}: 측정 가능한 목표값이 없습니다(6.2.1 b).")
        for field, label in (
            ("resources", "자원"),
            ("responsible_id", "책임자"),
            ("due_on", "기한"),
            ("evaluation_method", "평가방법"),
        ):
            if not row[field]:
                out.append(f"품질목표 {row['code']}: {label} 미정의(6.2.2).")
    if not any(row["safety_related"] for row in rows):
        out.append("안전 목표가 수립되지 않았습니다(9.3.3.1 a).")
    return out


def _ctl_034(db: Database, as_of: str | None) -> list[str]:
    """사업연속성 계획 (6.1.4)."""
    row = db.one(
        "SELECT * FROM governance_record WHERE kind = 'business_continuity_plan' "
        "ORDER BY ref_year DESC LIMIT 1"
    )
    if row is None:
        return ["사업연속성 계획이 수립되지 않았습니다."]
    out = []
    if not row["verified_on"]:
        out.append("사업연속성 계획의 검증(예: 주기적 시험) 기록이 없습니다(6.1.4 a).")
    if not row["reviewed_on"] or is_past(add_months(row["reviewed_on"], 12), as_of=as_of):
        out.append(f"사업연속성 계획 정기 검토 기한 경과(최근 {row['reviewed_on']}).")
    payload = json.loads(row["payload"])
    if not payload.get("responsibilities"):
        out.append("사업연속성 조치 책임이 정의되지 않았습니다(6.1.4 c).")
    return out


# ------------------------------------------------------------------------ 7장
def _ctl_003(db: Database, as_of: str | None) -> list[str]:
    """기록 보존기간 정의 및 만료 전 폐기 금지 (7.5.3.2, 7.5.3.3 d)."""
    out = []
    for row in db.query("SELECT * FROM document WHERE doc_type = 'record'"):
        if not row["record_type"] or not row["retention_months"]:
            out.append(f"기록 {row['doc_no']}: 기록 유형·보존기간 미정의.")
            continue
        if row["disposed_on"]:
            expiry = documents.retention_expiry(row)
            if expiry and not is_past(expiry, as_of=row["disposed_on"]):
                out.append(
                    f"기록 {row['doc_no']}: 보존기간 만료({expiry}) 전"
                    f" {row['disposed_on']} 에 폐기되었습니다."
                )
    return out


def _ctl_025_state(db: Database, as_of: str | None) -> list[str]:
    """교정 상태 점검 (7.1.5) — invariant 보완용 상태 리포트."""
    out = []
    for row in db.query("SELECT * FROM measuring_resource"):
        if row["status"] in ("overdue", "unfit"):
            out.append(f"측정자원 {row['ident']}: 상태 {row['status']}.")
        elif is_past(row["next_due_on"], as_of=as_of):
            out.append(f"측정자원 {row['ident']}: 교정 기한 {row['next_due_on']} 경과.")
    for row in calibration.unfit_without_impact_assessment(db):
        out.append(
            f"교정기록 {row['id']}: 부적합 판정 후 소급 영향평가가 없습니다(7.1.5.2)."
        )
    return out


def _ctl_013(db: Database, as_of: str | None) -> list[str]:
    """검증 위임 등록부 및 동의 증거 (8.4.2.2)."""
    out = [
        f"위임 {row['id']}: 공급자 동의 증거가 없습니다."
        for row in suppliers.delegations_without_evidence(db)
    ]
    for row in db.query("SELECT * FROM verification_delegation"):
        if not (row["control_measure"] or "").strip():
            out.append(f"위임 {row['id']}: 통제수단(예: 정기 심사)이 정의되지 않았습니다.")
    return out


# ------------------------------------------------------------------------ 8장
def _ctl_044(db: Database, as_of: str | None) -> list[str]:
    """프로젝트 필수 계획서 (8.1.3.2, .6, .7, .8)."""
    out = []
    for project in db.query("SELECT * FROM project WHERE status = 'active'"):
        missing = projects.missing_plans(db, project["code"])
        if missing:
            out.append(f"{project['code']}: 누락 계획서 {', '.join(missing)}")
    return out


def _ctl_045(db: Database, as_of: str | None) -> list[str]:
    """프로젝트 정기 검토 (8.1.3.11)."""
    return [
        f"{p['code']}: 정기 프로젝트 검토 기한 경과 또는 미실시."
        for p in projects.overdue_project_reviews(db, as_of=as_of)
    ]


def _ctl_007(db: Database, as_of: str | None) -> list[str]:
    """안전관련 형상항목 식별 (8.1.4.1.1 c)."""
    out = [
        f"형상항목 {row['part_no']}: 안전관련이나 추적성 식별 기준이 없습니다."
        for row in configuration.safety_items_without_traceability(db)
    ]
    for project in db.query("SELECT * FROM project WHERE safety_related = 1"):
        count = db.count(
            "SELECT COUNT(*) FROM config_item WHERE project_id = ? AND safety_related = 1",
            (project["id"],),
        )
        if count == 0:
            out.append(
                f"{project['code']}: 안전관련 프로젝트이나 안전관련 형상항목이"
                " 식별되지 않았습니다."
            )
    return out


def _ctl_046(db: Database, as_of: str | None) -> list[str]:
    """요구사항 기술규격 문서화 (8.2.2.1.1, 8.2.5)."""
    out = []
    for row in db.query("SELECT * FROM requirement WHERE reviewed = 1"):
        if row["spec_doc_id"] is None:
            out.append(f"요구사항 {row['req_no']}: 기술규격 문서화가 누락되었습니다.")
    for row in db.query("SELECT * FROM requirement WHERE reviewed = 0"):
        out.append(f"요구사항 {row['req_no']}: 조항별 검토가 완료되지 않았습니다.")
    return out


def _ctl_048(db: Database, as_of: str | None) -> list[str]:
    """외부공급자 분류·평가·성과감시 (8.4.1.1.2, .3, 8.4.2.3)."""
    out = []
    for row in suppliers.stale_classifications(db, as_of=as_of):
        out.append(f"공급자 {row['code']}: 분류 재검토 기한 경과 또는 미분류.")
    for row in db.query("SELECT * FROM supplier WHERE evaluated_on IS NULL"):
        out.append(f"공급자 {row['code']}: 평가 기록이 없습니다(8.4.1.1.3).")
    for row in suppliers.key_suppliers_without_performance_review(db, as_of=as_of):
        out.append(f"핵심 공급자 {row['code']}: 성과검토 기한 경과 또는 미실시.")
    return out


def _ctl_049(db: Database, as_of: str | None) -> list[str]:
    """발주 확인서 및 요구사항 전달 (8.4.3.1, 8.4.4)."""
    return [
        f"발주 {row['po_no']}: 공급자 확인서를 수령하지 못했습니다(8.4.4 a)."
        for row in suppliers.unacknowledged_orders(db)
    ]


def _ctl_011_state(db: Database, as_of: str | None) -> list[str]:
    """승인되지 않은 공급자에 대한 발주 상태 점검 (8.4.1.1.4)."""
    return [
        f"발주 {row['po_no']}: 공급자 {row['supplier_code']} 가 승인되지 않았습니다."
        for row in suppliers.unapproved_with_orders(db)
    ]


def _ctl_050(db: Database, as_of: str | None) -> list[str]:
    """승인된 생산데이터·관리된 조건 (8.5.1.1.2, .3, 8.5.1.2.1)."""
    out = []
    for row in db.query(
        "SELECT * FROM production_order WHERE status IN ('in_progress','released')"
    ):
        if row["approved_data_doc_id"] is None:
            out.append(f"생산오더 {row['order_no']}: 승인된 생산데이터가 없습니다.")
        if row["process_verified_on"] is None:
            out.append(f"생산오더 {row['order_no']}: 공정 검증(8.5.1.1.3) 미완료.")
        if not (row["scheduled_start_on"] and row["scheduled_finish_on"]):
            out.append(f"생산오더 {row['order_no']}: 생산 일정계획이 없습니다(8.5.1.2.1).")
    return out


def _ctl_051(db: Database, as_of: str | None) -> list[str]:
    """생산설비 식별·정비·검증 (8.5.1.4.1)."""
    out = []
    for row in production.equipment_due(db, as_of=as_of):
        if not row["validated_before_first_use_on"]:
            out.append(f"설비 {row['ident']}: 최초 사용 전 유효성확인이 없습니다.")
        else:
            out.append(f"설비 {row['ident']}: 재검증 기한 {row['next_verification_on']} 경과.")
    for row in db.query("SELECT * FROM production_equipment WHERE TRIM(preventive_plan) = ''"):
        out.append(f"설비 {row['ident']}: 예방정비 계획이 없습니다(8.5.1.4.1 b).")
    return out


def _ctl_032(db: Database, as_of: str | None) -> list[str]:
    """보증종료까지 추적성 유지 (8.5.2.1)."""
    out = [
        f"품목 {row['serial_no']}: 추적성 정보가 불완전합니다."
        for row in production.traceability_gaps(db, as_of=as_of)
    ]
    for row in db.query("SELECT * FROM traceable_item WHERE status = 'unknown'"):
        out.append(f"품목 {row['serial_no']}: 상태 불명 — 부적합품으로 관리해야 합니다.")
    return out


def _ctl_052(db: Database, as_of: str | None) -> list[str]:
    """보존 규격 및 고객 소유물 추적성 (8.5.3.1, 8.5.4.1)."""
    out = []
    if not db.one("SELECT 1 FROM preservation_spec LIMIT 1"):
        out.append("문서화된 보존 규격이 없습니다(8.5.4.1).")
    for row in db.query(
        "SELECT * FROM external_property WHERE status IN ('lost','damaged') "
        "AND (reported_on IS NULL OR TRIM(cause_analysis) = '')"
    ):
        out.append(
            f"소유물 {row['ref_no']}: 분실·손상 보고 또는 원인분석이 누락되었습니다."
        )
    return out


def _ctl_059(db: Database, as_of: str | None) -> list[str]:
    """인도 후 활동 기술문서·수리지침 (8.5.5.1)."""
    out = [
        f"인도 후 활동 {row['ref_no']}: 승인된 수리지침이 없습니다."
        for row in post_delivery.repairs_without_instruction(db)
    ]
    out += [
        f"인도 후 활동 {row['ref_no']}: RQMS 환류 기록이 없습니다."
        for row in post_delivery.activities_without_feedback(db)
    ]
    return out


def _ctl_057(db: Database, as_of: str | None) -> list[str]:
    """안전표준 식별 및 안전 케이스 (8.3.1.1, 8.8.3)."""
    out = []
    for row in db.query("SELECT * FROM design WHERE safety_related = 1"):
        if not (row["safety_standard"] or "").strip():
            out.append(f"설계 {row['design_no']}: 적용 안전표준이 식별되지 않았습니다.")
        if row["output_released_on"] and row["safety_case_doc_id"] is None:
            out.append(f"설계 {row['design_no']}: 안전 케이스 없이 출력이 출시되었습니다.")
    for row in db.query("SELECT * FROM safety_record WHERE TRIM(hazard_log) = ''"):
        out.append(f"안전기록 {row['product']}: 위험원 기록이 없습니다.")
    return out


def _ctl_030(db: Database, as_of: str | None) -> list[str]:
    """단산 리스크 평가 및 관리계획 검토 (8.10)."""
    out = []
    if not db.one("SELECT 1 FROM obsolescence_plan LIMIT 1"):
        out.append("단산 관리계획이 수립되지 않았습니다(8.10 b).")
    for row in obsolescence.plans_due_for_review(db, as_of=as_of):
        out.append(f"단산 관리계획 {row['product']}: 정기 검토 기한 경과.")
    for row in obsolescence.open_high_risks(db):
        if not row["customer_communicated_on"]:
            out.append(
                f"단산 리스크 {row['part_no']}: 고위험이나 고객 의사소통이 없습니다(8.10 c)."
            )
    return out


def _ctl_018_state(db: Database, as_of: str | None) -> list[str]:
    """특채 유효기간 상태 점검 (8.7.3 e, f)."""
    out = []
    for row in db.query("SELECT * FROM concession WHERE status = 'open'"):
        if is_past(row["valid_until"], as_of=as_of):
            out.append(
                f"특채 {row['concession_no']}: 유효기간 {row['valid_until']} 만료 —"
                " 제품을 더 이상 사용할 수 없습니다."
            )
    return out


# ------------------------------------------------------------------------ 9장
def _ctl_021(db: Database, as_of: str | None) -> list[str]:
    """3년 심사 커버리지 (9.2.3.1, 9.2.3.2)."""
    out = []
    for gap in audit.coverage_gaps(db, as_of=as_of):
        if gap["last_audit"] is None:
            out.append(f"프로세스 {gap['process']}: 내부심사 실적이 없습니다.")
        else:
            out.append(
                f"프로세스 {gap['process']}: 최근 심사 {gap['last_audit']}"
                f" ({gap['years']}년 경과) — 3년 주기 초과."
            )
    out += [
        f"심사 발견사항 {row['id']}: {row['grade']} 등급이나 시정조치가 없습니다."
        for row in audit.findings_without_capa(db)
    ]
    return out


def _ctl_022(db: Database, as_of: str | None) -> list[str]:
    """자기업무 심사 금지 (9.2.2 c, 9.2.3.2 d)."""
    out = []
    for row in db.query("SELECT * FROM internal_audit WHERE process_code IS NOT NULL"):
        auditor_row = db.find("auditor", person_id=row["lead_auditor_id"])
        if auditor_row is None:
            out.append(f"심사 {row['audit_no']}: 선임심사원이 심사원 명부에 없습니다.")
            continue
        home = {
            p.strip() for p in (auditor_row["home_processes"] or "").split(",") if p.strip()
        }
        if row["process_code"] in home:
            person = db.fetch("person", int(row["lead_auditor_id"]))
            out.append(
                f"심사 {row['audit_no']}: {person['name']} 이 소속 프로세스"
                f" {row['process_code']} 를 심사했습니다."
            )
    return out


def _ctl_055(db: Database, as_of: str | None) -> list[str]:
    """심사팀 역량 요건 (9.2.3.3.1)."""
    rows = db.query("SELECT * FROM auditor")
    if not rows:
        return ["등록된 내부심사원이 없습니다(9.2.3.3.2 c)."]
    out = []
    for row in rows:
        person = db.fetch("person", int(row["person_id"]))
        if not row["knows_audit_principles"]:
            out.append(f"심사원 {person['name']}: 심사원칙 지식이 확인되지 않았습니다.")
        for field, label in (
            ("scope_knowledge", "심사범위"),
            ("clause_knowledge", "해당 조항"),
            ("criteria_knowledge", "심사기준"),
        ):
            if not (row[field] or "").strip():
                out.append(f"심사원 {person['name']}: {label} 지식 미확인.")
        if int(row["audits_performed"]) < audit.MIN_AUDITS_PERFORMED:
            out.append(
                f"심사원 {person['name']}: 심사 경험 부족"
                f"({row['audits_performed']}건 < {audit.MIN_AUDITS_PERFORMED}건)."
            )
        if not row["refresh_training_on"] or is_past(
            add_months(row["refresh_training_on"], 24), as_of=as_of
        ):
            out.append(f"심사원 {person['name']}: 정기 보수교육 기한 경과.")
    return out


def _ctl_056(db: Database, as_of: str | None) -> list[str]:
    """PI 정의 완비 (9.1.1.1.1 a~g)."""
    out = [
        f"지표 {item['code']}: 정의 누락 항목 {', '.join(item['missing'])}"  # type: ignore[arg-type]
        for item in indicators.incomplete_definitions()
    ]
    registry = load_registry()
    for process in registry.processes:
        if not registry.indicators_for_process(process.code):
            out.append(f"프로세스 {process.code}: 성과지표가 정의되지 않았습니다(4.4.1 c).")
    return out


def _ctl_020(db: Database, as_of: str | None) -> list[str]:
    """KPI 목표 미달 시 시정조치 (9.1.3.1, 9.3.3.1)."""
    out = []
    for row in indicators.unmet_kpi_measurements(db):
        if row["capa_id"] is None:
            out.append(
                f"KPI {row['indicator_code']}/{row['period']}: 목표 미달이나 시정조치가"
                " 없습니다."
            )
    for row in db.query("SELECT * FROM quality_objective WHERE achieved = 0"):
        linked = db.one(
            "SELECT 1 FROM capa WHERE source_ref = ? LIMIT 1", (row["code"],)
        )
        if linked is None:
            out.append(f"품질목표 {row['code']}: 미달이나 시정조치가 없습니다(9.3.3.1).")
    return out


def _ctl_053(db: Database, as_of: str | None) -> list[str]:
    """고객 불만 접수통보·시정조치 연계 (9.1.2.1)."""
    out = [
        f"불만 {row['complaint_no']}: 접수 통보가 없습니다."
        for row in customer.unacknowledged_complaints(db)
    ]
    out += [
        f"불만 {row['complaint_no']}: 시정조치 연계가 없습니다."
        for row in customer.complaints_without_capa(db)
    ]
    return out


def _ctl_023(db: Database, as_of: str | None) -> list[str]:
    """경영검토 주기 (9.3.1.1)."""
    out = []
    overdue = review.overdue_management_review(db, as_of=as_of)
    if overdue == "never":
        out.append("경영검토 실시 기록이 없습니다.")
    elif overdue:
        out.append(f"연간 경영검토 기한 경과(최근 실시 {overdue}).")
    for row in db.query("SELECT * FROM nonconformity WHERE safety_impact = 1"):
        linked = db.one(
            "SELECT 1 FROM management_review WHERE review_kind = 'extraordinary' "
            "AND trigger LIKE ? LIMIT 1",
            (f"%{row['nc_no']}%",),
        )
        if linked is None:
            out.append(
                f"안전영향 부적합 {row['nc_no']}: 추가 경영검토가 실시되지 않았습니다"
                " (9.3.1.1)."
            )
    return out


def _ctl_054(db: Database, as_of: str | None) -> list[str]:
    """경영검토 입력 완비 (9.3.2, 9.3.2.1)."""
    row = db.one("SELECT * FROM management_review ORDER BY held_on DESC LIMIT 1")
    if row is None:
        return ["경영검토 기록이 없습니다."]
    inputs = json.loads(row["inputs"])
    required = review.MR_INPUTS_ISO9001 + review.MR_INPUTS_SUPPLEMENTAL
    missing = [k for k in required if not inputs.get(k)]
    out = []
    if missing:
        out.append(f"경영검토 {row['ref_no']} 입력 누락: {', '.join(missing)}")
    outputs = json.loads(row["outputs"])
    missing_out = [k for k in review.MR_OUTPUTS if not outputs.get(k)]
    if missing_out:
        out.append(f"경영검토 {row['ref_no']} 출력 누락: {', '.join(missing_out)}")
    return out


def _ctl_024(db: Database, as_of: str | None) -> list[str]:
    """프로세스 검토 주기 (9.4)."""
    out = []
    for item in review.overdue_process_reviews(db, as_of=as_of):
        label = "필수" if str(item["obligation"]).startswith("mandatory") else "권고"
        if item["last_review"] is None:
            out.append(f"프로세스 {item['process']}({label}): 프로세스 검토 실적이 없습니다.")
        else:
            out.append(
                f"프로세스 {item['process']}({label}): 최근 검토 {item['last_review']} —"
                f" {item['cycle_months']}개월 주기 초과."
            )
    return out


# --------------------------------------------------------- 무결성 / 변경 / 역량
def _ctl_002_state(db: Database, as_of: str | None) -> list[str]:
    """승인 기록 무결성 봉인 (7.5.3.2)."""
    return [
        f"문서 {row['doc_no']} v{row['version']}: 무결성 봉인 불일치(무단 변경 의심)."
        for row in documents.broken_seals(db)
    ]


def _ctl_027_state(db: Database, as_of: str | None) -> list[str]:
    """변경 실행 후 검증 (8.1.4.2 j)."""
    return [
        f"변경 {row['change_no']}: 실행되었으나 실행 검증이 없습니다."
        for row in change.unverified_implementations(db)
    ]


def _ctl_026_state(db: Database, as_of: str | None) -> list[str]:
    """역량 갭 조치 (7.2.1.1 b, c)."""
    out = []
    for row in competence.open_gaps(db):
        person = db.fetch("person", int(row["person_id"]))
        if not (row["action"] or "").strip():
            out.append(
                f"{person['name']}/{row['competence_code']}: 역량 갭 조치가 계획되지"
                " 않았습니다."
            )
        elif is_past(row["due_on"], as_of=as_of):
            out.append(
                f"{person['name']}/{row['competence_code']}: 역량 갭 조치 기한"
                f" {row['due_on']} 경과."
            )
    return out


def _ctl_033_state(db: Database, as_of: str | None) -> list[str]:
    """시정조치 평가·감시 (10.2.1, 10.2.3 d)."""
    out = []
    for row in db.query("SELECT * FROM nonconformity WHERE capa_needed IS NULL"):
        out.append(f"부적합 {row['nc_no']}: 시정조치 필요성 평가가 없습니다(10.2.3 b).")
    for row in db.query(
        "SELECT * FROM nonconformity WHERE capa_needed = 1 AND capa_id IS NULL"
    ):
        out.append(f"부적합 {row['nc_no']}: 시정조치가 필요하나 연결되지 않았습니다.")
    for row in db.query(
        "SELECT * FROM capa WHERE status = 'closed' AND effectiveness_reviewed_on IS NULL"
    ):
        out.append(f"시정조치 {row['capa_no']}: 종결되었으나 효과성 검토가 없습니다.")
    return out


def _ctl_016_state(db: Database, as_of: str | None) -> list[str]:
    """FAI 선행 요건 상태 점검 (8.9.3)."""
    out = []
    for row in db.query(
        "SELECT * FROM production_order WHERE serial_production_released_on IS NOT NULL"
    ):
        if row["fai_id"] is None:
            out.append(f"생산오더 {row['order_no']}: FAI 없이 양산이 출시되었습니다.")
    for row in db.query(
        "SELECT * FROM purchase_order WHERE is_new_or_modified = 1"
    ):
        released = db.find("eppps_release", po_id=row["id"])
        if released is None:
            out.append(f"발주 {row['po_no']}: 신규/변경 EPPPS 출시 승인 기록이 없습니다.")
    return out


def _ctl_017_state(db: Database, as_of: str | None) -> list[str]:
    """출하 권한·증거 상태 점검 (8.6)."""
    return [
        f"출하기록 {row['id']}: 출하 권한자 또는 적합성 증거가 없습니다."
        for row in nonconformity_release_gaps(db)
    ]


def nonconformity_release_gaps(db: Database) -> list[Any]:
    from .services import release

    return release.released_without_authority(db)


#: 통제 ID -> 점검 함수
CHECKS: dict[str, CheckFn] = {
    "CTL-002": _ctl_002_state,
    "CTL-003": _ctl_003,
    "CTL-007": _ctl_007,
    "CTL-011": _ctl_011_state,
    "CTL-013": _ctl_013,
    "CTL-016": _ctl_016_state,
    "CTL-017": _ctl_017_state,
    "CTL-018": _ctl_018_state,
    "CTL-020": _ctl_020,
    "CTL-021": _ctl_021,
    "CTL-022": _ctl_022,
    "CTL-023": _ctl_023,
    "CTL-024": _ctl_024,
    "CTL-025": _ctl_025_state,
    "CTL-026": _ctl_026_state,
    "CTL-027": _ctl_027_state,
    "CTL-030": _ctl_030,
    "CTL-031": _ctl_031,
    "CTL-032": _ctl_032,
    "CTL-033": _ctl_033_state,
    "CTL-034": _ctl_034,
    "CTL-036": _ctl_036,
    "CTL-037": _ctl_037,
    "CTL-038": _ctl_038,
    "CTL-039": _ctl_039,
    "CTL-040": _ctl_040,
    "CTL-041": _ctl_041,
    "CTL-042": _ctl_042,
    "CTL-043": _ctl_043,
    "CTL-044": _ctl_044,
    "CTL-045": _ctl_045,
    "CTL-046": _ctl_046,
    "CTL-048": _ctl_048,
    "CTL-049": _ctl_049,
    "CTL-050": _ctl_050,
    "CTL-051": _ctl_051,
    "CTL-052": _ctl_052,
    "CTL-053": _ctl_053,
    "CTL-054": _ctl_054,
    "CTL-055": _ctl_055,
    "CTL-056": _ctl_056,
    "CTL-057": _ctl_057,
    "CTL-059": _ctl_059,
}


def run_checks(
    db: Database, *, as_of: str | None = None, control_ids: list[str] | None = None
) -> list[Finding]:
    """등록된 상태 점검을 실행하여 위반 목록을 반환한다."""
    registry = load_registry()
    findings: list[Finding] = []
    targets = control_ids or sorted(CHECKS)
    for control_id in targets:
        check = CHECKS.get(control_id)
        if check is None:
            continue
        control = registry.control(control_id)
        for detail in check(db, as_of):
            findings.append(
                Finding(
                    control_id=control_id,
                    severity=control.severity,
                    title=control.title,
                    clauses=control.clauses,
                    detail=detail,
                )
            )
    return findings


def unchecked_audit_controls() -> list[str]:
    """kind=audit 이지만 점검 함수가 없는 통제 — 시스템 자체의 갭이다."""
    registry = load_registry()
    return [c.id for c in registry.controls_by_kind("audit") if c.id not in CHECKS]


def summary(findings: list[Finding]) -> dict[str, object]:
    """점검 결과 요약."""
    by_control: dict[str, int] = {}
    for finding in findings:
        by_control[finding.control_id] = by_control.get(finding.control_id, 0) + 1
    return {
        "as_of": today(),
        "total": len(findings),
        "major": sum(1 for f in findings if f.severity == "major"),
        "minor": sum(1 for f in findings if f.severity == "minor"),
        "controls_violated": len(by_control),
        "by_control": dict(sorted(by_control.items())),
    }
