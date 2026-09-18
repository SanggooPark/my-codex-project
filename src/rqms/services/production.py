"""PSP — 생산 및 서비스 제공 프로세스 (8.5.1, 8.5.2, 8.5.3, 8.5.4).

강제 통제
    CTL-016  FAI 완료 없이 공정 유효성확인·양산 출시 금지 (8.5.1.1.4.1 c)
    CTL-050  승인된 생산데이터 없이 생산 착수 금지 (8.5.1.1.2 a, 8.5.1.1.3)
    CTL-051  생산설비 개별식별·예방정비·최초 사용 전 유효성확인 (8.5.1.4.1)
    CTL-052  보존 규격 문서화 및 고객·공급자 소유물 추적성 (8.5.3.1, 8.5.4.1)
    CTL-032  추적성 요구 품목은 보증종료까지 추적성 유지 (8.5.2.1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents, fai, special_processes
from ._base import add_months, enforce, is_past

#: 8.5.1.1.2 a) 1) 승인된 생산 데이터에 포함되어야 하는 항목
PRODUCTION_DATA_ITEMS = (
    "drawings",
    "bill_of_material",
    "process_flow_chart",
    "inspection_test_planning",
    "production_documents",
)

#: 8.5.1.2.1 a) 생산 일정계획 지평
SCHEDULE_HORIZONS = ("short_term", "master_production_schedule", "sales_and_operation_plan")


# ------------------------------------------------------------- 8.5.1 생산 오더
def create_order(
    db: Database,
    *,
    order_no: str,
    item: str,
    qty: float,
    approved_data_doc_id: int,
    itp_doc_id: int,
    risk_assessment: str,
    tool_program_list: str,
    project_code: str | None = None,
    config_part_no: str | None = None,
    special_process_codes: str = "",
    is_first_run: bool = False,
    scheduled_start_on: str | None = None,
    scheduled_finish_on: str | None = None,
    shift: str = "day",
) -> int:
    """생산 오더를 생성한다 (8.5.1.1.2 관리된 조건).

    승인된 생산 데이터와 검사·시험계획(ITP)이 있어야 하고, 생산활동 전반에 대한
    리스크 평가가 있어야 한다(8.5.1.1.2 e).
    """
    documents.assert_usable(db, approved_data_doc_id, f"생산데이터 {order_no}")
    documents.assert_usable(db, itp_doc_id, f"검사·시험계획 {order_no}")
    enforce(
        "CTL-050",
        bool(risk_assessment.strip()),
        f"생산오더 {order_no}: 생산·서비스 제공 활동 전반의 리스크 평가가 필요합니다"
        " (8.5.1.1.2 e).",
        db=db,
        context=f"production_order:{order_no}",
    )
    enforce(
        "CTL-050",
        bool(tool_program_list.strip()),
        f"생산오더 {order_no}: 필요한 치공구·NC 프로그램 목록이 필요합니다"
        " (8.5.1.1.2 a) 2)).",
        db=db,
        context=f"production_order:{order_no}",
    )

    project_id = None
    if project_code:
        project_id = int(db.require("project", code=project_code)["id"])
    config_item_id = None
    if config_part_no:
        config_item_id = int(
            db.require("config_item", project_id=project_id, part_no=config_part_no)["id"]
        )
    return db.insert(
        "production_order",
        order_no=order_no,
        project_id=project_id,
        config_item_id=config_item_id,
        item=item,
        qty=qty,
        approved_data_doc_id=approved_data_doc_id,
        tool_program_list=tool_program_list,
        itp_doc_id=itp_doc_id,
        risk_assessment=risk_assessment,
        special_process_codes=special_process_codes,
        is_first_run=int(is_first_run),
        scheduled_start_on=scheduled_start_on,
        scheduled_finish_on=scheduled_finish_on,
        shift=shift,
    )


def verify_process(
    db: Database,
    order_no: str,
    *,
    design_input_complete: bool,
    equipment_capable: bool,
    process_fmea: str,
) -> Row:
    """생산공정을 검증한다 (8.5.1.1.3 a~c)."""
    order = db.require("production_order", order_no=order_no)
    enforce(
        "CTL-050",
        design_input_complete,
        f"생산오더 {order_no}: 설계·개발 출력 대비 생산 입력의 완전성을 검증해야 합니다"
        " (8.5.1.1.3 a).",
        db=db,
        context=f"production_order:{order_no}",
    )
    enforce(
        "CTL-050",
        equipment_capable,
        f"생산오더 {order_no}: 생산설비의 설계요구 충족 능력을 검증해야 합니다"
        " (8.5.1.1.3 b).",
        db=db,
        context=f"production_order:{order_no}",
    )
    enforce(
        "CTL-050",
        bool(process_fmea.strip()),
        f"생산오더 {order_no}: 공정 초기 단계의 리스크 평가(예: 공정 FMEA)가 필요합니다"
        " (8.5.1.1.3 c).",
        db=db,
        context=f"production_order:{order_no}",
    )
    db.update("production_order", order["id"], process_verified_on=today())
    return db.fetch("production_order", order["id"])


def validate_process(
    db: Database,
    order_no: str,
    *,
    fai_id: int,
    design_requirements_met: bool,
    controlled_conditions_met: bool,
    design_feedback: str,
) -> Row:
    """생산공정을 유효성확인한다 (8.5.1.1.4.1 a~f).

    FAI 완료(c)가 전제이며, 설계·개발로의 환류(f)가 기록되어야 한다.
    """
    order = db.require("production_order", order_no=order_no)
    enforce(
        "CTL-050",
        bool(order["process_verified_on"]),
        f"생산오더 {order_no}: 공정 검증(8.5.1.1.3) 없이 유효성확인할 수 없습니다.",
        db=db,
        context=f"production_order:{order_no}",
    )
    enforce(
        "CTL-050",
        design_requirements_met and controlled_conditions_met,
        f"생산오더 {order_no}: 설계요구 충족과 관리된 조건 달성이 확인되어야 합니다"
        " (8.5.1.1.4.1 a, b).",
        db=db,
        context=f"production_order:{order_no}",
    )
    fai.assert_approved(db, fai_id, f"생산오더 {order_no} 공정 유효성확인")
    enforce(
        "CTL-050",
        bool(design_feedback.strip()),
        f"생산오더 {order_no}: 설계·개발로의 환류를 기록해야 합니다(8.5.1.1.4.1 f).",
        db=db,
        context=f"production_order:{order_no}",
    )
    db.update(
        "production_order",
        order["id"],
        fai_id=fai_id,
        process_validated_on=today(),
    )
    return db.fetch("production_order", order["id"])


def release_serial_production(db: Database, order_no: str) -> Row:
    """양산을 출시한다 (8.9.3 a, 8.5.1.1.4.1 c / CTL-016)."""
    order = db.require("production_order", order_no=order_no)
    fai.assert_approved(db, order["fai_id"], f"생산오더 {order_no} 양산 출시")
    enforce(
        "CTL-016",
        bool(order["process_validated_on"]),
        f"생산오더 {order_no}: 생산공정 유효성확인 없이 양산을 출시할 수 없습니다"
        " (8.5.1.1.4.1).",
        db=db,
        context=f"production_order:{order_no}",
    )
    db.update(
        "production_order",
        order["id"],
        serial_production_released_on=today(),
        status="released",
    )
    return db.fetch("production_order", order["id"])


def start_order(db: Database, order_no: str, *, operator_ids: dict[str, int] | None = None) -> Row:
    """생산을 착수한다.

    승인된 생산데이터가 유효해야 하고(CTL-050), 특수공정을 포함하는 경우 공정·작업자
    자격이 유효해야 한다(CTL-014).
    """
    order = db.require("production_order", order_no=order_no)
    documents.assert_usable(
        db, order["approved_data_doc_id"], f"생산오더 {order_no} 착수"
    )
    documents.assert_usable(db, order["itp_doc_id"], f"생산오더 {order_no} 착수")
    enforce(
        "CTL-050",
        bool(order["process_verified_on"]),
        f"생산오더 {order_no}: 공정 검증(8.5.1.1.3) 없이 착수할 수 없습니다.",
        db=db,
        context=f"production_order:{order_no}",
    )
    codes = [c.strip() for c in (order["special_process_codes"] or "").split(",") if c.strip()]
    if codes:
        operator_ids = operator_ids or {}
        for code in codes:
            operator_id = operator_ids.get(code)
            enforce(
                "CTL-014",
                operator_id is not None,
                f"생산오더 {order_no}: 특수공정 {code} 의 작업자가 지정되지 않았습니다"
                " (8.5.1.3 b) 5)).",
                db=db,
                context=f"production_order:{order_no}",
            )
            assert operator_id is not None
            special_processes.assert_executable(
                db,
                code,
                operator_id=operator_id,
                purpose=f"생산오더 {order_no} 착수",
            )
    db.update("production_order", order["id"], status="in_progress")
    return db.fetch("production_order", order["id"])


# ---------------------------------------------------------- 8.5.2 식별·추적성
def create_item(
    db: Database,
    *,
    serial_no: str,
    order_no: str,
    identification_method: str,
    warranty_months: int,
    traceability_required: bool = True,
) -> int:
    """추적 가능한 품목을 생성한다 (8.5.2, 8.5.2.1).

    추적성이 요구되는 품목은 식별 방법과 보증종료일이 정의되어야 한다.
    """
    order = db.require("production_order", order_no=order_no)
    if traceability_required:
        enforce(
            "CTL-032",
            bool(identification_method.strip()) and warranty_months > 0,
            f"품목 {serial_no}: 추적성 요구 품목은 식별 방법과 보증기간이 필요합니다"
            " (8.5.2.1).",
            db=db,
            context=f"traceable_item:{serial_no}",
        )
    return db.insert(
        "traceable_item",
        serial_no=serial_no,
        config_item_id=order["config_item_id"],
        production_order_id=order["id"],
        identification_method=identification_method,
        traceability_required=int(traceability_required),
        warranty_end_on=add_months(today(), warranty_months) if warranty_months else None,
        status="in_process",
    )


def record_inspection(
    db: Database,
    *,
    order_no: str,
    serial_no: str | None,
    itp_step: str,
    acceptance_criteria: str,
    result: str,
    actual_data: str,
    inspector_id: int,
    measuring_resource_id: int | None = None,
) -> int:
    """검사·시험 결과를 기록한다 (8.6.1 d~f).

    측정자원을 사용하는 경우 교정 상태가 유효해야 한다(CTL-025).
    실제 측정값이 기록되어야 한다(8.6.1 "실제 결과 데이터").
    """
    from . import calibration

    order = db.require("production_order", order_no=order_no)
    item_id = None
    if serial_no:
        item_id = int(db.require("traceable_item", serial_no=serial_no)["id"])
    if result not in ("pass", "fail"):
        raise ValueError("result 는 pass 또는 fail 여야 합니다.")
    enforce(
        "CTL-017",
        bool(actual_data.strip()),
        f"검사 {order_no}/{itp_step}: 실제 결과 데이터를 기록해야 합니다(8.6.1).",
        db=db,
        context=f"inspection:{order_no}",
    )
    calibration.assert_usable(
        db, measuring_resource_id, f"검사 {order_no}/{itp_step}"
    )
    inspection_id = db.insert(
        "inspection",
        production_order_id=order["id"],
        traceable_item_id=item_id,
        itp_step=itp_step,
        acceptance_criteria=acceptance_criteria,
        performed_on=today(),
        result=result,
        actual_data=actual_data,
        inspector_id=inspector_id,
        measuring_resource_id=measuring_resource_id,
    )
    if item_id is not None:
        db.update(
            "traceable_item",
            item_id,
            status="inspected" if result == "pass" else "nonconforming",
        )
    return inspection_id


def traceability_gaps(db: Database, *, as_of: str | None = None) -> list[Row]:
    """보증종료 전인데 추적성 정보가 불완전한 품목 (8.5.2.1, CTL-032)."""
    rows = db.query("SELECT * FROM traceable_item WHERE traceability_required = 1")
    out = []
    for row in rows:
        if row["status"] == "scrapped":
            continue
        warranty_open = not is_past(row["warranty_end_on"], as_of=as_of)
        if warranty_open and (
            not row["identification_method"] or not row["warranty_end_on"]
        ):
            out.append(row)
    return out


# ------------------------------------------------- 8.5.3 고객·공급자 소유물
def receive_external_property(
    db: Database,
    *,
    ref_no: str,
    owner_kind: str,
    owner_name: str,
    description: str,
    protection_measure: str,
) -> int:
    """고객·외부공급자 소유물을 인수한다 (8.5.3, 8.5.3.1)."""
    if owner_kind not in ("customer", "external_provider"):
        raise ValueError("owner_kind 는 customer 또는 external_provider 여야 합니다.")
    enforce(
        "CTL-052",
        bool(protection_measure.strip()),
        f"소유물 {ref_no}: 보호·보전 조치를 정의해야 합니다(8.5.3).",
        db=db,
        context=f"external_property:{ref_no}",
    )
    return db.insert(
        "external_property",
        ref_no=ref_no,
        owner_kind=owner_kind,
        owner_name=owner_name,
        description=description,
        received_on=today(),
        verified_on=today(),
        protection_measure=protection_measure,
        status="held",
    )


def report_property_issue(
    db: Database, ref_no: str, *, status: str, cause_analysis: str
) -> Row:
    """소유물의 분실·손상을 소유자에게 보고한다 (8.5.3, 8.5.3.1)."""
    if status not in ("lost", "damaged"):
        raise ValueError("status 는 lost 또는 damaged 여야 합니다.")
    prop = db.require("external_property", ref_no=ref_no)
    enforce(
        "CTL-052",
        bool(cause_analysis.strip()),
        f"소유물 {ref_no}: 분실·손상 시 원인분석을 수행해야 합니다(8.5.3.1).",
        db=db,
        context=f"external_property:{ref_no}",
    )
    db.update(
        "external_property",
        prop["id"],
        status=status,
        reported_on=today(),
        cause_analysis=cause_analysis,
    )
    return db.fetch("external_property", prop["id"])


def return_property(db: Database, ref_no: str) -> Row:
    """소유물을 반환한다 — 반환 시점까지 추적성을 유지한다 (8.5.3.1)."""
    prop = db.require("external_property", ref_no=ref_no)
    db.update("external_property", prop["id"], status="returned", returned_on=today())
    return db.fetch("external_property", prop["id"])


# ------------------------------------------------------------- 8.5.4 보존
def define_preservation(
    db: Database,
    *,
    scope: str,
    marking: str,
    special_handling: str,
    cleaning: str,
    shelf_life_control: str,
    environment: str,
    doc_id: int,
    config_part_no: str | None = None,
    project_code: str | None = None,
) -> int:
    """보존 규격을 문서화한다 (8.5.4.1 a~e)."""
    documents.assert_usable(db, doc_id, f"보존 규격 {scope}")
    missing = [
        name
        for name, value in (
            ("marking", marking),
            ("special_handling", special_handling),
            ("cleaning", cleaning),
            ("shelf_life_control", shelf_life_control),
            ("environment", environment),
        )
        if not value.strip()
    ]
    enforce(
        "CTL-052",
        not missing,
        f"보존 규격 {scope} 누락 항목(8.5.4.1): {', '.join(missing)}",
        db=db,
        context=f"preservation:{scope}",
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
        "preservation_spec",
        config_item_id=config_item_id,
        scope=scope,
        marking=marking,
        special_handling=special_handling,
        cleaning=cleaning,
        shelf_life_control=shelf_life_control,
        environment=environment,
        doc_id=doc_id,
    )


# ------------------------------------------------------- 8.5.1.4 생산설비
def register_equipment(
    db: Database,
    *,
    ident: str,
    name: str,
    acceptance_criteria: str,
    verification_interval_months: int = 12,
    preventive_plan: str = "",
    spare_parts_secured: bool = False,
) -> int:
    """생산설비를 개별 식별하여 등록한다 (8.5.1.4.1 b) 3))."""
    enforce(
        "CTL-051",
        bool(acceptance_criteria.strip()),
        f"설비 {ident}: 검증 방법과 합격기준을 정의해야 합니다(8.5.1.4.1 b) 1)).",
        db=db,
        context=f"equipment:{ident}",
    )
    return db.insert(
        "production_equipment",
        ident=ident,
        name=name,
        acceptance_criteria=acceptance_criteria,
        verification_interval_months=verification_interval_months,
        preventive_plan=preventive_plan,
        spare_parts_secured=int(spare_parts_secured),
        status="pending_validation",
    )


def validate_equipment_before_first_use(
    db: Database, ident: str, *, fai_id: int
) -> Row:
    """최초 사용 전 설비를 유효성확인한다 (8.5.1.4.1 b) 2), 8.9.3 a)."""
    equipment = db.require("production_equipment", ident=ident)
    fai.assert_approved(db, fai_id, f"설비 {ident} 최초 사용 전 유효성확인")
    db.update(
        "production_equipment",
        equipment["id"],
        validated_before_first_use_on=today(),
        last_verified_on=today(),
        next_verification_on=add_months(
            today(), int(equipment["verification_interval_months"])
        ),
        condition_checked_on=today(),
        status="ok",
    )
    return db.fetch("production_equipment", equipment["id"])


def record_maintenance(
    db: Database,
    *,
    ident: str,
    kind: str,
    result: str,
    downtime_hours: float = 0.0,
) -> int:
    """정비·검증 활동을 기록한다 (8.5.1.4.1 b), c), g))."""
    if kind not in ("preventive", "corrective", "predictive", "verification"):
        raise ValueError(f"알 수 없는 정비 유형: {kind}")
    equipment = db.require("production_equipment", ident=ident)
    record_id = db.insert(
        "equipment_maintenance",
        equipment_id=equipment["id"],
        performed_on=today(),
        kind=kind,
        result=result,
        downtime_hours=downtime_hours,
    )
    if kind in ("preventive", "verification"):
        db.update(
            "production_equipment",
            equipment["id"],
            last_verified_on=today(),
            next_verification_on=add_months(
                today(), int(equipment["verification_interval_months"])
            ),
            condition_checked_on=today(),
        )
    return record_id


def assert_equipment_usable(db: Database, ident: str, purpose: str) -> Row:
    """설비가 사용 가능한지 확인한다 (CTL-051)."""
    equipment = db.require("production_equipment", ident=ident)
    enforce(
        "CTL-051",
        bool(equipment["validated_before_first_use_on"]),
        f"{purpose}: 설비 {ident} 는 최초 사용 전 유효성확인이 필요합니다"
        " (8.5.1.4.1 b) 2)).",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-051",
        not is_past(equipment["next_verification_on"]),
        f"{purpose}: 설비 {ident} 의 재검증 기한({equipment['next_verification_on']})이"
        " 경과했습니다(8.5.1.4.1 b) 6)).",
        db=db,
        context=purpose,
    )
    return equipment


def equipment_due(db: Database, *, as_of: str | None = None) -> list[Row]:
    """검증·점검 기한이 경과한 설비 (8.5.1.4.1)."""
    return [
        r
        for r in db.query("SELECT * FROM production_equipment")
        if not r["validated_before_first_use_on"]
        or is_past(r["next_verification_on"], as_of=as_of)
    ]


def downtime_rate(db: Database, *, planned_hours: float) -> float | None:
    """설비 비가동률 (PI-EQDT)."""
    if planned_hours <= 0:
        return None
    total = db.scalar("SELECT COALESCE(SUM(downtime_hours), 0) FROM equipment_maintenance")
    return round(float(total) / planned_hours * 100, 2)
