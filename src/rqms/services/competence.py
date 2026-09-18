"""CMP — 역량 관리 프로세스 (7.2).

강제 통제
    CTL-026  필요역량을 충족하지 않은 인원의 해당 업무 배정 금지 (7.2, 7.2.1.1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ._base import enforce, is_past

#: 7.2.1.2 NOTE 1 — 역량 매트릭스 단계
LEVELS = {1: "learner", 2: "basic", 3: "advanced", 4: "coach"}


def add_person(
    db: Database, *, emp_no: str, name: str, role: str, department: str
) -> int:
    """인원을 등록한다 (7.1.2)."""
    return db.insert(
        "person", emp_no=emp_no, name=name, role=role, department=department
    )


def define_requirement(
    db: Database,
    *,
    task_code: str,
    competence_code: str,
    min_level: int,
    quality_or_safety_relevant: bool = False,
) -> int:
    """업무에 필요한 역량을 정의한다 (7.2 a)."""
    if min_level not in LEVELS:
        raise ValueError(f"역량 단계는 {sorted(LEVELS)} 중 하나여야 합니다.")
    return db.insert(
        "competence_requirement",
        task_code=task_code,
        competence_code=competence_code,
        min_level=min_level,
        quality_or_safety_relevant=int(quality_or_safety_relevant),
    )


def record_competence(
    db: Database,
    *,
    person_id: int,
    competence_code: str,
    level: int,
    evidence: str,
    valid_until: str | None = None,
) -> int:
    """역량 보유 증거를 기록한다 (7.2 b, d)."""
    enforce(
        "CTL-026",
        bool(evidence.strip()),
        "역량 기록에는 교육·훈련·경험 증거가 필요합니다(7.2 d).",
        db=db,
        context=f"competence:{person_id}:{competence_code}",
    )
    existing = db.find(
        "competence", person_id=person_id, competence_code=competence_code
    )
    if existing:
        db.update(
            "competence",
            existing["id"],
            level=level,
            evidence=evidence,
            valid_until=valid_until,
        )
        return int(existing["id"])
    return db.insert(
        "competence",
        person_id=person_id,
        competence_code=competence_code,
        level=level,
        evidence=evidence,
        valid_until=valid_until,
    )


def gaps_for(db: Database, person_id: int, task_code: str) -> list[dict[str, object]]:
    """인원이 해당 업무에 대해 가진 역량 갭을 계산한다 (7.2.1.1 b)."""
    required = db.query(
        "SELECT * FROM competence_requirement WHERE task_code = ?", (task_code,)
    )
    held = {
        r["competence_code"]: r
        for r in db.query("SELECT * FROM competence WHERE person_id = ?", (person_id,))
    }
    gaps: list[dict[str, object]] = []
    for req in required:
        actual = held.get(req["competence_code"])
        level = int(actual["level"]) if actual else 0
        expired = bool(actual and actual["valid_until"] and is_past(actual["valid_until"]))
        if level < int(req["min_level"]) or expired:
            gaps.append(
                {
                    "competence_code": req["competence_code"],
                    "required_level": int(req["min_level"]),
                    "actual_level": 0 if expired else level,
                    "expired": expired,
                }
            )
    return gaps


def assign_task(db: Database, *, person_id: int, task_code: str) -> int:
    """업무를 배정한다. 역량 갭이 있으면 배정을 거부한다 (CTL-026).

    갭은 competence_gap 등록부에 기록되어 교육 계획의 입력이 된다(7.2.1.1 b, c).
    """
    person = db.fetch("person", person_id)
    gaps = gaps_for(db, person_id, task_code)
    if gaps:
        for gap in gaps:
            _record_gap(db, person_id, gap)
        detail = ", ".join(
            f"{g['competence_code']}({g['actual_level']}<{g['required_level']})" for g in gaps
        )
        enforce(
            "CTL-026",
            False,
            f"{person['name']} 은 업무 {task_code} 의 필요역량을 충족하지 않습니다: {detail}",
            db=db,
            context=f"assignment:{task_code}",
        )
    existing = db.find("task_assignment", person_id=person_id, task_code=task_code)
    if existing:
        return int(existing["id"])
    return db.insert(
        "task_assignment", person_id=person_id, task_code=task_code, assigned_on=today()
    )


def assert_competent(db: Database, person_id: int, task_code: str, purpose: str) -> None:
    """업무 수행 시점에 역량 충족을 재확인한다 (7.2 b)."""
    gaps = gaps_for(db, person_id, task_code)
    if not gaps:
        return
    person = db.fetch("person", person_id)
    detail = ", ".join(str(g["competence_code"]) for g in gaps)
    enforce(
        "CTL-026",
        False,
        f"{purpose}: {person['name']} 의 역량 부족({detail})으로 {task_code} 를 수행할 수 없습니다.",
        db=db,
        context=purpose,
    )


def plan_gap_action(
    db: Database, gap_id: int, *, action: str, due_on: str
) -> None:
    """역량 갭 해소 조치를 계획한다 (7.2.1.1 c)."""
    enforce(
        "CTL-026",
        bool(action.strip()) and bool(due_on),
        "역량 갭 조치는 내용과 기한을 정의해야 합니다(7.2.1.1 c).",
        db=db,
        context=f"competence_gap:{gap_id}",
    )
    db.update("competence_gap", gap_id, action=action, due_on=due_on)


def close_gap(db: Database, gap_id: int) -> None:
    """역량 갭을 해소 처리한다."""
    db.update("competence_gap", gap_id, closed_on=today())


def open_gaps(db: Database) -> list[Row]:
    return db.query("SELECT * FROM competence_gap WHERE closed_on IS NULL")


def matrix(db: Database) -> list[dict[str, object]]:
    """역량 매트릭스 — 필요역량 대비 실제 상태 (7.2.1.2 a)."""
    rows = db.query(
        "SELECT p.id AS person_id, p.name, p.department, cr.task_code, "
        "       cr.competence_code, cr.min_level, c.level AS actual_level, c.valid_until "
        "FROM person p "
        "JOIN task_assignment ta ON ta.person_id = p.id "
        "JOIN competence_requirement cr ON cr.task_code = ta.task_code "
        "LEFT JOIN competence c ON c.person_id = p.id "
        "                      AND c.competence_code = cr.competence_code "
        "ORDER BY p.name, cr.task_code, cr.competence_code"
    )
    return [
        {
            "person": r["name"],
            "department": r["department"],
            "task_code": r["task_code"],
            "competence_code": r["competence_code"],
            "required_level": int(r["min_level"]),
            "actual_level": int(r["actual_level"] or 0),
            "label": LEVELS.get(int(r["actual_level"] or 0), "none"),
            "valid_until": r["valid_until"],
        }
        for r in rows
    ]


def _record_gap(db: Database, person_id: int, gap: dict[str, object]) -> None:
    existing = db.one(
        "SELECT * FROM competence_gap "
        "WHERE person_id = ? AND competence_code = ? AND closed_on IS NULL",
        (person_id, gap["competence_code"]),
    )
    if existing:
        return
    db.insert(
        "competence_gap",
        person_id=person_id,
        competence_code=gap["competence_code"],
        required_level=gap["required_level"],
        actual_level=gap["actual_level"],
    )
