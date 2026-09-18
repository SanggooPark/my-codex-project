"""NCO — 부적합 출력 관리 프로세스 (8.7).

강제 통제
    CTL-015  식별 또는 상태가 불명한 품목은 부적합품으로 처리 (8.5.2.1)
    CTL-018  특채의 유효기간 만료 또는 승인수량 초과 시 사용 금지 (8.7.3 f)
    CTL-019  고객승인 대상 특채는 인도 전 고객승인 필수, 공급자 특채는 내부승인 선행
             (8.7.3 g)
    CTL-033  부적합의 시정조치 필요성 평가 및 에스컬레이션 (10.2.1 b, 10.2.3 b, e)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import enforce, is_past

#: 8.7.1 a)~d) 및 8.7.3 c) 처리 방법
DISPOSITIONS = (
    "correction",
    "rework",
    "repair",
    "scrap",
    "segregate",
    "return",
    "concession",
)

#: 8.7.3 부적합 출처
SOURCES = ("internal", "customer", "external_provider", "process", "project", "design")

#: 10.2.3 b) 시정조치 필요성 평가 기준 — 아래 조건 중 하나라도 해당하면 시정조치 필수
CAPA_CRITERIA = (
    "safety_impact",
    "customer_origin",
    "repeated",
    "cost_above_threshold",
)

#: 10.2.3 e) 에스컬레이션 결정 기준 (비용 기준, 통화 단위는 조직 정의)
ESCALATION_COST_THRESHOLD = 10_000_000.0


def raise_nonconformity(
    db: Database,
    *,
    nc_no: str,
    source: str,
    description: str,
    qty: float = 0.0,
    ref: str = "",
    detected_at_stage: str = "",
    serial_no: str | None = None,
    supplier_code: str | None = None,
    cost: float = 0.0,
    safety_impact: bool = False,
) -> int:
    """부적합을 등록부에 등록한다 (8.7.1, 8.7.3 b)."""
    if source not in SOURCES:
        raise ValueError(f"알 수 없는 부적합 출처: {source}")

    item_id = None
    if serial_no:
        item = db.require("traceable_item", serial_no=serial_no)
        item_id = int(item["id"])
        db.update("traceable_item", item_id, status="nonconforming")
    supplier_id = None
    if supplier_code:
        supplier_id = int(db.require("supplier", code=supplier_code)["id"])

    return db.insert(
        "nonconformity",
        nc_no=nc_no,
        source=source,
        detected_at_stage=detected_at_stage,
        ref=ref,
        traceable_item_id=item_id,
        supplier_id=supplier_id,
        description=description,
        detected_on=today(),
        qty=qty,
        cost=cost,
        safety_impact=int(safety_impact),
        status="open",
    )


def quarantine_unknown_item(db: Database, serial_no: str, *, reason: str) -> int:
    """식별·상태가 불명한 품목을 부적합품으로 처리한다 (8.5.2.1, CTL-015)."""
    item = db.require("traceable_item", serial_no=serial_no)
    db.update("traceable_item", item["id"], status="nonconforming")
    return raise_nonconformity(
        db,
        nc_no=f"NC-UNK-{serial_no}",
        source="internal",
        description=f"식별/상태 불명 품목 — {reason} (8.5.2.1)",
        qty=1,
        serial_no=serial_no,
        detected_at_stage="identification",
    )


def assert_item_identified(db: Database, serial_no: str, purpose: str) -> Row:
    """품목의 식별·상태가 확인되었는지 검사한다 (CTL-015)."""
    item = db.require("traceable_item", serial_no=serial_no)
    enforce(
        "CTL-015",
        item["status"] != "unknown",
        f"{purpose}: 품목 {serial_no} 의 상태가 불명이므로 부적합품으로 관리해야 합니다"
        " (8.5.2.1).",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-015",
        bool(item["identification_method"]),
        f"{purpose}: 품목 {serial_no} 의 식별 방법이 정의되지 않았습니다(8.5.2.1).",
        db=db,
        context=purpose,
    )
    return item


def decide_disposition(
    db: Database,
    nc_no: str,
    *,
    disposition: str,
    authority_id: int,
    customer_informed: bool = False,
    concession_id: int | None = None,
) -> Row:
    """부적합 처리를 결정한다 (8.7.1, 8.7.2 d, 8.7.3 c).

    고객 통보가 필요한 처리(반품·특채)에서는 통보 사실이 기록되어야 하고,
    특채 처리는 특채 레코드가 연결되어야 한다.
    """
    if disposition not in DISPOSITIONS:
        raise ValueError(f"알 수 없는 처리방법: {disposition}")
    nc = db.require("nonconformity", nc_no=nc_no)
    if disposition == "concession":
        enforce(
            "CTL-019",
            concession_id is not None,
            f"부적합 {nc_no}: 특채 처리는 승인된 특채 레코드가 필요합니다(8.7.3 c) 2)).",
            db=db,
            context=f"nonconformity:{nc_no}",
        )
    db.update(
        "nonconformity",
        nc["id"],
        disposition=disposition,
        disposition_authority_id=authority_id,
        customer_informed_on=today() if customer_informed else None,
        concession_id=concession_id,
    )
    return db.fetch("nonconformity", nc["id"])


def verify_correction(db: Database, nc_no: str) -> Row:
    """시정(correction) 후 요구사항 적합성을 검증한다 (8.7.1 마지막 문단)."""
    nc = db.require("nonconformity", nc_no=nc_no)
    enforce(
        "CTL-033",
        nc["disposition"] in ("correction", "rework", "repair"),
        f"부적합 {nc_no}: 시정·재작업·수리 처리에만 적합성 재검증이 적용됩니다.",
        db=db,
        context=f"nonconformity:{nc_no}",
    )
    db.update("nonconformity", nc["id"], corrected_verified_on=today())
    if nc["traceable_item_id"]:
        db.update("traceable_item", int(nc["traceable_item_id"]), status="inspected")
    return db.fetch("nonconformity", nc["id"])


def evaluate_capa_need(
    db: Database, nc_no: str, *, repeated: bool = False, note: str = ""
) -> dict[str, object]:
    """시정조치 필요성을 기준에 따라 평가한다 (10.2.1 b, 10.2.3 b, e).

    기준 충족 시 시정조치가 필수가 되며, 비용·안전 영향에 따라 에스컬레이션 단계를
    산정한다.
    """
    nc = db.require("nonconformity", nc_no=nc_no)
    triggered = []
    if nc["safety_impact"]:
        triggered.append("safety_impact")
    if nc["source"] == "customer":
        triggered.append("customer_origin")
    if repeated:
        triggered.append("repeated")
    if float(nc["cost"]) >= ESCALATION_COST_THRESHOLD:
        triggered.append("cost_above_threshold")

    needed = bool(triggered)
    escalation = 0
    if nc["safety_impact"]:
        escalation = 3
    elif float(nc["cost"]) >= ESCALATION_COST_THRESHOLD:
        escalation = 2
    elif needed:
        escalation = 1

    db.update(
        "nonconformity",
        nc["id"],
        capa_needed=int(needed),
        capa_decision_note=note or f"기준 충족: {', '.join(triggered) or '없음'}",
    )
    return {
        "nc_no": nc_no,
        "capa_needed": needed,
        "criteria": triggered,
        "escalation_level": escalation,
    }


def link_capa(db: Database, nc_no: str, *, capa_id: int) -> Row:
    """부적합에 시정조치를 연결한다 (10.2)."""
    nc = db.require("nonconformity", nc_no=nc_no)
    db.update("nonconformity", nc["id"], capa_id=capa_id)
    return db.fetch("nonconformity", nc["id"])


def close(db: Database, nc_no: str) -> Row:
    """부적합을 종결한다.

    시정조치가 필요하다고 평가된 부적합은 시정조치가 연결·종결되어야 한다(CTL-033).
    """
    nc = db.require("nonconformity", nc_no=nc_no)
    enforce(
        "CTL-033",
        nc["capa_needed"] is not None,
        f"부적합 {nc_no}: 시정조치 필요성 평가(10.2.3 b) 없이 종결할 수 없습니다.",
        db=db,
        context=f"nonconformity:{nc_no}",
    )
    if nc["capa_needed"]:
        enforce(
            "CTL-033",
            nc["capa_id"] is not None,
            f"부적합 {nc_no}: 시정조치가 필요하다고 평가되었으나 연결된 시정조치가 없습니다"
            " (10.2.1 b).",
            db=db,
            context=f"nonconformity:{nc_no}",
        )
        capa = db.fetch("capa", int(nc["capa_id"]))
        enforce(
            "CTL-033",
            capa["status"] == "closed",
            f"부적합 {nc_no}: 시정조치 {capa['capa_no']} 가 종결되지 않았습니다.",
            db=db,
            context=f"nonconformity:{nc_no}",
        )
    db.update("nonconformity", nc["id"], status="closed")
    return db.fetch("nonconformity", nc["id"])


# ------------------------------------------------------------- 8.7.3 특채 관리
def raise_concession(
    db: Database,
    *,
    concession_no: str,
    kind: str,
    nc_no: str,
    description: str,
    qty_authorized: float,
    valid_until: str,
    customer_approval_required: bool,
    identification_agreed: bool = False,
    recorded_on_doc: str = "",
) -> int:
    """특채를 등록한다 (8.7.3 d) — 유효기간과 승인수량이 반드시 기록된다."""
    if kind not in ("internal", "customer", "external_provider"):
        raise ValueError(f"알 수 없는 특채 유형: {kind}")
    nc = db.require("nonconformity", nc_no=nc_no)
    enforce(
        "CTL-018",
        qty_authorized > 0 and bool(valid_until),
        f"특채 {concession_no}: 승인수량과 유효기간을 기록해야 합니다(8.7.3 d).",
        db=db,
        context=f"concession:{concession_no}",
    )
    return db.insert(
        "concession",
        concession_no=concession_no,
        kind=kind,
        nonconformity_id=nc["id"],
        description=description,
        qty_authorized=qty_authorized,
        valid_until=valid_until,
        customer_approval_required=int(customer_approval_required),
        identification_agreed=int(identification_agreed),
        recorded_on_doc=recorded_on_doc,
    )


def approve_concession_internally(
    db: Database, concession_no: str, *, approver_id: int
) -> Row:
    """특채를 내부 승인한다 (8.7.3 c) 2)).

    외부공급자 특채는 고객 제출 전에 내부 승인이 선행되어야 한다(8.7.3 g) 2)).
    """
    concession = db.require("concession", concession_no=concession_no)
    db.update(
        "concession",
        concession["id"],
        internally_approved_on=today(),
        internally_approved_by_id=approver_id,
    )
    return db.fetch("concession", concession["id"])


def approve_concession_by_customer(db: Database, concession_no: str) -> Row:
    """고객 특채 승인을 기록한다 (8.7.3 g) 1)).

    공급자 특채는 내부 승인이 선행되어야 하고(g) 2)), 제품 식별 방법이 고객과
    합의되어야 한다(g) 3)).
    """
    concession = db.require("concession", concession_no=concession_no)
    if concession["kind"] == "external_provider":
        enforce(
            "CTL-019",
            bool(concession["internally_approved_on"]),
            f"특채 {concession_no}: 외부공급자 특채는 고객 제출 전 내부 승인이 필요합니다"
            " (8.7.3 g) 2)).",
            db=db,
            context=f"concession:{concession_no}",
        )
    enforce(
        "CTL-019",
        bool(concession["identification_agreed"]),
        f"특채 {concession_no}: 특채 제품의 식별 방법을 고객과 합의해야 합니다"
        " (8.7.3 g) 3)).",
        db=db,
        context=f"concession:{concession_no}",
    )
    enforce(
        "CTL-019",
        bool(concession["recorded_on_doc"]),
        f"특채 {concession_no}: 특채 내용을 제품 적합성 선언서에 기재해야 합니다"
        " (8.7.3 g) 4)).",
        db=db,
        context=f"concession:{concession_no}",
    )
    db.update("concession", concession["id"], customer_approved_on=today())
    return db.fetch("concession", concession["id"])


def assert_concession_valid(
    db: Database, concession_id: int, *, qty: float, purpose: str
) -> Row:
    """특채가 사용 가능한 상태인지 확인한다 (8.7.3 f, g / CTL-018, CTL-019).

    - 유효기간이 만료되면 제품을 더 이상 사용할 수 없다(8.7.3 f).
    - 승인수량을 초과하여 사용할 수 없다(8.7.3 d).
    - 고객승인이 필요한 특채는 인도 전 고객승인이 있어야 한다(8.7.3 g) 1)).
    """
    concession = db.fetch("concession", concession_id)
    enforce(
        "CTL-018",
        not is_past(concession["valid_until"]),
        f"{purpose}: 특채 {concession['concession_no']} 의 유효기간이"
        f" {concession['valid_until']} 에 만료되어 제품을 사용할 수 없습니다(8.7.3 f).",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-018",
        float(concession["qty_used"]) + qty <= float(concession["qty_authorized"]),
        f"{purpose}: 특채 {concession['concession_no']} 의 승인수량"
        f"({concession['qty_authorized']})을 초과합니다"
        f" (기사용 {concession['qty_used']} + 요청 {qty}).",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-019",
        bool(concession["internally_approved_on"]),
        f"{purpose}: 특채 {concession['concession_no']} 의 내부 승인이 없습니다(8.7.3 c) 2)).",
        db=db,
        context=purpose,
    )
    if concession["customer_approval_required"]:
        enforce(
            "CTL-019",
            bool(concession["customer_approved_on"]),
            f"{purpose}: 특채 {concession['concession_no']} 는 인도 전 고객승인이"
            " 필요합니다(8.7.3 g) 1)).",
            db=db,
            context=purpose,
        )
    return concession


def consume_concession(db: Database, concession_id: int, *, qty: float, purpose: str) -> Row:
    """특채 사용수량을 차감 기록한다 (8.7.3 d, e)."""
    concession = assert_concession_valid(db, concession_id, qty=qty, purpose=purpose)
    used = float(concession["qty_used"]) + qty
    db.update(
        "concession",
        concession_id,
        qty_used=used,
        status="closed" if used >= float(concession["qty_authorized"]) else "open",
    )
    return db.fetch("concession", concession_id)


def refresh_concession_status(db: Database, *, as_of: str | None = None) -> list[Row]:
    """유효기간이 만료된 특채를 expired 로 표시한다 (8.7.3 e, f)."""
    expired = []
    for row in db.query("SELECT * FROM concession WHERE status = 'open'"):
        if is_past(row["valid_until"], as_of=as_of):
            db.update("concession", row["id"], status="expired")
            expired.append(row)
    return expired


def open_concessions(db: Database) -> list[Row]:
    return db.query("SELECT * FROM concession WHERE status = 'open'")


def register(db: Database) -> list[Row]:
    """부적합 출력 등록부 (8.7.3 b)."""
    return db.query("SELECT * FROM nonconformity ORDER BY detected_on DESC, nc_no")
