"""TDR — 입찰 관리 프로세스 (8.1.2).

강제 통제
    CTL-008  요구사항 조항별 검토 완료 전 입찰 제출·계약 수락 금지
             (8.1.2 a, 8.2.3.1, 8.2.5 e 1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import requirements
from ._base import enforce


def open_tender(
    db: Database, *, tender_no: str, customer: str, title: str
) -> int:
    """입찰 건을 등록한다 (8.1.2)."""
    return db.insert(
        "tender", tender_no=tender_no, customer=customer, title=title, status="draft"
    )


def complete_review(
    db: Database,
    tender_no: str,
    *,
    control_extent: str,
    risk_entry_ref: str,
    monetary_risk_eval: str,
    knowledge_input: str,
    deliverable_cost_plan: str,
    resource_plan: str,
) -> Row:
    """입찰 검토를 완료한다 (8.1.2 a~f).

    요구사항 조항별 검토(8.2.5 e 1)가 선행되어야 하며, 리스크·기회의 금액 평가
    (8.1.2 c), 인도물 원가 계획(e), 계약이행 자원 계획(f)이 모두 있어야 한다.
    """
    tender = db.require("tender", tender_no=tender_no)
    requirements.assert_all_reviewed(
        db,
        owner_scope="tender",
        owner_ref=tender_no,
        purpose=f"입찰 {tender_no} 검토",
    )
    missing = [
        name
        for name, value in (
            ("type_and_extent_of_controls", control_extent),
            ("risk_and_opportunity", risk_entry_ref),
            ("monetary_evaluation", monetary_risk_eval),
            ("knowledge_input", knowledge_input),
            ("deliverable_cost_plan", deliverable_cost_plan),
            ("resource_plan", resource_plan),
        )
        if not str(value).strip()
    ]
    enforce(
        "CTL-008",
        not missing,
        f"입찰 {tender_no} 검토 누락 항목(8.1.2): {', '.join(missing)}",
        db=db,
        context=f"tender:{tender_no}",
    )
    db.update(
        "tender",
        tender["id"],
        status="reviewed",
        control_extent=control_extent,
        risk_entry_ref=risk_entry_ref,
        monetary_risk_eval=monetary_risk_eval,
        knowledge_input=knowledge_input,
        deliverable_cost_plan=deliverable_cost_plan,
        resource_plan=resource_plan,
    )
    return db.fetch("tender", tender["id"])


def approve_offer(db: Database, tender_no: str, *, approver_id: int) -> Row:
    """견적(제안)을 승인한다 (8.1.2 g)."""
    tender = db.require("tender", tender_no=tender_no)
    enforce(
        "CTL-008",
        tender["status"] == "reviewed",
        f"입찰 {tender_no}: 검토 완료 전에는 승인할 수 없습니다(현재 {tender['status']}).",
        db=db,
        context=f"tender:{tender_no}",
    )
    db.update(
        "tender",
        tender["id"],
        status="approved",
        approved_by_id=approver_id,
        approved_on=today(),
    )
    return db.fetch("tender", tender["id"])


def submit(db: Database, tender_no: str) -> Row:
    """입찰서를 제출한다. 승인되지 않은 입찰은 제출할 수 없다 (CTL-008)."""
    tender = db.require("tender", tender_no=tender_no)
    enforce(
        "CTL-008",
        tender["status"] == "approved" and bool(tender["approved_on"]),
        f"입찰 {tender_no}: 승인(8.1.2 g) 없이 제출할 수 없습니다(현재 {tender['status']}).",
        db=db,
        context=f"tender:{tender_no}",
    )
    requirements.assert_all_reviewed(
        db,
        owner_scope="tender",
        owner_ref=tender_no,
        purpose=f"입찰 {tender_no} 제출",
    )
    db.update("tender", tender["id"], status="submitted", submitted_on=today())
    return db.fetch("tender", tender["id"])


def record_outcome(db: Database, tender_no: str, *, won: bool) -> Row:
    """낙찰 결과를 기록한다."""
    tender = db.require("tender", tender_no=tender_no)
    enforce(
        "CTL-008",
        tender["status"] == "submitted",
        f"입찰 {tender_no}: 제출되지 않은 입찰의 결과를 기록할 수 없습니다.",
        db=db,
        context=f"tender:{tender_no}",
    )
    db.update("tender", tender["id"], status="won" if won else "lost")
    return db.fetch("tender", tender["id"])
