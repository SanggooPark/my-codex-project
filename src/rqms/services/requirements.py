"""REQ — 제품·서비스 요구사항 관리 프로세스 (8.2).

강제 통제
    CTL-008  요구사항 조항별 검토 완료 전 입찰 제출·계약 수락 금지 (8.2.3.1, 8.2.5 e 1)
    CTL-046  요구사항의 기술규격 문서화 및 RAMS/LCC·단산·중요특성 반영
             (8.2.2.1.1, 8.2.5 e 6)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import enforce

#: Annex B — 요구사항 하위 개념
REQ_TYPES = (
    "functional",
    "performance",
    "integration",
    "non_functional",
    "non_technical",
    "rams",
    "lcc",
    "obsolescence",
    "critical_characteristic",
)

#: 8.2.2.1.1 a)~d) 요구사항 결정 시 반드시 고려해야 하는 범주
REQUIRED_CATEGORIES = ("functional", "non_functional", "rams", "critical_characteristic")

#: 3.1.3.7 운용 성숙도
MATURITY = ("not_existing", "under_development", "ready_to_use", "in_use")

#: 기술 요구사항으로 간주되어 검증·유효성확인 대상이 되는 유형 (8.3.4.3, 8.3.4.4)
TECHNICAL_TYPES = (
    "functional",
    "performance",
    "integration",
    "non_functional",
    "rams",
    "critical_characteristic",
)


def register(
    db: Database,
    *,
    req_no: str,
    owner_scope: str,
    owner_ref: str,
    req_type: str,
    text: str,
    source: str,
    operational_maturity: str = "not_existing",
) -> int:
    """요구사항을 등록한다 (8.2.2)."""
    if req_type not in REQ_TYPES:
        raise ValueError(f"알 수 없는 요구사항 유형: {req_type} (Annex B)")
    if operational_maturity not in MATURITY:
        raise ValueError(f"알 수 없는 운용성숙도: {operational_maturity}")
    return db.insert(
        "requirement",
        req_no=req_no,
        owner_scope=owner_scope,
        owner_ref=owner_ref,
        req_type=req_type,
        text=text,
        source=source,
        operational_maturity=operational_maturity,
    )


def review_clause_by_clause(
    db: Database,
    req_id: int,
    *,
    result: str,
    risk_assessed: bool,
    verifiable: bool,
    cascaded: bool,
    verification_method: str,
    validation_method: str,
) -> Row:
    """요구사항을 조항별로 검토한다 (8.2.5 e) 1)~5)).

    검증·유효성확인 방법이 없으면 "검증 가능"으로 볼 수 없으므로 검토를 거부한다.
    """
    requirement = db.fetch("requirement", req_id)
    enforce(
        "CTL-008",
        bool(result.strip()),
        f"요구사항 {requirement['req_no']}: 조항별 검토 결과를 기록해야 합니다(8.2.5 e 1).",
        db=db,
        context=f"requirement:{requirement['req_no']}",
    )
    if requirement["req_type"] in TECHNICAL_TYPES:
        enforce(
            "CTL-008",
            verifiable
            and bool(verification_method.strip())
            and bool(validation_method.strip()),
            f"요구사항 {requirement['req_no']}: 기술 요구사항은 검증·유효성확인 방법이"
            " 정의되어야 합니다(8.2.5 d 3, 4 / e 5).",
            db=db,
            context=f"requirement:{requirement['req_no']}",
        )
    db.update(
        "requirement",
        req_id,
        reviewed=1,
        review_result=result,
        risk_assessed=int(risk_assessed),
        verifiable=int(verifiable),
        cascaded=int(cascaded),
        verification_method=verification_method,
        validation_method=validation_method,
    )
    return db.fetch("requirement", req_id)


def document_specification(db: Database, *, owner_scope: str, owner_ref: str, doc_id: int) -> int:
    """검토 완료된 요구사항을 기술규격으로 문서화한다 (8.2.5 e) 6)).

    범주(기능·비기능·RAMS·중요특성)가 누락되면 기술규격을 확정할 수 없다(8.2.2.1.1).
    """
    documents.assert_usable(db, doc_id, f"기술규격 {owner_scope}:{owner_ref}")
    rows = _for_owner(db, owner_scope, owner_ref)
    enforce(
        "CTL-046",
        bool(rows),
        f"{owner_scope}:{owner_ref} 에 등록된 요구사항이 없습니다.",
        db=db,
        context=f"specification:{owner_ref}",
    )
    present = {r["req_type"] for r in rows}
    missing = [c for c in REQUIRED_CATEGORIES if c not in present]
    enforce(
        "CTL-046",
        not missing,
        f"{owner_scope}:{owner_ref} 기술규격에 누락된 요구사항 범주(8.2.2.1.1): "
        f"{', '.join(missing)}",
        db=db,
        context=f"specification:{owner_ref}",
    )
    unreviewed = [r["req_no"] for r in rows if not r["reviewed"]]
    enforce(
        "CTL-008",
        not unreviewed,
        f"{owner_scope}:{owner_ref} 미검토 요구사항이 있어 기술규격을 확정할 수 없습니다: "
        f"{', '.join(unreviewed)}",
        db=db,
        context=f"specification:{owner_ref}",
    )
    for row in rows:
        db.update("requirement", row["id"], spec_doc_id=doc_id)
    return doc_id


def assert_all_reviewed(db: Database, *, owner_scope: str, owner_ref: str, purpose: str) -> None:
    """해당 범위의 모든 요구사항이 조항별 검토를 마쳤는지 확인한다 (CTL-008)."""
    rows = _for_owner(db, owner_scope, owner_ref)
    enforce(
        "CTL-008",
        bool(rows),
        f"{purpose}: 요구사항이 등록되지 않았습니다(8.2.2).",
        db=db,
        context=purpose,
    )
    pending = [r["req_no"] for r in rows if not r["reviewed"]]
    enforce(
        "CTL-008",
        not pending,
        f"{purpose}: 조항별 검토가 완료되지 않은 요구사항이 있습니다: {', '.join(pending)}",
        db=db,
        context=purpose,
    )


def mark_verified(db: Database, req_id: int, *, on: str | None = None) -> None:
    """요구사항 검증 완료를 기록한다 (8.3.4.3)."""
    requirement = db.fetch("requirement", req_id)
    enforce(
        "CTL-046",
        bool(requirement["verification_method"]),
        f"요구사항 {requirement['req_no']}: 검증 방법이 정의되지 않았습니다(8.2.5 d 3).",
        db=db,
        context=f"requirement:{requirement['req_no']}",
    )
    db.update("requirement", req_id, verified_on=on or today())


def mark_validated(db: Database, req_id: int, *, on: str | None = None) -> None:
    """요구사항 유효성확인 완료를 기록한다 (8.3.4.4)."""
    requirement = db.fetch("requirement", req_id)
    enforce(
        "CTL-046",
        bool(requirement["validation_method"]),
        f"요구사항 {requirement['req_no']}: 유효성확인 방법이 정의되지 않았습니다(8.2.5 d 4).",
        db=db,
        context=f"requirement:{requirement['req_no']}",
    )
    db.update("requirement", req_id, validated_on=on or today())


def apply_change(db: Database, req_id: int, *, change_no: str, new_text: str) -> None:
    """승인된 변경에 따라 요구사항을 갱신한다 (8.2.4, 8.2.5 e 7)).

    변경은 change 서비스에서 승인 여부가 확인된 뒤 호출된다.
    """
    db.update(
        "requirement",
        req_id,
        text=new_text,
        reviewed=0,
        review_result="",
        superseded_by_change=change_no,
    )


def unverified_technical(db: Database, *, owner_scope: str, owner_ref: str) -> list[Row]:
    """검증되지 않은 기술 요구사항 (8.3.4.3)."""
    rows = _for_owner(db, owner_scope, owner_ref)
    return [
        r for r in rows if r["req_type"] in TECHNICAL_TYPES and not r["verified_on"]
    ]


def unvalidated_technical(db: Database, *, owner_scope: str, owner_ref: str) -> list[Row]:
    """유효성확인되지 않은 기술 요구사항 (8.3.4.4)."""
    rows = _for_owner(db, owner_scope, owner_ref)
    return [
        r for r in rows if r["req_type"] in TECHNICAL_TYPES and not r["validated_on"]
    ]


def _for_owner(db: Database, owner_scope: str, owner_ref: str) -> list[Row]:
    return db.query(
        "SELECT * FROM requirement WHERE owner_scope = ? AND owner_ref = ? ORDER BY req_no",
        (owner_scope, owner_ref),
    )
