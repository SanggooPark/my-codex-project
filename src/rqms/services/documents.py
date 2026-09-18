"""DIC — 문서화된 정보 관리 프로세스 (7.5).

강제 통제
    CTL-001  승인되지 않은 문서의 배포·사용 금지 (7.5.2 c, 7.5.3.1)
    CTL-002  승인된 기록의 무결성 봉인 및 무단 변경 탐지 (7.5.3.2)
    CTL-003  기록 유형별 보존기간 정의 및 만료 전 폐기 금지 (7.5.3.3 d)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, seal_of, today
from ._base import add_months, enforce, is_past

#: 7.5.3.3 b) 문서 계층 — 숫자가 작을수록 상위
HIERARCHY = {
    "policy": 1,
    "manual": 1,
    "procedure": 2,
    "instruction": 3,
    "template": 4,
    "record": 5,
    "external": 5,
}

#: 7.5.3.3 기밀등급
CONFIDENTIALITY = ("public", "internal", "confidential")


def create(
    db: Database,
    *,
    doc_no: str,
    title: str,
    doc_type: str,
    version: str,
    author_id: int,
    content: str = "",
    record_type: str | None = None,
    retention_months: int | None = None,
    confidentiality: str = "internal",
) -> int:
    """문서를 초안으로 등록한다 (7.5.2 a) 식별, b) 형식)."""
    if doc_type not in HIERARCHY:
        raise ValueError(f"알 수 없는 문서 유형: {doc_type}")
    if confidentiality not in CONFIDENTIALITY:
        raise ValueError(f"알 수 없는 기밀등급: {confidentiality}")

    # CTL-003 — 기록은 보존기간이 정의되어야 한다 (7.5.3.3 d).
    if doc_type == "record":
        enforce(
            "CTL-003",
            bool(record_type) and bool(retention_months),
            f"기록 문서 {doc_no} 는 기록 유형과 보존기간을 정의해야 합니다.",
            db=db,
            context=f"document:{doc_no}",
        )

    doc_id = db.insert(
        "document",
        doc_no=doc_no,
        title=title,
        doc_type=doc_type,
        hierarchy_level=HIERARCHY[doc_type],
        version=version,
        status="draft",
        author_id=author_id,
        content=content,
        record_type=record_type,
        retention_months=retention_months,
        confidentiality=confidentiality,
    )
    _log(db, doc_id, "created", author_id)
    return doc_id


def submit_for_review(db: Database, doc_id: int, verifier_id: int) -> None:
    """검토자를 지정하고 검토 상태로 전이한다 (7.5.3.3 c)."""
    doc = db.fetch("document", doc_id)
    enforce(
        "CTL-001",
        doc["status"] == "draft",
        f"문서 {doc['doc_no']} 는 초안 상태에서만 검토 요청할 수 있습니다(현재 {doc['status']}).",
        db=db,
        context=f"document:{doc['doc_no']}",
    )
    db.update("document", doc_id, status="in_review", verifier_id=verifier_id)
    _log(db, doc_id, "submitted_for_review", verifier_id)


def approve(
    db: Database,
    doc_id: int,
    approver_id: int,
    *,
    effective_from: str | None = None,
) -> str:
    """문서를 승인하고 무결성 봉인을 생성한다 (7.5.2 c, 7.5.3.2)."""
    doc = db.fetch("document", doc_id)
    enforce(
        "CTL-001",
        doc["status"] == "in_review",
        f"문서 {doc['doc_no']} 는 검토를 거쳐야 승인할 수 있습니다(현재 {doc['status']}).",
        db=db,
        context=f"document:{doc['doc_no']}",
    )
    # 7.5.3.3 c) — 작성자와 승인자는 분리되어야 한다.
    enforce(
        "CTL-001",
        doc["author_id"] != approver_id,
        f"문서 {doc['doc_no']} 의 작성자는 승인자가 될 수 없습니다.",
        db=db,
        context=f"document:{doc['doc_no']}",
    )

    approved_on = today()
    seal = _seal(doc, approver_id, approved_on)
    db.update(
        "document",
        doc_id,
        status="approved",
        approver_id=approver_id,
        approved_on=approved_on,
        effective_from=effective_from or approved_on,
        seal=seal,
    )
    _log(db, doc_id, "approved", approver_id)
    return seal


def assert_usable(db: Database, doc_id: int | None, purpose: str) -> Row:
    """문서가 승인·유효 상태이며 봉인이 유지되는지 확인한다 (CTL-001, CTL-002).

    승인된 문서를 참조하는 모든 업무(생산 착수, 출하, 검사 등)의 공통 관문이다.
    """
    enforce(
        "CTL-001",
        doc_id is not None,
        f"{purpose}: 승인된 문서가 지정되지 않았습니다.",
        db=db,
        context=purpose,
    )
    assert doc_id is not None
    doc = db.fetch("document", doc_id)
    enforce(
        "CTL-001",
        doc["status"] == "approved",
        f"{purpose}: 문서 {doc['doc_no']} 가 승인 상태가 아닙니다({doc['status']}).",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-002",
        doc["seal"] == _seal(doc, doc["approver_id"], doc["approved_on"]),
        f"{purpose}: 문서 {doc['doc_no']} 의 무결성 봉인이 일치하지 않습니다(무단 변경 의심).",
        db=db,
        context=purpose,
    )
    return doc


def revise(db: Database, doc_id: int, new_version: str, author_id: int, content: str) -> int:
    """개정판을 발행하고 구판을 폐지한다 (7.5.3.2 c) 변경 관리)."""
    current = db.fetch("document", doc_id)
    enforce(
        "CTL-002",
        current["status"] == "approved",
        f"문서 {current['doc_no']} 는 승인된 판만 개정할 수 있습니다.",
        db=db,
        context=f"document:{current['doc_no']}",
    )
    new_id = create(
        db,
        doc_no=current["doc_no"],
        title=current["title"],
        doc_type=current["doc_type"],
        version=new_version,
        author_id=author_id,
        content=content,
        record_type=current["record_type"],
        retention_months=current["retention_months"],
        confidentiality=current["confidentiality"],
    )
    db.update("document", doc_id, status="obsolete", superseded_by=new_id)
    _log(db, doc_id, "superseded", author_id, note=f"-> v{new_version}")
    return new_id


def dispose(db: Database, doc_id: int, actor_id: int) -> None:
    """보존기간이 만료된 기록을 폐기한다 (7.5.3.2 d, CTL-003)."""
    doc = db.fetch("document", doc_id)
    if doc["doc_type"] == "record":
        reference = doc["approved_on"] or doc["effective_from"]
        enforce(
            "CTL-003",
            bool(reference) and bool(doc["retention_months"]),
            f"기록 {doc['doc_no']} 는 보존 기산일과 보존기간이 정의되어야 폐기할 수 있습니다.",
            db=db,
            context=f"document:{doc['doc_no']}",
        )
        expiry = add_months(reference, int(doc["retention_months"]))
        enforce(
            "CTL-003",
            is_past(expiry),
            f"기록 {doc['doc_no']} 는 보존기간 만료일({expiry}) 이전에 폐기할 수 없습니다.",
            db=db,
            context=f"document:{doc['doc_no']}",
        )
    db.update("document", doc_id, status="obsolete", disposed_on=today())
    _log(db, doc_id, "disposed", actor_id)


def retention_expiry(doc: Row) -> str | None:
    """기록의 보존기간 만료일을 계산한다."""
    reference = doc["approved_on"] or doc["effective_from"]
    if not reference or not doc["retention_months"]:
        return None
    return add_months(reference, int(doc["retention_months"]))


def broken_seals(db: Database) -> list[Row]:
    """봉인이 깨진 승인 문서 목록 (7.5.3.2)."""
    rows = db.query("SELECT * FROM document WHERE status = 'approved'")
    return [r for r in rows if r["seal"] != _seal(r, r["approver_id"], r["approved_on"])]


def _seal(doc: Row, approver_id: int | None, approved_on: str | None) -> str:
    return seal_of(
        [
            doc["doc_no"],
            doc["version"],
            doc["title"],
            doc["doc_type"],
            doc["content"],
            approver_id,
            approved_on,
        ]
    )


def _log(db: Database, doc_id: int, event: str, actor_id: int | None, note: str = "") -> None:
    db.insert(
        "document_event",
        doc_id=doc_id,
        event=event,
        actor_id=actor_id,
        occurred_on=today(),
        note=note,
    )
