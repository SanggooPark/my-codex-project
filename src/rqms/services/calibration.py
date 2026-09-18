"""CAL — 모니터링·측정 자원 교정/검증 프로세스 (7.1.5).

강제 통제
    CTL-025  교정·검증 주기가 경과한 측정자원 사용 금지, 부적합 판정 시 소급 영향평가
             (7.1.5.2, 7.1.5.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import add_months, enforce, is_past


def register_resource(
    db: Database,
    *,
    ident: str,
    resource_type: str,
    location: str,
    interval_months: int,
    custodian_id: int | None = None,
    used_in_special_process: bool = False,
) -> int:
    """측정자원을 등록부에 등록한다 (7.1.5.3 — 유형·고유식별·위치·주기)."""
    enforce(
        "CTL-025",
        interval_months > 0,
        f"측정자원 {ident}: 교정·검증 주기가 정의되지 않았습니다(7.1.5.3).",
        db=db,
        context=f"measuring_resource:{ident}",
    )
    return db.insert(
        "measuring_resource",
        ident=ident,
        resource_type=resource_type,
        location=location,
        custodian_id=custodian_id,
        interval_months=interval_months,
        status="overdue",  # 최초 교정 전에는 사용할 수 없다.
        used_in_special_process=int(used_in_special_process),
    )


def record_calibration(
    db: Database,
    *,
    resource_id: int,
    result: str,
    reference_standard: str,
    procedure_ref: str,
    performed_by_id: int | None = None,
    internal: bool = False,
    acceptance_criteria: str = "",
    ambient_suitable: bool = True,
    performed_on: str | None = None,
) -> int:
    """교정·검증 결과를 기록한다 (7.1.5.3 e~h).

    내부 교정인 경우 방법·합격기준과 주위 조건 적합성이 필요하다(7.1.5.3 c, d).
    부적합(fail) 판정 시 자원은 사용 불가 상태가 되며, 소급 영향평가가 요구된다(7.1.5.2).
    """
    resource = db.fetch("measuring_resource", resource_id)
    if result not in ("pass", "fail"):
        raise ValueError("result 는 pass 또는 fail 여야 합니다.")
    enforce(
        "CTL-025",
        bool(reference_standard.strip()) and bool(procedure_ref.strip()),
        f"측정자원 {resource['ident']}: 교정 기준기와 절차를 기록해야 합니다(7.1.5.3 g, h).",
        db=db,
        context=f"measuring_resource:{resource['ident']}",
    )
    if internal:
        enforce(
            "CTL-025",
            bool(acceptance_criteria.strip()) and ambient_suitable,
            f"측정자원 {resource['ident']}: 내부 교정은 합격기준과 적합한 주위조건이 필요합니다"
            " (7.1.5.3 c, d).",
            db=db,
            context=f"measuring_resource:{resource['ident']}",
        )

    on = performed_on or today()
    record_id = db.insert(
        "calibration_record",
        resource_id=resource_id,
        performed_on=on,
        result=result,
        reference_standard=reference_standard,
        procedure_ref=procedure_ref,
        internal=int(internal),
        acceptance_criteria=acceptance_criteria,
        ambient_suitable=int(ambient_suitable),
        performed_by_id=performed_by_id,
    )
    if result == "pass":
        db.update(
            "measuring_resource",
            resource_id,
            last_calibrated_on=on,
            next_due_on=add_months(on, int(resource["interval_months"])),
            status="ok",
        )
    else:
        db.update("measuring_resource", resource_id, status="unfit")
    return record_id


def assess_retrospective_impact(
    db: Database, calibration_record_id: int, *, finding: str
) -> None:
    """부적합 측정자원으로 수행한 이전 측정결과의 영향을 평가한다 (7.1.5.2)."""
    enforce(
        "CTL-025",
        bool(finding.strip()),
        "소급 영향평가 결과를 기록해야 합니다(7.1.5.2).",
        db=db,
        context=f"calibration_record:{calibration_record_id}",
    )
    db.update(
        "calibration_record", calibration_record_id, retrospective_impact_assessed=1
    )


def assert_usable(db: Database, resource_id: int | None, purpose: str) -> Row | None:
    """측정자원이 검사·시험에 사용 가능한지 확인한다 (CTL-025).

    resource_id 가 없으면(측정자원을 쓰지 않는 검사) 통과시킨다.
    """
    if resource_id is None:
        return None
    resource = db.fetch("measuring_resource", resource_id)
    enforce(
        "CTL-025",
        resource["status"] == "ok",
        f"{purpose}: 측정자원 {resource['ident']} 의 상태가 {resource['status']} 이므로"
        " 사용할 수 없습니다.",
        db=db,
        context=purpose,
    )
    enforce(
        "CTL-025",
        not is_past(resource["next_due_on"]),
        f"{purpose}: 측정자원 {resource['ident']} 의 교정 주기가"
        f" {resource['next_due_on']} 에 경과했습니다.",
        db=db,
        context=purpose,
    )
    return resource


def refresh_due_status(db: Database, *, as_of: str | None = None) -> list[Row]:
    """주기 경과 자원을 overdue 로 표시하고 목록을 돌려준다."""
    overdue = []
    for row in db.query("SELECT * FROM measuring_resource WHERE status = 'ok'"):
        if is_past(row["next_due_on"], as_of=as_of):
            db.update("measuring_resource", row["id"], status="overdue")
            overdue.append(row)
    return overdue


def unfit_without_impact_assessment(db: Database) -> list[Row]:
    """부적합 판정 후 소급 영향평가가 누락된 기록 (7.1.5.2)."""
    return db.query(
        "SELECT * FROM calibration_record "
        "WHERE result = 'fail' AND retrospective_impact_assessed = 0"
    )
