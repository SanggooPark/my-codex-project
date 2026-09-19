"""성과지표 측정·분석 (9.1.1, 9.1.3).

강제 통제
    CTL-020  KPI 목표 미달 시 시정조치 등록 (9.1.3.1)
    CTL-041  최고경영자가 지정한 KPI 존재 (5.3.1 a)
    CTL-056  모든 PI 정의는 9.1.1.1.1 a)~g) 항목을 완비 (9.1.1.1.1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ..standard import Indicator, load_registry
from . import capa
from ._base import enforce


def definitions() -> tuple[Indicator, ...]:
    """PI/KPI 정의 목록 (Annex C Table C.1)."""
    return load_registry().indicators


def incomplete_definitions() -> list[dict[str, object]]:
    """9.1.1.1.1 a)~g) 항목이 누락된 PI 정의 (CTL-056)."""
    out = []
    for indicator in definitions():
        missing = indicator.missing_definition_fields()
        if missing:
            out.append({"code": indicator.code, "missing": missing})
    return out


def record_measurement(
    db: Database,
    *,
    indicator_code: str,
    period: str,
    value: float,
    analysis: str,
    trend: str,
    shared_with: str,
    capa_no: str | None = None,
) -> int:
    """PI 측정값을 기록한다 (9.1.1, 9.1.3.1).

    - 목표 미달이면 추세와 분석이 필요하고, KPI 인 경우 시정조치가 필수다(9.1.3.1).
    - 분석 결과는 관련 이해관계자와 공유되어야 한다(9.1.3.1 마지막 문단).
    """
    indicator = load_registry().indicator(indicator_code)
    met = indicator.is_met(value)

    enforce(
        "CTL-020",
        bool(shared_with.strip()),
        f"{indicator_code}/{period}: 분석 결과를 관련 이해관계자와 공유해야 합니다"
        " (9.1.3.1).",
        db=db,
        context=f"indicator:{indicator_code}",
    )
    if not met:
        enforce(
            "CTL-020",
            bool(analysis.strip()) and bool(trend.strip()),
            f"{indicator_code}/{period}: 목표 미달 시 분석과 추세를 제시해야 합니다"
            " (9.1.3.1).",
            db=db,
            context=f"indicator:{indicator_code}",
        )
        if indicator.is_kpi:
            enforce(
                "CTL-020",
                capa_no is not None,
                f"{indicator_code}/{period}: KPI 목표"
                f"({indicator.target}{indicator.unit}) 미달({value})이므로 시정조치가"
                " 필수입니다(9.1.3.1).",
                db=db,
                context=f"indicator:{indicator_code}",
            )

    capa_id = None
    if capa_no:
        capa_id = int(db.require("capa", capa_no=capa_no)["id"])

    existing = db.find(
        "indicator_measurement", indicator_code=indicator_code, period=period
    )
    values = {
        "value": value,
        "target": indicator.target,
        "met": int(met),
        "analysis": analysis,
        "trend": trend,
        "shared_with": shared_with,
        "capa_id": capa_id,
        "recorded_on": today(),
    }
    if existing:
        db.update("indicator_measurement", existing["id"], **values)
        return int(existing["id"])
    return db.insert(
        "indicator_measurement",
        indicator_code=indicator_code,
        period=period,
        **values,
    )


def assert_kpi_capa_coverage(db: Database) -> None:
    """목표 미달 KPI 전부에 시정조치가 연결되었는지 확인한다 (CTL-020)."""
    for row in unmet_kpi_measurements(db):
        if row["capa_id"] is None:
            capa.require_capa_for(
                db,
                source_type="kpi",
                source_ref=f"{row['indicator_code']}:{row['period']}",
                control_id="CTL-020",
                purpose=f"KPI {row['indicator_code']} {row['period']} 목표 미달",
            )


def unmet_kpi_measurements(db: Database) -> list[Row]:
    """목표를 달성하지 못한 KPI 측정값."""
    kpi_codes = [i.code for i in load_registry().kpis()]
    if not kpi_codes:
        return []
    marks = ",".join("?" for _ in kpi_codes)
    return db.query(
        f"SELECT * FROM indicator_measurement WHERE met = 0 AND indicator_code IN ({marks})",
        kpi_codes,
    )


def unmeasured_indicators(db: Database, *, period: str) -> list[str]:
    """해당 기간에 측정되지 않은 PI (9.1.1.1.1)."""
    measured = {
        r["indicator_code"]
        for r in db.query(
            "SELECT indicator_code FROM indicator_measurement WHERE period = ?", (period,)
        )
    }
    return [i.code for i in definitions() if i.code not in measured]


def scorecard(db: Database, *, period: str | None = None) -> list[dict[str, object]]:
    """PI 스코어카드 — 목표 대비 실적과 추세."""
    registry = load_registry()
    rows: list[dict[str, object]] = []
    for indicator in registry.indicators:
        if period:
            measurement = db.find(
                "indicator_measurement", indicator_code=indicator.code, period=period
            )
        else:
            measurement = db.one(
                "SELECT * FROM indicator_measurement WHERE indicator_code = ? "
                "ORDER BY period DESC LIMIT 1",
                (indicator.code,),
            )
        rows.append(
            {
                "code": indicator.code,
                "title": indicator.title_ko,
                "is_kpi": indicator.is_kpi,
                "mandate": indicator.mandate,
                "unit": indicator.unit,
                "target": indicator.target,
                "period": measurement["period"] if measurement else None,
                "value": measurement["value"] if measurement else None,
                "met": bool(measurement["met"]) if measurement else None,
                "capa_id": measurement["capa_id"] if measurement else None,
                "processes": list(indicator.processes),
            }
        )
    return rows


def process_coverage() -> dict[str, list[str]]:
    """프로세스별 PI 매핑 (4.4.1 c, Annex C.5)."""
    registry = load_registry()
    return {
        process.code: [i.code for i in registry.indicators_for_process(process.code)]
        for process in registry.processes
    }


def record_failure_data(
    db: Database, *, internal: int, external: int, period: str
) -> int:
    """내·외부 실패 보고 데이터를 기록한다 (9.1.1.1.1 두 번째 문단)."""
    return db.insert(
        "control_violation_log",
        control_id="CTL-056",
        clauses="9.1.1.1.1",
        context=f"failure_data:{period}",
        message=f"내부 실패 {internal}건, 외부 실패 {external}건",
        occurred_at=today(),
    )
