"""SPP — 특수공정 관리 프로세스 (8.5.1.3).

강제 통제
    CTL-014  특수공정은 공정자격·작업자 자격이 모두 유효한 경우에만 실행 (8.5.1.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents
from ._base import enforce, is_past

#: 8.5.1.3 b) 4) 작업지침이 다루어야 하는 6M
SIX_M = ("management", "manpower", "machine", "methods", "material", "mother_nature")

#: 8.5.1.3 NOTE — 대표적인 특수공정
TYPICAL = (
    "bonding_sealing",
    "casting",
    "crimping",
    "heat_treatment",
    "riveting",
    "surface_treatment",
    "torque_tightening",
    "welding",
)


def register(
    db: Database,
    *,
    code: str,
    name: str,
    applicable_standard: str,
    risk_assessment: str,
    owner_id: int,
    work_instruction_doc_id: int | None = None,
    six_m_covered: dict[str, str] | None = None,
) -> int:
    """특수공정을 식별·등록한다 (8.5.1.3 a, b) 1)~4)).

    적용 표준이 없으면 6M 을 다루는 작업지침이 반드시 있어야 한다(8.5.1.3 b) 4)).
    """
    enforce(
        "CTL-014",
        bool(risk_assessment.strip()),
        f"특수공정 {code}: 리스크 평가(예: 공정 FMEA)가 필요합니다(8.5.1.3 b) 3)).",
        db=db,
        context=f"special_process:{code}",
    )
    if not applicable_standard.strip():
        six_m_covered = six_m_covered or {}
        missing = [m for m in SIX_M if not six_m_covered.get(m)]
        enforce(
            "CTL-014",
            work_instruction_doc_id is not None and not missing,
            f"특수공정 {code}: 적용 표준이 없으므로 6M 을 다루는 작업지침이 필요합니다"
            f" (누락: {', '.join(missing) or '작업지침'}) — 8.5.1.3 b) 4).",
            db=db,
            context=f"special_process:{code}",
        )
    if work_instruction_doc_id is not None:
        documents.assert_usable(db, work_instruction_doc_id, f"특수공정 작업지침 {code}")
    return db.insert(
        "special_process",
        code=code,
        name=name,
        applicable_standard=applicable_standard,
        risk_assessment=risk_assessment,
        work_instruction_doc_id=work_instruction_doc_id,
        owner_id=owner_id,
    )


def qualify_process(db: Database, code: str, *, valid_until: str, evidence: str) -> Row:
    """특수공정을 자격부여한다 (8.5.1.3 b) 7), 8))."""
    process = db.require("special_process", code=code)
    enforce(
        "CTL-014",
        bool(evidence.strip()) and bool(valid_until),
        f"특수공정 {code}: 자격부여 증거와 유효기간이 필요합니다(8.5.1.3 b) 7)).",
        db=db,
        context=f"special_process:{code}",
    )
    db.update(
        "special_process",
        process["id"],
        qualified_on=today(),
        qualification_valid_until=valid_until,
    )
    return db.fetch("special_process", process["id"])


def qualify_operator(
    db: Database, *, code: str, person_id: int, qualified_until: str
) -> int:
    """작업자를 자격부여한다 (8.5.1.3 b) 5))."""
    db.require("special_process", code=code)
    existing = db.find("special_process_operator", special_process_code=code, person_id=person_id)
    if existing:
        db.update("special_process_operator", existing["id"], qualified_until=qualified_until)
        return int(existing["id"])
    return db.insert(
        "special_process_operator",
        special_process_code=code,
        person_id=person_id,
        qualified_until=qualified_until,
    )


def revalidate(db: Database, code: str, *, reason: str, valid_until: str) -> Row:
    """변경 후 특수공정을 재유효성확인한다 (8.5.1.3 b) 9))."""
    process = db.require("special_process", code=code)
    enforce(
        "CTL-014",
        bool(reason.strip()),
        f"특수공정 {code}: 재유효성확인 사유를 기록해야 합니다(8.5.1.3 b) 9)).",
        db=db,
        context=f"special_process:{code}",
    )
    db.update(
        "special_process",
        process["id"],
        qualified_on=today(),
        qualification_valid_until=valid_until,
        revalidation_note=reason,
    )
    return db.fetch("special_process", process["id"])


def assert_executable(
    db: Database, code: str, *, operator_id: int, purpose: str, as_of: str | None = None
) -> Row:
    """특수공정 실행 가능 여부를 확인한다 (CTL-014).

    공정 자격과 작업자 자격이 모두 유효해야 한다.
    """
    process = db.require("special_process", code=code)
    enforce(
        "CTL-014",
        bool(process["qualified_on"])
        and not is_past(process["qualification_valid_until"], as_of=as_of),
        f"{purpose}: 특수공정 {code} 의 공정 자격이 유효하지 않습니다"
        f" (유효기한 {process['qualification_valid_until']}) — 8.5.1.3 b) 7).",
        db=db,
        context=purpose,
    )
    operator = db.find(
        "special_process_operator", special_process_code=code, person_id=operator_id
    )
    person = db.fetch("person", operator_id)
    enforce(
        "CTL-014",
        operator is not None and not is_past(operator["qualified_until"], as_of=as_of),
        f"{purpose}: {person['name']} 은 특수공정 {code} 의 유효한 자격이 없습니다"
        " (8.5.1.3 b) 5)).",
        db=db,
        context=purpose,
    )
    return process


def expired_qualifications(db: Database, *, as_of: str | None = None) -> dict[str, list[Row]]:
    """자격 만료 목록 (공정/작업자)."""
    processes = [
        p
        for p in db.query("SELECT * FROM special_process")
        if not p["qualified_on"] or is_past(p["qualification_valid_until"], as_of=as_of)
    ]
    operators = [
        o
        for o in db.query("SELECT * FROM special_process_operator")
        if is_past(o["qualified_until"], as_of=as_of)
    ]
    return {"processes": processes, "operators": operators}
