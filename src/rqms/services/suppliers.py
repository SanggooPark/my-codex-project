"""EPP — 외부공급 프로세스·제품·서비스(EPPPS) 관리 프로세스 (8.4).

강제 통제
    CTL-011  EPPPS 는 승인된 외부공급자에게만 발주 (8.4.1.1.4)
    CTL-012  인수검증 미완료 EPPPS 의 사용·투입 금지 (8.4.2.2)
    CTL-013  검증활동 위임은 위임 등록부 등록 및 공급자 동의 증거 보유 (8.4.2.2)
    CTL-016  신규/변경 EPPPS 는 FAI 승인 후 출시 (8.4.2.1.1 c, e)
    CTL-048  외부공급자 분류·평가·성과감시 (8.4.1.1.2, .3, .5.1, 8.4.2.3)
    CTL-049  구매발주 확인서 수령 및 요구사항 전달 (8.4.3.1, 8.4.4)
"""

from __future__ import annotations

import json
from sqlite3 import Row

from ..db import Database, today
from ._base import add_months, enforce, is_past

#: 8.4.1.1.2 외부공급자 분류
CLASSIFICATIONS = ("key", "standard", "commodity")

#: 8.4.1.1.2 분류 정기 재검토 주기(개월)
CLASSIFICATION_REVIEW_MONTHS = 24

#: 8.4.2.3 a) 핵심 공급자 성과검토 주기(개월)
PERFORMANCE_REVIEW_MONTHS = 12

#: 8.4.3 / 8.4.3.1 외부공급자에게 전달해야 하는 요구사항
REQUIRED_COMMUNICATION = (
    "processes_products_services",
    "approval_requirements",
    "competence_requirements",
    "interaction_with_organization",
    "performance_control_and_monitoring",
    "verification_at_premises",
    "specification_revisions",
    "eppps_deliverables_and_schedule",
    "change_and_nonconformity_management",
    "delivery_schedule",
    "product_criticality",
    "right_of_access",
)

#: 8.4.1.1.5.1 a)~d) 견적 선정 분석 항목
OFFER_ANALYSIS_TOPICS = (
    "clause_by_clause_conformity",
    "total_cost_of_ownership",
    "past_qcd_performance",
    "supplier_classification",
)


def register(db: Database, *, code: str, name: str) -> int:
    """외부공급자를 등록한다 (8.4.1)."""
    return db.insert("supplier", code=code, name=name)


def classify(
    db: Database,
    supplier_code: str,
    *,
    classification: str,
    criteria_note: str,
) -> Row:
    """외부공급자를 분류한다 (8.4.1.1.2). 분류기준에는 요구사항 충족능력이 포함된다."""
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"알 수 없는 분류: {classification}")
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-048",
        bool(criteria_note.strip()),
        f"공급자 {supplier_code}: 분류 기준(요구사항 충족능력 포함)을 기록해야 합니다"
        " (8.4.1.1.2).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.update(
        "supplier",
        supplier["id"],
        classification=classification,
        classification_reviewed_on=today(),
        evaluation_note=criteria_note,
    )
    return db.fetch("supplier", supplier["id"])


def evaluate(
    db: Database,
    supplier_code: str,
    *,
    people_infrastructure_processes: str,
    certifications: str,
    targeted: bool = False,
) -> Row:
    """외부공급자를 평가한다 (8.4.1.1.3 a, b)."""
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-048",
        bool(people_infrastructure_processes.strip()),
        f"공급자 {supplier_code}: 인원·기반구조·프로세스 평가가 필요합니다(8.4.1.1.3 a).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    enforce(
        "CTL-048",
        bool(certifications.strip()),
        f"공급자 {supplier_code}: 자격(인증) 보유 현황을 평가해야 합니다(8.4.1.1.3 b).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.update(
        "supplier",
        supplier["id"],
        evaluated_on=today(),
        evaluation_note=people_infrastructure_processes,
        certifications=certifications,
        targeted=int(targeted),
    )
    return db.fetch("supplier", supplier["id"])


def approve(
    db: Database, supplier_code: str, *, approver_id: int, approval_scope: str
) -> Row:
    """외부공급자를 승인한다 (8.4.1.1.4 a, c).

    분류·평가가 선행되어야 하며, 승인 범위가 정의되어야 한다.
    """
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-048",
        bool(supplier["classification_reviewed_on"]) and bool(supplier["evaluated_on"]),
        f"공급자 {supplier_code}: 분류(8.4.1.1.2)와 평가(8.4.1.1.3) 없이 승인할 수 없습니다.",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    enforce(
        "CTL-011",
        bool(approval_scope.strip()),
        f"공급자 {supplier_code}: 승인 범위를 정의해야 합니다(8.4.1.1.4 c).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.update(
        "supplier",
        supplier["id"],
        approved=1,
        approval_scope=approval_scope,
        approved_on=today(),
        approved_by_id=approver_id,
        rejected_on=None,
    )
    return db.fetch("supplier", supplier["id"])


def revoke_approval(db: Database, supplier_code: str, *, approver_id: int, reason: str) -> Row:
    """승인된 외부공급자의 승인을 철회한다 (8.4.1.1.4 b).

    승인 권한을 가진 기능은 철회 권한도 가진다.
    """
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-011",
        bool(reason.strip()),
        f"공급자 {supplier_code}: 승인 철회 사유를 기록해야 합니다.",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.update(
        "supplier",
        supplier["id"],
        approved=0,
        rejected_on=today(),
        approved_by_id=approver_id,
        development_plan=reason,
    )
    return db.fetch("supplier", supplier["id"])


def select_offer(
    db: Database, supplier_code: str, *, analysis: dict[str, str]
) -> Row:
    """견적을 선정한다 (8.4.1.1.5.1 a~d)."""
    supplier = db.require("supplier", code=supplier_code)
    missing = [t for t in OFFER_ANALYSIS_TOPICS if not analysis.get(t)]
    enforce(
        "CTL-048",
        not missing,
        f"공급자 {supplier_code} 견적 선정 분석 누락 항목(8.4.1.1.5.1): {', '.join(missing)}",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.insert(
        "governance_record",
        kind="offer_selection",
        doc_id=None,
        payload=json.dumps({"supplier": supplier_code, "analysis": analysis}, ensure_ascii=False),
        reviewed_on=today(),
    )
    return db.fetch("supplier", supplier["id"])


def issue_purchase_order(
    db: Database,
    *,
    po_no: str,
    supplier_code: str,
    item: str,
    qty: float,
    required_on: str,
    requirements_communicated: dict[str, str],
    criticality: str = "standard",
    project_code: str | None = None,
    config_part_no: str | None = None,
    is_new_or_modified: bool = False,
    special_process_approval: str = "",
) -> int:
    """구매발주를 발행한다 (8.4.3, 8.4.3.1).

    승인된 공급자만 발주 가능(CTL-011)하고, 요구사항이 모두 전달되어야 한다(CTL-049).
    """
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-011",
        bool(supplier["approved"]),
        f"공급자 {supplier_code}({supplier['name']}) 는 승인되지 않았습니다."
        " EPPPS 는 승인된 공급자만 공급할 수 있습니다(8.4.1.1.4).",
        db=db,
        context=f"purchase_order:{po_no}",
    )
    missing = [t for t in REQUIRED_COMMUNICATION if not requirements_communicated.get(t)]
    enforce(
        "CTL-049",
        not missing,
        f"발주 {po_no}: 외부공급자에게 전달해야 하는 요구사항 누락(8.4.3, 8.4.3.1): "
        f"{', '.join(missing)}",
        db=db,
        context=f"purchase_order:{po_no}",
    )

    project_id = None
    if project_code:
        project_id = int(db.require("project", code=project_code)["id"])
    config_item_id = None
    if config_part_no:
        config_item_id = int(
            db.require("config_item", project_id=project_id, part_no=config_part_no)["id"]
        )
    return db.insert(
        "purchase_order",
        po_no=po_no,
        supplier_id=supplier["id"],
        project_id=project_id,
        item=item,
        config_item_id=config_item_id,
        qty=qty,
        required_on=required_on,
        criticality=criticality,
        requirements_communicated=",".join(sorted(requirements_communicated)),
        special_process_approval=special_process_approval,
        is_new_or_modified=int(is_new_or_modified),
    )


def acknowledge_order(db: Database, po_no: str) -> Row:
    """공급자의 발주 확인서 수령을 기록한다 (8.4.4 a)."""
    po = db.require("purchase_order", po_no=po_no)
    db.update("purchase_order", po["id"], acknowledged_on=today())
    return db.fetch("purchase_order", po["id"])


def approve_release(
    db: Database,
    *,
    po_no: str,
    approval_method: str,
    fai_id: int | None,
    validated_before_first_use: bool,
    baseline_id: int | None,
    approver_id: int,
) -> int:
    """신규/변경 EPPPS 의 출시를 승인한다 (8.4.2.1.1 a~f).

    FAI(또는 적절한 인수/출하검사)가 승인되어야 하고, 최초 사용 전 유효성확인과
    형상 기준선 정의가 필요하다.
    """
    po = db.require("purchase_order", po_no=po_no)
    enforce(
        "CTL-016",
        bool(approval_method.strip()),
        f"발주 {po_no}: 승인 방법을 결정해야 합니다(8.4.2.1.1 a).",
        db=db,
        context=f"eppps_release:{po_no}",
    )
    enforce(
        "CTL-016",
        fai_id is not None,
        f"발주 {po_no}: 신규/변경 EPPPS 는 FAI 를 실시해야 합니다(8.4.2.1.1 c, 8.9.3 a).",
        db=db,
        context=f"eppps_release:{po_no}",
    )
    fai = db.fetch("fai", int(fai_id))
    enforce(
        "CTL-016",
        fai["decision"] in ("approved", "conditional"),
        f"발주 {po_no}: FAI {fai['fai_no']} 가 승인되지 않았습니다(현재 {fai['decision']}).",
        db=db,
        context=f"eppps_release:{po_no}",
    )
    enforce(
        "CTL-016",
        validated_before_first_use,
        f"발주 {po_no}: 고객 계약에 최초 사용하기 전 유효성확인이 필요합니다"
        " (8.4.2.1.1 d).",
        db=db,
        context=f"eppps_release:{po_no}",
    )
    enforce(
        "CTL-016",
        baseline_id is not None,
        f"발주 {po_no}: 형상 기준선을 정의·갱신해야 합니다(8.4.2.1.1 f).",
        db=db,
        context=f"eppps_release:{po_no}",
    )
    return db.insert(
        "eppps_release",
        po_id=po["id"],
        approval_method=approval_method,
        fai_id=fai_id,
        validated_before_first_use=int(validated_before_first_use),
        baseline_id=baseline_id,
        approved_on=today(),
        approved_by_id=approver_id,
    )


def delegate_verification(
    db: Database,
    *,
    supplier_code: str,
    scope: str,
    requirements_text: str,
    supplier_acceptance_evidence: str,
    control_measure: str,
) -> int:
    """검증활동을 외부공급자에게 위임한다 (8.4.2.2).

    위임 요구사항·통제수단을 정의하고, 공급자의 동의 증거가 있어야 하며,
    위임 등록부에 등재되어야 한다.
    """
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-013",
        bool(supplier_acceptance_evidence.strip()),
        f"공급자 {supplier_code}: 검증 위임에는 공급자의 동의 증거가 필요합니다(8.4.2.2).",
        db=db,
        context=f"delegation:{supplier_code}",
    )
    enforce(
        "CTL-013",
        bool(requirements_text.strip()) and bool(control_measure.strip()),
        f"공급자 {supplier_code}: 위임 요구사항과 통제수단(예: 정기 심사)을 정의해야 합니다"
        " (8.4.2.2).",
        db=db,
        context=f"delegation:{supplier_code}",
    )
    return db.insert(
        "verification_delegation",
        supplier_id=supplier["id"],
        scope=scope,
        requirements=requirements_text,
        supplier_acceptance_evidence=supplier_acceptance_evidence,
        control_measure=control_measure,
        granted_on=today(),
    )


def record_incoming_inspection(
    db: Database,
    *,
    po_no: str,
    result: str,
    evidence: str,
    released_by_id: int,
    planned_extent: str = "",
    delegated: bool = False,
    concession_id: int | None = None,
) -> int:
    """출시 후 EPPPS 검증(인수검사)을 기록한다 (8.4.2.2 a~e).

    위임 검증인 경우 위임 등록부에 등재되어 있어야 한다(CTL-013).
    """
    po = db.require("purchase_order", po_no=po_no)
    if result not in ("pass", "fail"):
        raise ValueError("result 는 pass 또는 fail 여야 합니다.")
    enforce(
        "CTL-012",
        bool(evidence.strip()),
        f"발주 {po_no}: 요구사항 적합 증거(성적서·시험보고서 등)를 확보해야 합니다"
        " (8.4.2.2 c).",
        db=db,
        context=f"incoming_inspection:{po_no}",
    )
    if delegated:
        delegation = db.find("verification_delegation", supplier_id=po["supplier_id"])
        enforce(
            "CTL-013",
            delegation is not None,
            f"발주 {po_no}: 위임 등록부에 등재되지 않은 검증 위임입니다(8.4.2.2).",
            db=db,
            context=f"incoming_inspection:{po_no}",
        )
    return db.insert(
        "incoming_inspection",
        po_id=po["id"],
        planned_extent=planned_extent,
        performed_on=today(),
        result=result,
        evidence=evidence,
        released_by_id=released_by_id,
        delegated=int(delegated),
        concession_id=concession_id,
    )


def assert_verified_for_use(db: Database, po_no: str, purpose: str) -> Row:
    """EPPPS 를 사용·투입하기 전 검증 완료를 확인한다 (8.4.2.2, CTL-012).

    부적합이더라도 승인된 특채(concession) 하에서는 사용할 수 있다.
    """
    from . import nonconformity  # 순환 참조 회피

    po = db.require("purchase_order", po_no=po_no)
    inspection = db.one(
        "SELECT * FROM incoming_inspection WHERE po_id = ? "
        "ORDER BY performed_on DESC LIMIT 1",
        (po["id"],),
    )
    enforce(
        "CTL-012",
        inspection is not None,
        f"{purpose}: 발주 {po_no} 의 인수검증 기록이 없어 사용할 수 없습니다(8.4.2.2).",
        db=db,
        context=purpose,
    )
    assert inspection is not None
    if inspection["result"] == "pass":
        return po

    enforce(
        "CTL-012",
        inspection["concession_id"] is not None,
        f"{purpose}: 발주 {po_no} 의 인수검증이 부적합이며 승인된 특채가 없습니다"
        " (8.4.2.2).",
        db=db,
        context=purpose,
    )
    nonconformity.assert_concession_valid(
        db, int(inspection["concession_id"]), qty=float(po["qty"]), purpose=purpose
    )
    return po


def review_performance(
    db: Database,
    supplier_code: str,
    *,
    score: float,
    ranking: str,
    audit_criteria: str,
    feedback_given: bool,
    development_plan: str = "",
) -> Row:
    """핵심 공급자의 성과를 검토·등급화한다 (8.4.2.3 a~h)."""
    supplier = db.require("supplier", code=supplier_code)
    enforce(
        "CTL-048",
        bool(audit_criteria.strip()),
        f"공급자 {supplier_code}: 심사 기준을 정의해야 합니다(8.4.2.3 b).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    enforce(
        "CTL-048",
        feedback_given,
        f"공급자 {supplier_code}: 성과 결과를 공급자에게 피드백해야 합니다(8.4.2.3 e).",
        db=db,
        context=f"supplier:{supplier_code}",
    )
    db.update(
        "supplier",
        supplier["id"],
        performance_reviewed_on=today(),
        performance_score=score,
        ranking=ranking,
        development_plan=development_plan,
    )
    return db.fetch("supplier", supplier["id"])


# ------------------------------------------------------------------- 상태 점검
def unapproved_with_orders(db: Database) -> list[Row]:
    """승인되지 않은 공급자에게 발행된 발주 (CTL-011)."""
    return db.query(
        "SELECT po.*, s.code AS supplier_code FROM purchase_order po "
        "JOIN supplier s ON s.id = po.supplier_id WHERE s.approved = 0"
    )


def unacknowledged_orders(db: Database) -> list[Row]:
    """확인서를 받지 못한 발주 (8.4.4 a)."""
    return db.query(
        "SELECT * FROM purchase_order WHERE acknowledged_on IS NULL AND status != 'cancelled'"
    )


def stale_classifications(db: Database, *, as_of: str | None = None) -> list[Row]:
    """분류 재검토 주기를 초과한 공급자 (8.4.1.1.2)."""
    out = []
    for row in db.query("SELECT * FROM supplier"):
        reviewed = row["classification_reviewed_on"]
        if not reviewed or is_past(
            add_months(reviewed, CLASSIFICATION_REVIEW_MONTHS), as_of=as_of
        ):
            out.append(row)
    return out


def key_suppliers_without_performance_review(
    db: Database, *, as_of: str | None = None
) -> list[Row]:
    """성과검토 주기를 초과한 핵심 공급자 (8.4.2.3 a)."""
    out = []
    for row in db.query("SELECT * FROM supplier WHERE classification = 'key'"):
        reviewed = row["performance_reviewed_on"]
        if not reviewed or is_past(
            add_months(reviewed, PERFORMANCE_REVIEW_MONTHS), as_of=as_of
        ):
            out.append(row)
    return out


def delegations_without_evidence(db: Database) -> list[Row]:
    """공급자 동의 증거가 없는 검증 위임 (CTL-013)."""
    return db.query(
        "SELECT * FROM verification_delegation "
        "WHERE TRIM(supplier_acceptance_evidence) = ''"
    )
