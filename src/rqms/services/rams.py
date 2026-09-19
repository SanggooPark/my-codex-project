"""RAM / SAF / LCC — 신뢰성·가용성·정비성, 안전, 수명주기비용 (8.8).

강제 통제
    CTL-029  RAM 목표 미달 시 현장데이터 분석 및 시정조치 등록 (8.8.2 g)
    CTL-057  안전관련 제품은 적용 안전표준 식별 및 안전 케이스 보유 (8.8.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import enforce

#: 8.8.2 RAM 지표
METRICS = ("MTBF", "MTTR", "availability", "SIL")

#: 8.8.2 a) RAM 산정 단계
STAGES = ("tender", "design", "production", "operation")

#: 8.8.3 적용 가능한 안전 표준
SAFETY_STANDARDS = ("IEC 62278", "IEC 62425", "IEC 62279", "EN 50126", "EN 50128", "EN 50129")

#: 8.8.2 d) / 8.8.4 d) 분석 기법
ANALYSIS_METHODS = ("8D", "FRACAS", "FMECA")


def set_objective(
    db: Database,
    *,
    product: str,
    metric: str,
    target: float,
    unit: str,
    period: str,
    applicable_standard: str,
    calculated: float | None = None,
    calculated_at_stage: str = "tender",
    direction: str = "higher_is_better",
) -> int:
    """RAM 목표를 설정하고 산정값을 기록한다 (8.8.2 a, b).

    적용 규정·표준(예: IEC 62278)을 식별해야 한다(8.8.2 첫 문단).
    """
    if metric not in METRICS:
        raise ValueError(f"알 수 없는 RAM 지표: {metric}")
    if calculated_at_stage not in STAGES:
        raise ValueError(f"알 수 없는 산정 단계: {calculated_at_stage}")
    enforce(
        "CTL-029",
        bool(applicable_standard.strip()),
        f"{product}/{metric}: RAM 프로세스에 적용되는 규정·표준을 식별해야 합니다(8.8.2).",
        db=db,
        context=f"rams:{product}",
    )
    return db.insert(
        "rams_objective",
        product=product,
        metric=metric,
        target=target,
        unit=unit,
        direction=direction,
        calculated=calculated,
        calculated_at_stage=calculated_at_stage,
        period=period,
        applicable_standard=applicable_standard,
    )


def collect_field_data(
    db: Database,
    *,
    product: str,
    occurred_on: str,
    failure_symptom: str,
    failure_category: str,
    component: str,
    severity: str,
    serial_no: str | None = None,
    mileage_km: float | None = None,
    operating_hours: float | None = None,
    repair_cost: float = 0.0,
    source: str = "maintenance_contract",
) -> int:
    """현장 데이터를 수집한다 (8.8.2 c).

    원인분석은 고장분류·부품할당·영향(조치·심각도)에 근거해야 하므로(8.8.2 마지막 문단),
    해당 항목을 필수로 기록한다.
    """
    enforce(
        "CTL-029",
        bool(failure_category.strip()) and bool(component.strip()) and bool(severity.strip()),
        f"{product}: 현장 데이터는 고장분류·부품·심각도를 포함해야 합니다(8.8.2).",
        db=db,
        context=f"field_data:{product}",
    )
    return db.insert(
        "field_data",
        product=product,
        serial_no=serial_no,
        occurred_on=occurred_on,
        failure_symptom=failure_symptom,
        failure_category=failure_category,
        component=component,
        severity=severity,
        mileage_km=mileage_km,
        operating_hours=operating_hours,
        repair_cost=repair_cost,
        source=source,
    )


def evaluate_objective(
    db: Database,
    objective_id: int,
    *,
    field_value: float,
    analysis: str,
    capa_id: int | None = None,
    feedback_to_design: str = "",
    feedback_to_provider: str = "",
) -> Row:
    """현장 데이터로 RAM 목표 달성을 평가한다 (8.8.2 d~g).

    목표 미달 시 현장 데이터 분석과 시정조치가 필수이며(8.8.2 g),
    설계·외부공급자로의 환류가 기록되어야 한다(e, f).
    """
    objective = db.fetch("rams_objective", objective_id)
    met = (
        field_value >= float(objective["target"])
        if objective["direction"] == "higher_is_better"
        else field_value <= float(objective["target"])
    )
    if not met:
        enforce(
            "CTL-029",
            bool(analysis.strip()),
            f"{objective['product']}/{objective['metric']}: 목표 미달 시 현장 데이터"
            " 분석이 필요합니다(8.8.2 g).",
            db=db,
            context=f"rams:{objective['product']}",
        )
        enforce(
            "CTL-029",
            capa_id is not None,
            f"{objective['product']}/{objective['metric']}: 목표"
            f" {objective['target']}{objective['unit']} 미달({field_value})이므로"
            " 시정조치가 필요합니다(8.8.2 g, 10.2).",
            db=db,
            context=f"rams:{objective['product']}",
        )
        enforce(
            "CTL-029",
            bool(feedback_to_design.strip()),
            f"{objective['product']}/{objective['metric']}: RAM 데이터를 설계 개선으로"
            " 환류해야 합니다(8.8.2 e).",
            db=db,
            context=f"rams:{objective['product']}",
        )
    db.update(
        "rams_objective",
        objective_id,
        field_value=field_value,
        analysis=analysis,
        capa_id=capa_id,
        feedback_to_design=feedback_to_design,
        feedback_to_provider=feedback_to_provider,
    )
    return db.fetch("rams_objective", objective_id)


def unmet_objectives(db: Database) -> list[Row]:
    """목표 미달 RAM 항목 (8.8.2 g)."""
    rows = db.query("SELECT * FROM rams_objective WHERE field_value IS NOT NULL")
    out = []
    for row in rows:
        met = (
            float(row["field_value"]) >= float(row["target"])
            if row["direction"] == "higher_is_better"
            else float(row["field_value"]) <= float(row["target"])
        )
        if not met:
            out.append(row)
    return out


def achievement_rate(db: Database) -> float | None:
    """RAM 목표 달성률 (PI-RAM)."""
    total = db.count("SELECT COUNT(*) FROM rams_objective WHERE field_value IS NOT NULL")
    if total == 0:
        return None
    return round((total - len(unmet_objectives(db))) / total * 100, 2)


# ----------------------------------------------------------------- 8.8.3 안전
def record_safety_case(
    db: Database,
    *,
    product: str,
    applicable_standards: str,
    safety_case_doc_id: int,
    sil_level: str = "",
    hazard_log: str = "",
) -> int:
    """안전관련 제품의 안전 케이스를 등록한다 (8.8.3).

    IEC 62278 / 62425 / 62279 또는 동등 표준을 식별해야 한다.
    """
    enforce(
        "CTL-057",
        any(std in applicable_standards for std in SAFETY_STANDARDS),
        f"{product}: 적용 안전표준(IEC 62278, 62425, 62279 또는 동등)을 식별해야 합니다"
        " (8.8.3).",
        db=db,
        context=f"safety:{product}",
    )
    documents.assert_usable(db, safety_case_doc_id, f"안전 케이스 {product}")
    enforce(
        "CTL-057",
        bool(hazard_log.strip()),
        f"{product}: 위험원 기록(hazard log)이 필요합니다(8.8.3).",
        db=db,
        context=f"safety:{product}",
    )
    existing = db.find("safety_record", product=product)
    if existing:
        db.update(
            "safety_record",
            existing["id"],
            sil_level=sil_level,
            applicable_standards=applicable_standards,
            safety_case_doc_id=safety_case_doc_id,
            hazard_log=hazard_log,
            assessed_on=today(),
        )
        return int(existing["id"])
    return db.insert(
        "safety_record",
        product=product,
        sil_level=sil_level,
        applicable_standards=applicable_standards,
        safety_case_doc_id=safety_case_doc_id,
        hazard_log=hazard_log,
        assessed_on=today(),
    )


def assert_safety_case(db: Database, product: str, purpose: str) -> Row:
    """안전관련 제품의 안전 케이스 보유를 확인한다 (CTL-057)."""
    record = db.find("safety_record", product=product)
    enforce(
        "CTL-057",
        record is not None,
        f"{purpose}: 안전관련 제품 {product} 의 안전 케이스가 없습니다(8.8.3).",
        db=db,
        context=purpose,
    )
    assert record is not None
    return record


# ------------------------------------------------------------------ 8.8.4 LCC
def record_lcc(
    db: Database,
    *,
    product: str,
    period: str,
    calculated: float,
    perspective: str = "manufacturer",
    actual: float | None = None,
    analysis: str = "",
) -> int:
    """수명주기비용을 산정·기록한다 (8.8.4 a~e, 권고)."""
    return db.insert(
        "lcc_record",
        product=product,
        period=period,
        perspective=perspective,
        calculated=calculated,
        actual=actual,
        analysis=analysis,
    )
