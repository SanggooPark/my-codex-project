"""PDA — 인도 후 활동 프로세스 (8.5.5).

강제 통제
    CTL-059  인도 후 활동의 기술문서 갱신 및 승인된 수리지침 보유 (8.5.5.1 b, d)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import enforce

#: 8.5.5.1 활동 유형
KINDS = ("warranty", "maintenance", "training", "spare_parts", "disposal")

#: 8.5.5.1 c) 문제해결 기법
PROBLEM_SOLVING = ("8D", "FRACAS", "4D", "5why")


def record(
    db: Database,
    *,
    ref_no: str,
    product: str,
    customer: str,
    activity_kind: str,
    technical_doc_id: int,
    problem_solving_method: str,
    repair_instruction_doc_id: int | None = None,
    consignment_stock: str = "",
    feedback_to_rqms: str = "",
) -> int:
    """인도 후 활동을 기록한다 (8.5.5.1 a~f).

    기술문서(운전지침·정비매뉴얼·예비품 목록)는 승인·최신 상태여야 하고(b),
    수리 활동은 승인된 수리지침이 필요하다(d).
    """
    if activity_kind not in KINDS:
        raise ValueError(f"알 수 없는 인도 후 활동 유형: {activity_kind}")
    if problem_solving_method not in PROBLEM_SOLVING:
        raise ValueError(f"알 수 없는 문제해결 기법: {problem_solving_method} (8.5.5.1 c)")

    documents.assert_usable(db, technical_doc_id, f"인도 후 기술문서 {ref_no}")
    if activity_kind in ("warranty", "maintenance"):
        enforce(
            "CTL-059",
            repair_instruction_doc_id is not None,
            f"인도 후 활동 {ref_no}: 승인된 수리지침이 필요합니다(8.5.5.1 d).",
            db=db,
            context=f"post_delivery:{ref_no}",
        )
        documents.assert_usable(
            db, repair_instruction_doc_id, f"수리지침 {ref_no}"
        )
    enforce(
        "CTL-059",
        bool(feedback_to_rqms.strip()),
        f"인도 후 활동 {ref_no}: 고객 불만·현장 정보를 RQMS 개선 입력으로 환류해야 합니다"
        " (8.5.5.1 f).",
        db=db,
        context=f"post_delivery:{ref_no}",
    )
    return db.insert(
        "post_delivery_activity",
        ref_no=ref_no,
        product=product,
        customer=customer,
        activity_kind=activity_kind,
        performed_on=today(),
        technical_doc_id=technical_doc_id,
        repair_instruction_doc_id=repair_instruction_doc_id,
        problem_solving_method=problem_solving_method,
        consignment_stock=consignment_stock,
        feedback_to_rqms=feedback_to_rqms,
    )


def activities_without_feedback(db: Database) -> list[Row]:
    """RQMS 환류가 기록되지 않은 인도 후 활동 (8.5.5.1 f)."""
    return db.query(
        "SELECT * FROM post_delivery_activity WHERE TRIM(feedback_to_rqms) = ''"
    )


def repairs_without_instruction(db: Database) -> list[Row]:
    """승인된 수리지침 없이 수행된 보증·정비 활동 (8.5.5.1 d)."""
    return db.query(
        "SELECT * FROM post_delivery_activity "
        "WHERE activity_kind IN ('warranty', 'maintenance') "
        "  AND repair_instruction_doc_id IS NULL"
    )
