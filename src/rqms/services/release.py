"""REL — 제품·서비스 출하 프로세스 (8.6).

강제 통제
    CTL-017  계획된 검사·시험 미완료 시 출하 금지(특채 승인 시 예외) (8.6, 8.6.1)
    CTL-010  설계 유효성확인 미완료 품목의 인도 금지 (8.3.4.4 b)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import nonconformity
from ._base import enforce


def pending_inspections(db: Database, serial_no: str) -> list[Row]:
    """해당 품목에 대해 계획되었으나 완료되지 않은 검사·시험 (8.6)."""
    item = db.require("traceable_item", serial_no=serial_no)
    return db.query(
        "SELECT * FROM inspection "
        "WHERE (traceable_item_id = ? OR (traceable_item_id IS NULL "
        "       AND production_order_id = ?)) "
        "  AND planned = 1 AND (performed_on IS NULL OR result != 'pass')",
        (item["id"], item["production_order_id"]),
    )


def release_item(
    db: Database,
    *,
    serial_no: str,
    authorized_by_id: int,
    conformity_evidence: str,
    concession_id: int | None = None,
    design_no: str | None = None,
) -> int:
    """제품을 출하한다 (8.6, 8.6.1).

    - 계획된 검사·시험이 만족스럽게 완료되어야 하며, 그렇지 않으면 고객 특채가
      필요하다(8.6.1).
    - 출하 권한자와 적합성 증거가 기록된다(8.6 a, b).
    - 설계 유효성확인이 완료되어야 인도할 수 있다(8.3.4.4 b).
    """
    item = nonconformity.assert_item_identified(db, serial_no, f"출하 {serial_no}")
    enforce(
        "CTL-017",
        bool(conformity_evidence.strip()),
        f"출하 {serial_no}: 합격기준 적합 증거를 기록해야 합니다(8.6 a).",
        db=db,
        context=f"release:{serial_no}",
    )

    pending = pending_inspections(db, serial_no)
    if pending:
        steps = ", ".join(str(p["itp_step"]) for p in pending)
        enforce(
            "CTL-017",
            concession_id is not None,
            f"출하 {serial_no}: 계획된 검사·시험이 완료되지 않았습니다({steps})."
            " 출하하려면 고객 특채가 필요합니다(8.6.1).",
            db=db,
            context=f"release:{serial_no}",
        )
        assert concession_id is not None
        nonconformity.consume_concession(
            db, concession_id, qty=1, purpose=f"출하 {serial_no}"
        )
    elif concession_id is not None:
        nonconformity.consume_concession(
            db, concession_id, qty=1, purpose=f"출하 {serial_no}"
        )

    if design_no:
        from . import design as design_service

        design_service.assert_ready_for_delivery(db, design_no, f"출하 {serial_no}")

    release_id = db.insert(
        "release_record",
        traceable_item_id=item["id"],
        released_on=today(),
        authorized_by_id=authorized_by_id,
        conformity_evidence=conformity_evidence,
        concession_id=concession_id,
    )
    db.update("traceable_item", item["id"], status="released")
    return release_id


def deliver_item(db: Database, serial_no: str, *, design_no: str | None = None) -> Row:
    """출하된 제품을 고객에게 인도한다.

    출하 기록이 없으면 인도할 수 없고, 설계 유효성확인이 필요하다(CTL-010).
    """
    item = db.require("traceable_item", serial_no=serial_no)
    release = db.find("release_record", traceable_item_id=item["id"])
    enforce(
        "CTL-017",
        release is not None,
        f"인도 {serial_no}: 출하 기록 없이 인도할 수 없습니다(8.6).",
        db=db,
        context=f"delivery:{serial_no}",
    )
    if design_no:
        from . import design as design_service

        design_service.assert_ready_for_delivery(db, design_no, f"인도 {serial_no}")
    db.update("traceable_item", item["id"], status="delivered", delivered_on=today())
    return db.fetch("traceable_item", item["id"])


def on_time_delivery_rate(db: Database) -> float | None:
    """고객 납기준수율 (PI-COTD) — 인도일 대비 프로젝트 고객 인도일 기준."""
    rows = db.query(
        "SELECT ti.delivered_on, p.customer_delivery_on "
        "FROM traceable_item ti "
        "JOIN production_order po ON po.id = ti.production_order_id "
        "LEFT JOIN project p ON p.id = po.project_id "
        "WHERE ti.delivered_on IS NOT NULL AND p.customer_delivery_on IS NOT NULL"
    )
    if not rows:
        return None
    on_time = sum(1 for r in rows if r["delivered_on"] <= r["customer_delivery_on"])
    return round(on_time / len(rows) * 100, 2)


def released_without_authority(db: Database) -> list[Row]:
    """출하 권한자 기록이 없는 출하 (8.6 b)."""
    return db.query(
        "SELECT * FROM release_record WHERE authorized_by_id IS NULL "
        "OR TRIM(conformity_evidence) = ''"
    )
