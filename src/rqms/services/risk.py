"""ROM — 리스크 및 기회 관리 프로세스 (6.1), 사업연속성 (6.1.4).

강제 통제
    CTL-034  사업연속성 계획 수립·검증 및 연간 검토 (6.1.4)
    CTL-042  리스크·기회 정기 검토 및 조치 효과성 평가 (6.1.3.1 b, e)
"""

from __future__ import annotations

import json
from sqlite3 import Row

from ..db import Database, today
from ._base import add_months, enforce, is_past

#: 6.1.3.1 리스크 관리 기법 (NOTE 1, 2)
METHODS = ("FMEA", "FMECA", "SWOT", "HAZOP", "qualitative")

#: 조치가 필요한 리스크 등급 하한 — 6.1.3.1 d) "조치 필요성 판단 기준"
ACTION_THRESHOLD = 9

#: 6.1.3.1 b) 정기 검토 주기(개월)
REVIEW_CYCLE_MONTHS = 6


def register(
    db: Database,
    *,
    ref_no: str,
    kind: str,
    scope: str,
    description: str,
    likelihood: int,
    impact: int,
    method: str = "qualitative",
    scope_ref: str = "",
    cost_benefit: str = "",
    action: str = "",
    action_owner_id: int | None = None,
    due_on: str | None = None,
) -> int:
    """리스크 또는 기회를 등록한다 (6.1.1, 6.1.2).

    등급이 조치 기준 이상이면 조치와 책임자가 반드시 지정되어야 한다(6.1.3.1 d).
    프로젝트 범위의 리스크·기회는 비용편익 분석이 필요하다(8.1.3.9.1 b).
    """
    if kind not in ("risk", "opportunity"):
        raise ValueError("kind 는 risk 또는 opportunity 여야 합니다.")
    if method not in METHODS:
        raise ValueError(f"알 수 없는 리스크 기법: {method}")

    rating = likelihood * impact
    if rating >= ACTION_THRESHOLD:
        enforce(
            "CTL-042",
            bool(action.strip()) and action_owner_id is not None and bool(due_on),
            f"{ref_no}: 등급 {rating} 리스크는 조치·책임자·기한을 지정해야 합니다(6.1.3.1 d).",
            db=db,
            context=f"risk:{ref_no}",
        )
    if scope == "project":
        enforce(
            "CTL-042",
            bool(cost_benefit.strip()),
            f"{ref_no}: 프로젝트 리스크·기회는 비용편익 분석이 필요합니다(8.1.3.9.1 b).",
            db=db,
            context=f"risk:{ref_no}",
        )

    return db.insert(
        "risk_entry",
        ref_no=ref_no,
        kind=kind,
        scope=scope,
        scope_ref=scope_ref,
        description=description,
        method=method,
        likelihood=likelihood,
        impact=impact,
        rating=rating,
        cost_benefit=cost_benefit,
        action=action,
        action_owner_id=action_owner_id,
        due_on=due_on,
        status="open",
        reviewed_on=today(),
    )


def review(
    db: Database,
    risk_id: int,
    *,
    effectiveness_note: str,
    likelihood: int | None = None,
    impact: int | None = None,
    close: bool = False,
) -> Row:
    """리스크·기회를 검토하고 조치 효과성을 평가한다 (6.1.3.1 b, e).

    종결하려면 효과성 평가가 기록되어야 한다.
    """
    entry = db.fetch("risk_entry", risk_id)
    enforce(
        "CTL-042",
        bool(effectiveness_note.strip()),
        f"{entry['ref_no']}: 검토 시 조치 효과성 평가를 기록해야 합니다(6.1.3.1 e).",
        db=db,
        context=f"risk:{entry['ref_no']}",
    )
    new_l = likelihood if likelihood is not None else entry["likelihood"]
    new_i = impact if impact is not None else entry["impact"]
    db.update(
        "risk_entry",
        risk_id,
        likelihood=new_l,
        impact=new_i,
        rating=new_l * new_i,
        effectiveness_note=effectiveness_note,
        reviewed_on=today(),
        status="closed" if close else entry["status"],
    )
    return db.fetch("risk_entry", risk_id)


def overdue_reviews(db: Database, *, as_of: str | None = None) -> list[Row]:
    """정기 검토 주기를 초과한 미종결 리스크 (6.1.3.1 b)."""
    rows = db.query("SELECT * FROM risk_entry WHERE status != 'closed'")
    out = []
    for row in rows:
        if not row["reviewed_on"]:
            out.append(row)
            continue
        if is_past(add_months(row["reviewed_on"], REVIEW_CYCLE_MONTHS), as_of=as_of):
            out.append(row)
    return out


# ------------------------------------------------------------- 6.1.4 사업연속성
#: 6.1.4 NOTE 1 — 사업연속성이 다루어야 하는 대표 리스크
CONTINUITY_TOPICS = (
    "interruptions",
    "supply_chain",
    "labour_shortage",
    "critical_technologies",
    "key_equipment_failure",
    "field_returns",
    "succession_plan",
    "information_technology",
    "communication",
    "emergency_or_crisis",
)


def record_continuity_plan(
    db: Database,
    *,
    year: int,
    doc_id: int,
    topics: dict[str, str],
    responsibilities: str,
    verified_on: str | None = None,
) -> int:
    """사업연속성 계획을 등록한다 (6.1.4 a, b, c).

    리스크 평가에 근거해야 하고, 책임이 정의되어야 하며, 검증(예: 주기적 시험)이
    기록되어야 한다.
    """
    from . import documents  # 순환 참조 회피

    documents.assert_usable(db, doc_id, f"사업연속성 계획 {year}")
    missing = [t for t in CONTINUITY_TOPICS if not topics.get(t)]
    enforce(
        "CTL-034",
        not missing,
        f"{year}년 사업연속성 계획 누락 리스크 항목: {', '.join(missing)}",
        db=db,
        context=f"bcp:{year}",
    )
    enforce(
        "CTL-034",
        bool(responsibilities.strip()),
        f"{year}년 사업연속성 계획에 조치 책임이 정의되지 않았습니다(6.1.4 c).",
        db=db,
        context=f"bcp:{year}",
    )
    return db.insert(
        "governance_record",
        kind="business_continuity_plan",
        ref_year=year,
        doc_id=doc_id,
        payload=json.dumps(
            {"topics": topics, "responsibilities": responsibilities}, ensure_ascii=False
        ),
        verified_on=verified_on,
        reviewed_on=today(),
    )


def verify_continuity_plan(db: Database, record_id: int, *, evidence: str) -> None:
    """사업연속성 계획을 검증한다(주기적 시험 등) (6.1.4 a)."""
    enforce(
        "CTL-034",
        bool(evidence.strip()),
        "사업연속성 계획 검증에는 증거(예: 시험 결과)가 필요합니다.",
        db=db,
        context=f"bcp:{record_id}",
    )
    record = db.fetch("governance_record", record_id)
    payload = json.loads(record["payload"])
    payload["verification_evidence"] = evidence
    db.update(
        "governance_record",
        record_id,
        payload=json.dumps(payload, ensure_ascii=False),
        verified_on=today(),
    )
