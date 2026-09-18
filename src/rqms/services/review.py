"""경영검토 (9.3) 및 프로세스 검토 (9.4).

강제 통제
    CTL-023  경영검토 연 1회 이상 + 중대 품질사고 시 추가 경영검토 (9.3.1.1)
    CTL-024  필수 프로세스는 연 1회 프로세스 검토 실시 (9.4)
    CTL-054  경영검토 입력이 9.3.2 및 9.3.2.1 항목을 모두 포함 (9.3.2, 9.3.2.1)
    CTL-020  목표 미달 시 시정조치 (9.3.3.1)
"""

from __future__ import annotations

import json

from ..db import Database, today
from ..standard import load_registry
from . import capa
from ._base import add_months, enforce, is_past, parse_date

#: 9.3.2 a)~f) 경영검토 입력 (ISO 9001)
MR_INPUTS_ISO9001 = (
    "previous_actions_status",
    "context_changes",
    "customer_satisfaction_and_feedback",
    "quality_objectives_achievement",
    "process_performance_and_conformity",
    "nonconformities_and_corrective_actions",
    "monitoring_and_measurement_results",
    "audit_results",
    "external_provider_performance",
    "resource_adequacy",
    "risk_action_effectiveness",
    "improvement_opportunities",
)

#: 9.3.2.1 a)~e) 철도 부문 추가 입력
MR_INPUTS_SUPPLEMENTAL = (
    "project_review_key_issues",
    "process_review_results",
    "kpi_and_pi_analysis",
    "internal_external_failure_safety_impact",
    "business_planning_outputs",
)

#: 9.3.3 a)~c) + 9.3.3.1 a), b) 경영검토 출력
MR_OUTPUTS = (
    "improvement_opportunities",
    "qms_changes",
    "resource_needs",
    "objectives_achievement",
    "customer_satisfaction",
)

#: 9.4 a)~g), i)~l) 프로세스 검토 출력
PROCESS_REVIEW_FIELDS = (
    "conformity_note",
    "previous_actions",
    "nonconforming_outputs",
    "resources_note",
    "pi_analysis",
    "pi_relevance_note",
    "audit_capa_note",
    "interested_party_input",
    "decisions",
)


# --------------------------------------------------------------- 9.3 경영검토
def hold_management_review(
    db: Database,
    *,
    ref_no: str,
    inputs: dict[str, str],
    outputs: dict[str, str],
    attendees: str,
    doc_id: int | None = None,
    review_kind: str = "annual",
    trigger: str = "",
) -> int:
    """경영검토를 실시한다 (9.3.1.1, 9.3.2, 9.3.2.1, 9.3.3, 9.3.3.1).

    입력은 9.3.2 와 9.3.2.1 항목을 모두 포함해야 하고, 출력은 9.3.3 과 9.3.3.1
    항목을 포함해야 한다.
    """
    if review_kind not in ("annual", "extraordinary"):
        raise ValueError("review_kind 는 annual 또는 extraordinary 여야 합니다.")
    required_inputs = MR_INPUTS_ISO9001 + MR_INPUTS_SUPPLEMENTAL
    missing_inputs = [k for k in required_inputs if not inputs.get(k)]
    enforce(
        "CTL-054",
        not missing_inputs,
        f"경영검토 {ref_no} 입력 누락 항목(9.3.2 / 9.3.2.1): {', '.join(missing_inputs)}",
        db=db,
        context=f"management_review:{ref_no}",
    )
    missing_outputs = [k for k in MR_OUTPUTS if not outputs.get(k)]
    enforce(
        "CTL-023",
        not missing_outputs,
        f"경영검토 {ref_no} 출력 누락 항목(9.3.3 / 9.3.3.1): {', '.join(missing_outputs)}",
        db=db,
        context=f"management_review:{ref_no}",
    )
    if review_kind == "extraordinary":
        enforce(
            "CTL-023",
            bool(trigger.strip()),
            f"경영검토 {ref_no}: 추가 경영검토의 사유(중대 품질사고·RQMS 중대변경)를"
            " 기록해야 합니다(9.3.1.1).",
            db=db,
            context=f"management_review:{ref_no}",
        )

    # 9.3.3.1 — 목표 미달 시 시정조치가 등록되어 있어야 한다.
    for objective in db.query(
        "SELECT * FROM quality_objective WHERE achieved = 0"
    ):
        capa.require_capa_for(
            db,
            source_type="management_review",
            source_ref=objective["code"],
            control_id="CTL-020",
            purpose=f"품질목표 {objective['code']} 미달",
        )

    return db.insert(
        "management_review",
        ref_no=ref_no,
        review_kind=review_kind,
        trigger=trigger,
        held_on=today(),
        attendees=attendees,
        inputs=json.dumps(inputs, ensure_ascii=False),
        outputs=json.dumps(outputs, ensure_ascii=False),
        doc_id=doc_id,
    )


def assert_annual_review(db: Database, *, as_of: str | None = None) -> None:
    """연 1회 경영검토 실시를 확인한다 (9.3.1.1, CTL-023)."""
    last = db.scalar(
        "SELECT MAX(held_on) FROM management_review WHERE review_kind = 'annual'"
    )
    enforce(
        "CTL-023",
        last is not None and not is_past(add_months(last, 12), as_of=as_of),
        "연 1회 경영검토가 실시되지 않았습니다(9.3.1.1)."
        + (f" 최근 실시: {last}" if last else " 실시 기록 없음."),
        db=db,
        context="management_review",
    )


def require_extraordinary_review(
    db: Database, *, incident_ref: str, as_of: str | None = None
) -> None:
    """중대 품질사고 발생 시 추가 경영검토 실시를 확인한다 (9.3.1.1)."""
    rows = db.query(
        "SELECT * FROM management_review WHERE review_kind = 'extraordinary' "
        "AND trigger LIKE ?",
        (f"%{incident_ref}%",),
    )
    enforce(
        "CTL-023",
        bool(rows),
        f"중대 품질사고 {incident_ref} 에 대한 추가 경영검토가 실시되지 않았습니다"
        " (9.3.1.1).",
        db=db,
        context=f"management_review:{incident_ref}",
    )


def overdue_management_review(db: Database, *, as_of: str | None = None) -> str | None:
    """연간 경영검토 기한 초과 여부. 초과 시 마지막 실시일(또는 None)을 돌려준다."""
    last = db.scalar(
        "SELECT MAX(held_on) FROM management_review WHERE review_kind = 'annual'"
    )
    if last is None:
        return "never"
    return last if is_past(add_months(last, 12), as_of=as_of) else None


# ------------------------------------------------------------ 9.4 프로세스 검토
def hold_process_review(
    db: Database,
    *,
    process_code: str,
    owner_id: int,
    participants: str,
    fields: dict[str, str],
    reported_to_top_management: bool,
    doc_id: int | None = None,
) -> int:
    """프로세스 검토를 실시한다 (9.4 a~l).

    프로세스 오너가 주재해야 하고(h), 내부 이해관계자 대표가 참여해야 하며,
    결과는 최고경영자에게 보고되어야 한다(k).
    """
    process = load_registry().process(process_code)
    registered = db.find("process_instance", code=process_code)
    enforce(
        "CTL-024",
        registered is not None,
        f"프로세스 {process_code}: 등록되지 않은 프로세스는 검토할 수 없습니다(4.4.3).",
        db=db,
        context=f"process_review:{process_code}",
    )
    assert registered is not None
    enforce(
        "CTL-024",
        int(registered["owner_id"] or 0) == owner_id,
        f"프로세스 {process_code}: 프로세스 오너가 검토를 주재해야 합니다(9.4 h).",
        db=db,
        context=f"process_review:{process_code}",
    )
    enforce(
        "CTL-024",
        bool(participants.strip()),
        f"프로세스 {process_code}: 내부 이해관계자 대표가 참여해야 합니다(9.4 h).",
        db=db,
        context=f"process_review:{process_code}",
    )
    missing = [k for k in PROCESS_REVIEW_FIELDS if not fields.get(k)]
    enforce(
        "CTL-024",
        not missing,
        f"프로세스 {process_code} 검토 누락 항목(9.4): {', '.join(missing)}",
        db=db,
        context=f"process_review:{process_code}",
    )
    enforce(
        "CTL-024",
        reported_to_top_management,
        f"프로세스 {process_code}: 검토 출력은 최고경영자에게 보고되어야 합니다(9.4 k).",
        db=db,
        context=f"process_review:{process_code}",
    )
    return db.insert(
        "process_review",
        process_code=process.code,
        held_on=today(),
        owner_id=owner_id,
        participants=participants,
        reported_to_top_management=int(reported_to_top_management),
        doc_id=doc_id,
        **{k: fields[k] for k in PROCESS_REVIEW_FIELDS},
    )


def overdue_process_reviews(db: Database, *, as_of: str | None = None) -> list[dict[str, object]]:
    """검토 주기를 초과한 프로세스 (9.4, CTL-024).

    필수 프로세스는 연 1회, 권고 프로세스는 등록된 주기에 따른다.
    """
    reference = parse_date(as_of or today())
    out: list[dict[str, object]] = []
    for process in load_registry().processes:
        registered = db.find("process_instance", code=process.code)
        if registered is not None and not registered["applicable"]:
            continue
        last = db.scalar(
            "SELECT MAX(held_on) FROM process_review WHERE process_code = ?",
            (process.code,),
        )
        if last is None:
            out.append(
                {
                    "process": process.code,
                    "obligation": process.obligation,
                    "last_review": None,
                    "cycle_months": process.review_cycle_months,
                }
            )
            continue
        due = parse_date(add_months(last, process.review_cycle_months))
        if due < reference:
            out.append(
                {
                    "process": process.code,
                    "obligation": process.obligation,
                    "last_review": last,
                    "cycle_months": process.review_cycle_months,
                }
            )
    return out


def assert_process_reviews_current(db: Database, *, as_of: str | None = None) -> None:
    """필수 프로세스의 연간 검토 이행을 강제한다 (CTL-024)."""
    overdue = [
        item
        for item in overdue_process_reviews(db, as_of=as_of)
        if str(item["obligation"]).startswith("mandatory")
    ]
    enforce(
        "CTL-024",
        not overdue,
        "연간 프로세스 검토가 이행되지 않은 필수 프로세스: "
        + ", ".join(str(i["process"]) for i in overdue),
        db=db,
        context="process_review",
    )


def management_review_inputs_snapshot(db: Database) -> dict[str, str]:
    """시스템 데이터로부터 경영검토 입력 초안을 생성한다 (9.3.2, 9.3.2.1).

    실제 검토에서는 이 초안을 근거로 경영진이 판단을 기술한다.
    """
    open_capa = db.count("SELECT COUNT(*) FROM capa WHERE status != 'closed'")
    unmet = db.count("SELECT COUNT(*) FROM indicator_measurement WHERE met = 0")
    audits = db.count(
        "SELECT COUNT(*) FROM internal_audit WHERE performed_on IS NOT NULL"
    )
    findings = db.count("SELECT COUNT(*) FROM audit_finding")
    safety_ncs = db.count("SELECT COUNT(*) FROM nonconformity WHERE safety_impact = 1")
    project_issues = db.count(
        "SELECT COUNT(*) FROM open_issue WHERE closed_on IS NULL"
    )
    process_reviews = db.count("SELECT COUNT(*) FROM process_review")
    suppliers = db.count(
        "SELECT COUNT(*) FROM supplier WHERE performance_reviewed_on IS NOT NULL"
    )
    return {
        "previous_actions_status": f"미종결 시정조치 {open_capa}건",
        "context_changes": "context_entry 등록부 참조",
        "customer_satisfaction_and_feedback": "customer_satisfaction / complaint 등록부 참조",
        "quality_objectives_achievement": "quality_objective 등록부 참조",
        "process_performance_and_conformity": f"프로세스 검토 {process_reviews}건 실시",
        "nonconformities_and_corrective_actions": f"미종결 시정조치 {open_capa}건",
        "monitoring_and_measurement_results": f"목표 미달 PI {unmet}건",
        "audit_results": f"내부심사 {audits}건, 발견사항 {findings}건",
        "external_provider_performance": f"성과검토 완료 공급자 {suppliers}개사",
        "resource_adequacy": "resource_plan 등록부 참조",
        "risk_action_effectiveness": "risk_entry 등록부 참조",
        "improvement_opportunities": "improvement 등록부 참조",
        "project_review_key_issues": f"미종결 프로젝트 미결사항 {project_issues}건",
        "process_review_results": f"프로세스 검토 {process_reviews}건",
        "kpi_and_pi_analysis": f"목표 미달 지표 {unmet}건",
        "internal_external_failure_safety_impact": f"안전영향 부적합 {safety_ncs}건",
        "business_planning_outputs": "governance_record(business_plan) 참조",
    }
