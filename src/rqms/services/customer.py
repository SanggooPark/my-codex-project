"""CSA — 고객 의사소통 및 고객만족 관리 (8.2.1, 9.1.2).

강제 통제
    CTL-053  고객 불만은 접수 통보 및 시정조치 연계 관리 (9.1.2.1 a, b)
    CTL-028  불가피한 지연은 고객에게 통보 (8.2.1.1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import enforce

#: 8.2.1 a)~e) 고객 의사소통 범주
COMMUNICATION_TOPICS = (
    "product_service_information",
    "enquiries_contracts_orders",
    "customer_feedback_and_complaints",
    "customer_property",
    "contingency_actions",
)


def record_communication(
    db: Database,
    *,
    topic: str,
    customer: str,
    method: str,
    communicator: str,
    project_code: str | None = None,
) -> int:
    """고객 의사소통을 기록한다 (8.2.1)."""
    return db.insert(
        "communication_entry",
        kind="record",
        topic=topic,
        timing="as_occurred",
        audience=customer,
        method=method,
        communicator=communicator,
        project_code=project_code,
        occurred_on=today(),
    )


def notify_delay(
    db: Database,
    *,
    customer: str,
    project_code: str,
    reason: str,
    impact: str,
    countermeasure: str,
) -> int:
    """불가피한 지연을 고객에게 통보한다 (8.2.1.1, 8.1.3.8).

    영향과 대책이 함께 전달되어야 한다.
    """
    enforce(
        "CTL-028",
        bool(impact.strip()) and bool(countermeasure.strip()),
        f"{project_code}: 지연 통보에는 영향과 대책이 포함되어야 합니다(8.1.3.8).",
        db=db,
        context=f"delay_notification:{project_code}",
    )
    return db.insert(
        "communication_entry",
        kind="record",
        topic=f"납기 지연 통보 — 사유: {reason} / 영향: {impact} / 대책: {countermeasure}",
        timing="as_occurred",
        audience=customer,
        method="official_letter",
        communicator="project_manager",
        project_code=project_code,
        occurred_on=today(),
    )


def receive_complaint(
    db: Database,
    *,
    complaint_no: str,
    customer: str,
    description: str,
    nc_no: str | None = None,
) -> int:
    """고객 불만을 접수·기록한다 (9.1.2.1 a)."""
    nc_id = None
    if nc_no:
        nc_id = int(db.require("nonconformity", nc_no=nc_no)["id"])
    return db.insert(
        "complaint",
        complaint_no=complaint_no,
        customer=customer,
        description=description,
        received_on=today(),
        nonconformity_id=nc_id,
    )


def acknowledge(db: Database, complaint_no: str) -> Row:
    """고객에게 접수 사실을 통보한다 (9.1.2.1 b)."""
    complaint = db.require("complaint", complaint_no=complaint_no)
    db.update("complaint", complaint["id"], acknowledged_on=today())
    return db.fetch("complaint", complaint["id"])


def link_capa(db: Database, complaint_no: str, *, capa_no: str) -> Row:
    """불만에 시정조치를 연계한다 (9.1.2.1 b, 10.2)."""
    complaint = db.require("complaint", complaint_no=complaint_no)
    capa = db.require("capa", capa_no=capa_no)
    db.update("complaint", complaint["id"], capa_id=capa["id"])
    return db.fetch("complaint", complaint["id"])


def respond(db: Database, complaint_no: str, *, lesson_shared: bool) -> Row:
    """고객에게 시정조치 내용을 회신한다 (9.1.2.1 b).

    접수 통보와 시정조치 연계가 선행되어야 하며, 공통 해결책·교훈이 공유되어야 한다
    (9.1.2.1 a).
    """
    complaint = db.require("complaint", complaint_no=complaint_no)
    enforce(
        "CTL-053",
        bool(complaint["acknowledged_on"]),
        f"불만 {complaint_no}: 접수 통보 없이 회신할 수 없습니다(9.1.2.1 b).",
        db=db,
        context=f"complaint:{complaint_no}",
    )
    enforce(
        "CTL-053",
        complaint["capa_id"] is not None,
        f"불만 {complaint_no}: 시정조치(10.2) 연계 없이 회신할 수 없습니다(9.1.2.1 b).",
        db=db,
        context=f"complaint:{complaint_no}",
    )
    enforce(
        "CTL-053",
        lesson_shared,
        f"불만 {complaint_no}: 공통 해결책·교훈이 공유될 수 있도록 기록해야 합니다"
        " (9.1.2.1 a).",
        db=db,
        context=f"complaint:{complaint_no}",
    )
    db.update(
        "complaint",
        complaint["id"],
        response_on=today(),
        resolved_on=today(),
        lesson_shared=int(lesson_shared),
    )
    return db.fetch("complaint", complaint["id"])


def record_satisfaction(
    db: Database, *, customer: str, period: str, method: str, score: float, note: str = ""
) -> int:
    """고객만족 측정 결과를 기록한다 (9.1.2)."""
    existing = db.find("customer_satisfaction", customer=customer, period=period)
    if existing:
        db.update(
            "customer_satisfaction", existing["id"], method=method, score=score, note=note
        )
        return int(existing["id"])
    return db.insert(
        "customer_satisfaction",
        customer=customer,
        period=period,
        method=method,
        score=score,
        note=note,
    )


def average_satisfaction(db: Database, *, period: str) -> float | None:
    """기간 평균 고객만족도 (PI-CSAT)."""
    value = db.scalar(
        "SELECT AVG(score) FROM customer_satisfaction WHERE period = ?", (period,)
    )
    return None if value is None else round(float(value), 2)


def unacknowledged_complaints(db: Database) -> list[Row]:
    """접수 통보가 누락된 고객 불만 (9.1.2.1 b)."""
    return db.query("SELECT * FROM complaint WHERE acknowledged_on IS NULL")


def complaints_without_capa(db: Database) -> list[Row]:
    """시정조치가 연계되지 않은 고객 불만 (9.1.2.1 b)."""
    return db.query("SELECT * FROM complaint WHERE capa_id IS NULL")
