"""TRF — 프로세스 이전 계획 프로세스 (8.1.1.2).

강제 통제
    CTL-035  프로세스 이전은 타당성조사·리스크평가·FAI 완료 후 승인 (8.1.1.2 a, b, e)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ..standard import load_registry
from ._base import enforce


def plan(
    db: Database,
    *,
    transfer_no: str,
    process_code: str,
    from_site: str,
    to_site: str,
    external: bool,
    feasibility_study: str,
    risk_entry_ref: str,
    action_plan: str,
) -> int:
    """프로세스 이전을 계획한다 (8.1.1.2 a~c)."""
    load_registry().process(process_code)  # 미정의 코드면 KeyError
    missing = [
        name
        for name, value in (
            ("feasibility_study", feasibility_study),
            ("risk_assessment", risk_entry_ref),
            ("action_plan", action_plan),
        )
        if not value.strip()
    ]
    enforce(
        "CTL-035",
        not missing,
        f"이전 {transfer_no} 계획 누락 항목(8.1.1.2): {', '.join(missing)}",
        db=db,
        context=f"transfer:{transfer_no}",
    )
    return db.insert(
        "process_transfer",
        transfer_no=transfer_no,
        process_code=process_code,
        from_site=from_site,
        to_site=to_site,
        external=int(external),
        feasibility_study=feasibility_study,
        risk_entry_ref=risk_entry_ref,
        action_plan=action_plan,
        status="planned",
    )


def communicate_to_customer(db: Database, transfer_no: str) -> Row:
    """이전 사실을 고객에게 통보한다 (8.1.1.2 d)."""
    transfer = db.require("process_transfer", transfer_no=transfer_no)
    db.update("process_transfer", transfer["id"], customer_communicated_on=today())
    return db.fetch("process_transfer", transfer["id"])


def link_fai(db: Database, transfer_no: str, *, fai_id: int) -> Row:
    """이전에 따른 FAI 를 연결한다 (8.1.1.2 e)."""
    transfer = db.require("process_transfer", transfer_no=transfer_no)
    db.update("process_transfer", transfer["id"], fai_id=fai_id)
    return db.fetch("process_transfer", transfer["id"])


def link_change(db: Database, transfer_no: str, *, change_no: str) -> Row:
    """변경관리와 연계한다 (8.1.1.2 마지막 문단, 8.1.4.2)."""
    transfer = db.require("process_transfer", transfer_no=transfer_no)
    db.update("process_transfer", transfer["id"], change_no=change_no)
    return db.fetch("process_transfer", transfer["id"])


def approve(db: Database, transfer_no: str) -> Row:
    """프로세스 이전을 승인한다.

    FAI 가 승인되지 않았거나, 고객 통보가 필요한 외부 이전에서 통보가 없으면 거부한다.
    """
    transfer = db.require("process_transfer", transfer_no=transfer_no)
    enforce(
        "CTL-035",
        transfer["fai_id"] is not None,
        f"이전 {transfer_no}: FAI 없이 승인할 수 없습니다(8.1.1.2 e).",
        db=db,
        context=f"transfer:{transfer_no}",
    )
    fai = db.fetch("fai", int(transfer["fai_id"]))
    enforce(
        "CTL-035",
        fai["decision"] in ("approved", "conditional"),
        f"이전 {transfer_no}: FAI {fai['fai_no']} 가 승인되지 않았습니다"
        f" (현재 {fai['decision']}).",
        db=db,
        context=f"transfer:{transfer_no}",
    )
    if transfer["external"]:
        enforce(
            "CTL-035",
            bool(transfer["customer_communicated_on"]),
            f"이전 {transfer_no}: 외부 조직으로의 이전은 고객 통보가 필요합니다(8.1.1.2 d).",
            db=db,
            context=f"transfer:{transfer_no}",
        )
    enforce(
        "CTL-035",
        bool(transfer["change_no"]),
        f"이전 {transfer_no}: 변경관리(8.1.4.2)와 연계되어야 합니다.",
        db=db,
        context=f"transfer:{transfer_no}",
    )
    db.update(
        "process_transfer", transfer["id"], approved_on=today(), status="approved"
    )
    return db.fetch("process_transfer", transfer["id"])
