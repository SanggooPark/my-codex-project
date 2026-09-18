"""OBS — 단산(진부화) 관리 프로세스 (8.10).

강제 통제
    CTL-030  단산 리스크 평가 및 단산 관리계획 정기 검토 (8.10 a, b, c)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import add_months, enforce, is_past

#: 8.10 NOTE 1 — 단산 이슈 유형
ISSUE_KINDS = ("technical", "functional", "knowledge")

#: 8.10 NOTE 3 — 완화 전략
STRATEGIES = (
    "second_source",
    "storage",
    "modular_design",
    "technology_upgrade",
)

#: 8.10 b) 관리계획 정기 검토 주기(개월)
PLAN_REVIEW_MONTHS = 12


def create_plan(
    db: Database,
    *,
    product: str,
    version: str,
    strategy: str,
    support_until: str,
    doc_id: int,
) -> int:
    """단산 관리계획을 수립한다 (8.10 b).

    최소한 보증 종료 시점까지 공급 제품·예비품의 가용성을 보장해야 한다.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"알 수 없는 단산 완화 전략: {strategy} (8.10 NOTE 3)")
    documents.assert_usable(db, doc_id, f"단산 관리계획 {product}")
    enforce(
        "CTL-030",
        bool(support_until) and not is_past(support_until),
        f"{product}: 단산 관리계획의 지원 보장 시점이 유효하지 않습니다(8.10).",
        db=db,
        context=f"obsolescence_plan:{product}",
    )
    existing = db.find("obsolescence_plan", product=product)
    if existing:
        db.update(
            "obsolescence_plan",
            existing["id"],
            version=version,
            strategy=strategy,
            support_until=support_until,
            doc_id=doc_id,
            reviewed_on=today(),
            next_review_on=add_months(today(), PLAN_REVIEW_MONTHS),
        )
        return int(existing["id"])
    return db.insert(
        "obsolescence_plan",
        product=product,
        version=version,
        strategy=strategy,
        support_until=support_until,
        doc_id=doc_id,
        reviewed_on=today(),
        next_review_on=add_months(today(), PLAN_REVIEW_MONTHS),
    )


def assess_risk(
    db: Database,
    *,
    product: str,
    part_no: str,
    risk_level: str,
    mitigation: str,
    issue_kind: str = "technical",
    config_part_no: str | None = None,
    project_code: str | None = None,
) -> int:
    """공급 제품의 단산 리스크를 평가한다 (8.10 a).

    고위험 항목은 완화조치가 반드시 정의되어야 하고, 관리계획이 선행되어야 한다.
    """
    if risk_level not in ("high", "medium", "low"):
        raise ValueError("risk_level 은 high|medium|low 여야 합니다.")
    if issue_kind not in ISSUE_KINDS:
        raise ValueError(f"알 수 없는 단산 이슈 유형: {issue_kind}")

    plan = db.find("obsolescence_plan", product=product)
    enforce(
        "CTL-030",
        plan is not None,
        f"{product}: 단산 관리계획이 없어 리스크를 등록할 수 없습니다(8.10 b).",
        db=db,
        context=f"obsolescence:{part_no}",
    )
    if risk_level == "high":
        enforce(
            "CTL-030",
            bool(mitigation.strip()),
            f"{part_no}: 고위험 단산 항목은 예방·완화 조치를 정의해야 합니다(8.10 b).",
            db=db,
            context=f"obsolescence:{part_no}",
        )

    config_item_id = None
    if config_part_no:
        project_id = (
            int(db.require("project", code=project_code)["id"]) if project_code else None
        )
        config_item_id = int(
            db.require("config_item", project_id=project_id, part_no=config_part_no)["id"]
        )
    return db.insert(
        "obsolescence_risk",
        config_item_id=config_item_id,
        part_no=part_no,
        product=product,
        risk_level=risk_level,
        issue_kind=issue_kind,
        assessed_on=today(),
        mitigation=mitigation,
    )


def communicate_to_customer(db: Database, risk_id: int) -> Row:
    """단산 이슈를 고객과 의사소통한다 (8.10 c)."""
    db.update("obsolescence_risk", risk_id, customer_communicated_on=today())
    return db.fetch("obsolescence_risk", risk_id)


def close_risk(db: Database, risk_id: int) -> Row:
    """완화조치 완료로 단산 리스크를 종결한다.

    고위험 항목은 고객 의사소통이 선행되어야 한다(8.10 c).
    """
    risk = db.fetch("obsolescence_risk", risk_id)
    if risk["risk_level"] == "high":
        enforce(
            "CTL-030",
            bool(risk["customer_communicated_on"]),
            f"{risk['part_no']}: 고위험 단산 리스크는 고객 의사소통 후 종결할 수 있습니다"
            " (8.10 c).",
            db=db,
            context=f"obsolescence:{risk['part_no']}",
        )
    db.update("obsolescence_risk", risk_id, mitigated_on=today(), status="closed")
    return db.fetch("obsolescence_risk", risk_id)


def plans_due_for_review(db: Database, *, as_of: str | None = None) -> list[Row]:
    """정기 검토 기한이 경과한 단산 관리계획 (8.10 b)."""
    return [
        p
        for p in db.query("SELECT * FROM obsolescence_plan")
        if is_past(p["next_review_on"], as_of=as_of)
    ]


def open_high_risks(db: Database) -> list[Row]:
    """완화되지 않은 고위험 단산 리스크."""
    return db.query(
        "SELECT * FROM obsolescence_risk WHERE risk_level = 'high' AND status = 'open'"
    )


def mitigation_rate(db: Database) -> float | None:
    """단산 리스크 완화율 (PI-OBS)."""
    total = db.count("SELECT COUNT(*) FROM obsolescence_risk")
    if total == 0:
        return None
    closed = db.count("SELECT COUNT(*) FROM obsolescence_risk WHERE status = 'closed'")
    return round(closed / total * 100, 2)
