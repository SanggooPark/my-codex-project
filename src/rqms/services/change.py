"""CHG — 변경 관리 프로세스 (8.1.4.2).

강제 통제
    CTL-027  변경은 영향분석·승인 후에만 실행하며 실행 후 검증 필수
             (8.1.4.2 d, e, h, i, j)
    CTL-028  고객·외부공급자 요구사항에 영향을 주는 변경은 통보·합의 필요 (8.1.4.2 f)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import enforce

#: 8.1.4.2 p)~t) 변경관리 요구사항이 적용되는 범위
SCOPES = (
    "project_scope",
    "project_schedule",
    "project_budget",
    "requirement",
    "design",
    "configuration",
    "production",
    "process_transfer",
    "supplier",
)

ORIGINS = ("internal", "customer", "external_provider")


def raise_change(
    db: Database,
    *,
    change_no: str,
    scope: str,
    target_ref: str,
    description: str,
    origin: str = "internal",
    technical: bool = False,
    customer_impact: bool = False,
    from_failure: bool = False,
    cause_analysis: str = "",
) -> int:
    """변경요청을 등록한다 (8.1.4.2 b).

    고장에서 기인한 변경은 원인분석이 필요하다(8.1.4.2 c).
    """
    if scope not in SCOPES:
        raise ValueError(f"알 수 없는 변경 범위: {scope}")
    if origin not in ORIGINS:
        raise ValueError(f"알 수 없는 변경 출처: {origin}")
    if from_failure:
        enforce(
            "CTL-027",
            bool(cause_analysis.strip()),
            f"변경 {change_no}: 고장에 기인한 변경은 원인분석이 필요합니다(8.1.4.2 c).",
            db=db,
            context=f"change:{change_no}",
        )
    return db.insert(
        "change_request",
        change_no=change_no,
        scope=scope,
        target_ref=target_ref,
        description=description,
        origin=origin,
        technical=int(technical),
        customer_impact=int(customer_impact),
        cause_analysis=cause_analysis,
        status="raised",
    )


def analyse_impact(
    db: Database,
    change_no: str,
    *,
    impact_analysis: str,
    proposal_verified: bool,
    impact_on_delivered: str = "",
    revalidation_note: str = "",
    affected_serials: str = "",
) -> Row:
    """변경 영향분석과 제안 검증을 기록한다 (8.1.4.2 d, e, l~o).

    기술 변경은 기납품·고객규격·기술요구사항 영향과 재유효성확인 판단, 대상 일련번호가
    필요하다(8.1.4.2 l, n, o).
    """
    change = db.require("change_request", change_no=change_no)
    enforce(
        "CTL-027",
        bool(impact_analysis.strip()),
        f"변경 {change_no}: 리스크·기회를 고려한 영향분석이 필요합니다(8.1.4.2 d).",
        db=db,
        context=f"change:{change_no}",
    )
    enforce(
        "CTL-027",
        proposal_verified,
        f"변경 {change_no}: 악영향 방지를 위한 제안 검증이 필요합니다(8.1.4.2 e).",
        db=db,
        context=f"change:{change_no}",
    )
    if change["technical"]:
        enforce(
            "CTL-027",
            bool(impact_on_delivered.strip())
            and bool(revalidation_note.strip())
            and bool(affected_serials.strip()),
            f"변경 {change_no}: 기술 변경은 기납품 영향·재유효성확인 판단·대상 일련번호를"
            " 기록해야 합니다(8.1.4.2 l, n, o).",
            db=db,
            context=f"change:{change_no}",
        )
    db.update(
        "change_request",
        change["id"],
        impact_analysis=impact_analysis,
        proposal_verified=int(proposal_verified),
        impact_on_delivered=impact_on_delivered,
        revalidation_note=revalidation_note,
        affected_serials=affected_serials,
        status="analysed",
    )
    return db.fetch("change_request", change["id"])


def notify_customer(db: Database, change_no: str, *, agreed: bool = False) -> Row:
    """고객에게 변경을 통보하고 합의를 기록한다 (8.1.4.2 f)."""
    change = db.require("change_request", change_no=change_no)
    db.update(
        "change_request",
        change["id"],
        customer_notified_on=today(),
        customer_agreed_on=today() if agreed else None,
    )
    return db.fetch("change_request", change["id"])


def notify_provider(db: Database, change_no: str) -> Row:
    """외부공급자에게 변경을 통보한다 (8.1.4.2 f, 8.4.4 b)."""
    change = db.require("change_request", change_no=change_no)
    db.update("change_request", change["id"], provider_notified_on=today())
    return db.fetch("change_request", change["id"])


def approve(db: Database, change_no: str, *, approver_id: int) -> Row:
    """변경을 승인한다 (8.1.4.2 g, h).

    영향분석·제안검증이 선행되어야 하고, 고객 요구사항에 영향을 주는 변경은
    고객 합의가 있어야 승인할 수 있다(CTL-028).
    """
    change = db.require("change_request", change_no=change_no)
    enforce(
        "CTL-027",
        change["status"] == "analysed",
        f"변경 {change_no}: 영향분석 완료 전에는 승인할 수 없습니다(현재 {change['status']}).",
        db=db,
        context=f"change:{change_no}",
    )
    if change["customer_impact"]:
        enforce(
            "CTL-028",
            bool(change["customer_agreed_on"]),
            f"변경 {change_no}: 고객 요구사항에 영향을 주는 변경은 고객 합의가 필요합니다"
            " (8.1.4.2 f).",
            db=db,
            context=f"change:{change_no}",
        )
    if change["scope"] == "supplier" or change["origin"] == "external_provider":
        enforce(
            "CTL-028",
            bool(change["provider_notified_on"]),
            f"변경 {change_no}: 외부공급자 통보가 필요합니다(8.1.4.2 f).",
            db=db,
            context=f"change:{change_no}",
        )
    db.update(
        "change_request",
        change["id"],
        approver_id=approver_id,
        approved_on=today(),
        status="approved",
    )
    return db.fetch("change_request", change["id"])


def implement(db: Database, change_no: str) -> Row:
    """승인된 변경을 실행한다 (8.1.4.2 i). 승인 전 실행은 거부된다."""
    change = db.require("change_request", change_no=change_no)
    enforce(
        "CTL-027",
        bool(change["approved_on"]),
        f"변경 {change_no}: 승인 전에는 실행할 수 없습니다(8.1.4.2 h).",
        db=db,
        context=f"change:{change_no}",
    )
    db.update(
        "change_request", change["id"], implemented_on=today(), status="implemented"
    )
    return db.fetch("change_request", change["id"])


def verify_implementation(db: Database, change_no: str, *, effective: bool) -> Row:
    """실행 검증 및 효과성 추적을 기록한다 (8.1.4.2 j)."""
    change = db.require("change_request", change_no=change_no)
    enforce(
        "CTL-027",
        bool(change["implemented_on"]),
        f"변경 {change_no}: 실행되지 않은 변경은 검증할 수 없습니다.",
        db=db,
        context=f"change:{change_no}",
    )
    db.update(
        "change_request",
        change["id"],
        implementation_verified_on=today(),
        effectiveness_on=today() if effective else None,
        status="closed" if effective else "implemented",
    )
    return db.fetch("change_request", change["id"])


def approved_change(db: Database, *, scope: str, target_ref: str) -> Row | None:
    """해당 범위·대상에 대해 승인된(미종결 포함) 변경요청을 찾는다."""
    return db.one(
        "SELECT * FROM change_request "
        "WHERE scope = ? AND target_ref = ? AND approved_on IS NOT NULL "
        "ORDER BY approved_on DESC LIMIT 1",
        (scope, target_ref),
    )


def assert_approved_change(
    db: Database, *, scope: str, target_ref: str, control_id: str, purpose: str
) -> Row:
    """승인된 변경요청 없이 통제 대상 변경을 수행하지 못하게 한다."""
    change = approved_change(db, scope=scope, target_ref=target_ref)
    enforce(
        control_id,
        change is not None,
        f"{purpose}: 승인된 변경요청(scope={scope}) 없이 변경할 수 없습니다.",
        db=db,
        context=purpose,
    )
    assert change is not None
    return change


def unverified_implementations(db: Database) -> list[Row]:
    """실행되었으나 검증되지 않은 변경 (8.1.4.2 j)."""
    return db.query(
        "SELECT * FROM change_request "
        "WHERE implemented_on IS NOT NULL AND implementation_verified_on IS NULL"
    )
