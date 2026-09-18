"""NCA — 부적합 및 시정조치 관리 프로세스 (10.2), 개선 (10.1, 10.3).

강제 통제
    CTL-020  KPI 목표 미달 시 시정조치 등록 (9.1.3.1, 9.3.3.1)
    CTL-033  시정조치 필요성 평가 및 에스컬레이션 (10.2.1, 10.2.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import enforce

#: 10.2.3 c) 문제해결 기법
METHODS = ("4D", "8D", "FRACAS", "A3", "5why")

#: 시정조치 출처
SOURCE_TYPES = (
    "nonconformity",
    "complaint",
    "audit",
    "kpi",
    "rams",
    "process_review",
    "management_review",
)

#: 10.2.3 e) 에스컬레이션 단계별 보고 대상
ESCALATION_TARGETS = {
    0: "",
    1: "process_owner",
    2: "director",
    3: "top_management",
}

#: 10.1 개선 유형 (NOTE)
IMPROVEMENT_KINDS = (
    "correction",
    "corrective_action",
    "continual",
    "breakthrough",
    "innovation",
    "reorganization",
)


def open_capa(
    db: Database,
    *,
    capa_no: str,
    source_type: str,
    source_ref: str,
    description: str,
    criteria_applied: str,
    method: str,
    owner_id: int,
    due_on: str,
    escalation_level: int = 0,
) -> int:
    """시정조치를 개시한다 (10.2.1, 10.2.3 a~c, e).

    필요성 평가 기준과 문제해결 기법이 기록되어야 하며, 에스컬레이션 단계에 따라
    보고 대상이 결정된다.
    """
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"알 수 없는 시정조치 출처: {source_type}")
    if method not in METHODS:
        raise ValueError(f"알 수 없는 문제해결 기법: {method} (10.2.3 c)")
    enforce(
        "CTL-033",
        bool(criteria_applied.strip()),
        f"시정조치 {capa_no}: 필요성 평가 기준을 기록해야 합니다(10.2.3 b).",
        db=db,
        context=f"capa:{capa_no}",
    )
    enforce(
        "CTL-033",
        escalation_level in ESCALATION_TARGETS,
        f"시정조치 {capa_no}: 에스컬레이션 단계는 {sorted(ESCALATION_TARGETS)} 중"
        " 하나여야 합니다(10.2.3 e).",
        db=db,
        context=f"capa:{capa_no}",
    )
    return db.insert(
        "capa",
        capa_no=capa_no,
        source_type=source_type,
        source_ref=source_ref,
        description=description,
        criteria_applied=criteria_applied,
        method=method,
        owner_id=owner_id,
        opened_on=today(),
        due_on=due_on,
        escalation_level=escalation_level,
        escalated_to=ESCALATION_TARGETS[escalation_level],
        status="open",
    )


def record_analysis(
    db: Database,
    capa_no: str,
    *,
    root_cause: str,
    actions: str,
    similar_checked: bool,
    risk_updated: bool = False,
) -> Row:
    """원인분석과 조치계획을 기록한다 (10.2.1 b) 1)~3), c), e)).

    유사 부적합의 존재·발생 가능성 확인(10.2.1 b) 3))이 필수다.
    """
    capa = db.require("capa", capa_no=capa_no)
    enforce(
        "CTL-033",
        bool(root_cause.strip()) and bool(actions.strip()),
        f"시정조치 {capa_no}: 원인과 조치를 기록해야 합니다(10.2.1 b, c).",
        db=db,
        context=f"capa:{capa_no}",
    )
    enforce(
        "CTL-033",
        similar_checked,
        f"시정조치 {capa_no}: 유사 부적합의 존재·발생 가능성을 확인해야 합니다"
        " (10.2.1 b) 3)).",
        db=db,
        context=f"capa:{capa_no}",
    )
    db.update(
        "capa",
        capa["id"],
        root_cause=root_cause,
        actions=actions,
        similar_checked=int(similar_checked),
        risk_updated=int(risk_updated),
        status="in_progress",
    )
    return db.fetch("capa", capa["id"])


def close_capa(db: Database, capa_no: str, *, effective: bool, evidence: str) -> Row:
    """시정조치의 효과성을 검토하고 종결한다 (10.2.1 d).

    효과적이지 않으면 종결할 수 없고 조치를 계속해야 한다.
    """
    capa = db.require("capa", capa_no=capa_no)
    enforce(
        "CTL-033",
        bool(capa["root_cause"]) and bool(capa["actions"]),
        f"시정조치 {capa_no}: 원인분석·조치 기록 없이 종결할 수 없습니다(10.2.1 b, c).",
        db=db,
        context=f"capa:{capa_no}",
    )
    enforce(
        "CTL-033",
        bool(evidence.strip()),
        f"시정조치 {capa_no}: 효과성 검토 증거를 기록해야 합니다(10.2.1 d, 10.2.2 b).",
        db=db,
        context=f"capa:{capa_no}",
    )
    enforce(
        "CTL-033",
        effective,
        f"시정조치 {capa_no}: 효과적이지 않은 시정조치는 종결할 수 없습니다(10.2.1 d).",
        db=db,
        context=f"capa:{capa_no}",
    )
    db.update(
        "capa",
        capa["id"],
        effectiveness_reviewed_on=today(),
        effective=1,
        closed_on=today(),
        status="closed",
        actions=f"{capa['actions']}\n[효과성] {evidence}",
    )
    return db.fetch("capa", capa["id"])


def escalate(db: Database, capa_no: str, *, level: int) -> Row:
    """에스컬레이션 단계를 상향한다 (10.2.3 e)."""
    capa = db.require("capa", capa_no=capa_no)
    enforce(
        "CTL-033",
        level in ESCALATION_TARGETS and level > int(capa["escalation_level"]),
        f"시정조치 {capa_no}: 에스컬레이션은 현재 단계보다 높아야 합니다.",
        db=db,
        context=f"capa:{capa_no}",
    )
    db.update(
        "capa",
        capa["id"],
        escalation_level=level,
        escalated_to=ESCALATION_TARGETS[level],
    )
    return db.fetch("capa", capa["id"])


def require_capa_for(
    db: Database,
    *,
    source_type: str,
    source_ref: str,
    control_id: str = "CTL-020",
    purpose: str = "",
) -> Row:
    """해당 출처에 대해 시정조치가 등록되어 있는지 확인한다.

    KPI 목표 미달(9.1.3.1)·목표 미달(9.3.3.1) 시 시정조치 존재를 강제하는 데 쓰인다.
    """
    capa = db.one(
        "SELECT * FROM capa WHERE source_type = ? AND source_ref = ? "
        "ORDER BY opened_on DESC LIMIT 1",
        (source_type, source_ref),
    )
    enforce(
        control_id,
        capa is not None,
        f"{purpose or source_ref}: 시정조치가 등록되지 않았습니다"
        " (9.1.3.1 / 9.3.3.1 목표 미달 시 시정조치 필수).",
        db=db,
        context=purpose or f"{source_type}:{source_ref}",
    )
    assert capa is not None
    return capa


def open_capas(db: Database) -> list[Row]:
    return db.query("SELECT * FROM capa WHERE status != 'closed' ORDER BY due_on")


def overdue_capas(db: Database, *, as_of: str | None = None) -> list[Row]:
    """기한을 초과한 미종결 시정조치 (10.2.3 d)."""
    from ._base import is_past

    return [c for c in open_capas(db) if is_past(c["due_on"], as_of=as_of)]


# ------------------------------------------------------------------ 10.1 / 10.3
def record_improvement(
    db: Database,
    *,
    ref_no: str,
    kind: str,
    description: str,
    owner_id: int,
    source: str = "",
    benefit_note: str = "",
) -> int:
    """개선 항목을 등록한다 (10.1, 10.3)."""
    if kind not in IMPROVEMENT_KINDS:
        raise ValueError(f"알 수 없는 개선 유형: {kind}")
    return db.insert(
        "improvement",
        ref_no=ref_no,
        kind=kind,
        description=description,
        source=source,
        owner_id=owner_id,
        opened_on=today(),
        benefit_note=benefit_note,
    )
