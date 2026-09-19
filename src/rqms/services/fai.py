"""FAI — 초도품 검사 관리 프로세스 (8.9).

강제 통제
    CTL-016  FAI 승인 전 양산 출시·공정 유효성확인 완료 금지 (8.9.1, 8.9.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import enforce

#: 8.9.3 a) FAI 적용 대상
TARGET_KINDS = ("internal_product", "eppps", "production_equipment", "process_transfer")

#: 8.9.3 b) FAI 실시 계기
TRIGGERS = (
    "new_product",
    "significant_change",
    "process_verification",
    "invalidated_fai",
    "transfer",
)

#: 8.9.1 d) 결정 유형
DECISIONS = ("approved", "conditional", "rejected")


def plan(
    db: Database,
    *,
    fai_no: str,
    target_kind: str,
    target_ref: str,
    trigger: str,
    plan_doc_id: int,
    participants: str,
    representative_serial: str = "",
) -> int:
    """FAI 를 계획한다 (8.9.1 a, b / 8.9.2 b).

    적용 계기(신제품·중대변경 등)와 참석자, 대표 시료가 정의되어야 한다.
    """
    if target_kind not in TARGET_KINDS:
        raise ValueError(f"알 수 없는 FAI 대상: {target_kind}")
    if trigger not in TRIGGERS:
        raise ValueError(f"알 수 없는 FAI 계기: {trigger}")
    documents.assert_usable(db, plan_doc_id, f"FAI 계획 {fai_no}")
    enforce(
        "CTL-016",
        bool(participants.strip()),
        f"FAI {fai_no}: 대상에 따른 참석자를 정의해야 합니다(8.9.2 b).",
        db=db,
        context=f"fai:{fai_no}",
    )
    if target_kind in ("internal_product", "eppps"):
        enforce(
            "CTL-016",
            bool(representative_serial.strip()),
            f"FAI {fai_no}: 최초 양산 로트의 대표 시료를 지정해야 합니다(8.9.3 b).",
            db=db,
            context=f"fai:{fai_no}",
        )
    return db.insert(
        "fai",
        fai_no=fai_no,
        target_kind=target_kind,
        target_ref=target_ref,
        trigger=trigger,
        plan_doc_id=plan_doc_id,
        participants=participants,
        representative_serial=representative_serial,
    )


def confirm_preconditions(db: Database, fai_no: str, *, evidence: str) -> Row:
    """FAI 실시 전 사전조건을 평가한다 (8.9.2 a)."""
    fai = db.require("fai", fai_no=fai_no)
    enforce(
        "CTL-016",
        bool(evidence.strip()),
        f"FAI {fai_no}: 사전조건 평가 증거가 필요합니다(8.9.2 a).",
        db=db,
        context=f"fai:{fai_no}",
    )
    db.update("fai", fai["id"], preconditions_ok=1)
    return db.fetch("fai", fai["id"])


def perform_inspection(
    db: Database, fai_no: str, *, process_review_done: bool
) -> Row:
    """검사·검증 활동을 실시한다 (8.9.1 c).

    중요공정·특수공정에 중점을 둔 생산공정 검토가 포함되어야 한다.
    """
    fai = db.require("fai", fai_no=fai_no)
    enforce(
        "CTL-016",
        bool(fai["preconditions_ok"]),
        f"FAI {fai_no}: 사전조건 평가 없이 검사를 실시할 수 없습니다(8.9.2 a).",
        db=db,
        context=f"fai:{fai_no}",
    )
    enforce(
        "CTL-016",
        process_review_done,
        f"FAI {fai_no}: 중요·특수공정에 중점을 둔 생산공정 검토가 필요합니다(8.9.1 c).",
        db=db,
        context=f"fai:{fai_no}",
    )
    db.update(
        "fai",
        fai["id"],
        inspection_done_on=today(),
        process_review_done=int(process_review_done),
    )
    return db.fetch("fai", fai["id"])


def decide(
    db: Database,
    fai_no: str,
    *,
    decision: str,
    decided_by_id: int,
    capa_id: int | None = None,
) -> Row:
    """FAI 결정을 기록한다 (8.9.1 d, e).

    조건부 승인 또는 거부 시에는 시정조치가 연결되어야 한다(8.9.1 e).
    """
    if decision not in DECISIONS:
        raise ValueError(f"알 수 없는 FAI 결정: {decision}")
    fai = db.require("fai", fai_no=fai_no)
    enforce(
        "CTL-016",
        bool(fai["inspection_done_on"]),
        f"FAI {fai_no}: 검사·검증 실시 없이 결정할 수 없습니다(8.9.1 c).",
        db=db,
        context=f"fai:{fai_no}",
    )
    if decision in ("conditional", "rejected"):
        enforce(
            "CTL-016",
            capa_id is not None,
            f"FAI {fai_no}: 조건부 승인·거부 시 시정조치 후속조치가 필요합니다(8.9.1 e).",
            db=db,
            context=f"fai:{fai_no}",
        )
    db.update(
        "fai",
        fai["id"],
        decision=decision,
        decided_on=today(),
        decided_by_id=decided_by_id,
        capa_id=capa_id,
    )
    return db.fetch("fai", fai["id"])


def assert_approved(db: Database, fai_id: int | None, purpose: str) -> Row:
    """양산 출시·공정 유효성확인 전 FAI 승인을 확인한다 (CTL-016)."""
    enforce(
        "CTL-016",
        fai_id is not None,
        f"{purpose}: FAI 없이 진행할 수 없습니다(8.5.1.1.4.1 c, 8.9.3 a).",
        db=db,
        context=purpose,
    )
    assert fai_id is not None
    fai = db.fetch("fai", fai_id)
    enforce(
        "CTL-016",
        fai["decision"] in ("approved", "conditional"),
        f"{purpose}: FAI {fai['fai_no']} 의 결정이 {fai['decision']} 이므로 양산 출시를"
        " 할 수 없습니다(8.9.1 d).",
        db=db,
        context=purpose,
    )
    return fai


def invalidate(db: Database, fai_no: str, *, reason: str) -> Row:
    """변경으로 기존 FAI 결과가 무효화되었음을 기록한다 (8.9.3 b) 2))."""
    fai = db.require("fai", fai_no=fai_no)
    db.update("fai", fai["id"], decision="rejected")
    db.insert(
        "lesson_learned",
        source_type="project",
        source_ref=fai_no,
        description=f"FAI 무효화: {reason} (8.9.3 b 2)",
        is_good_practice=0,
        communicated_to="quality,production",
        created_on=today(),
    )
    return db.fetch("fai", fai["id"])


def first_pass_rate(db: Database) -> float | None:
    """FAI 일발 합격률 (PI-FAI)."""
    total = db.count("SELECT COUNT(*) FROM fai WHERE decision IS NOT NULL")
    if total == 0:
        return None
    approved = db.count("SELECT COUNT(*) FROM fai WHERE decision = 'approved'")
    return round(approved / total * 100, 2)
