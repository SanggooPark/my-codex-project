"""IAU — 내부심사 관리 프로세스 (9.2).

강제 통제
    CTL-021  심사 프로그램은 모든 필수 프로세스를 3년 내 최소 1회 포함 (9.2.3.2 c)
    CTL-022  심사원은 자신의 업무(소속 프로세스)를 심사할 수 없음 (9.2.3.2 d)
    CTL-055  심사팀은 심사범위·해당 조항 지식과 심사 경험 요건 충족 (9.2.3.3.1)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from ..standard import load_registry
from . import documents
from ._base import enforce, parse_date

#: 9.2.3.2 c) 최소 심사 주기(년)
MAX_AUDIT_INTERVAL_YEARS = 3

#: 9.2.3.3.1 b) 심사 경험 최소 요건(수행 심사 건수)
MIN_AUDITS_PERFORMED = 2

#: 심사 발견사항 등급
GRADES = ("major", "minor", "observation", "opportunity")


def create_programme(db: Database, *, year: int) -> int:
    """연간 심사 프로그램을 생성한다 (9.2.2 a, 9.2.3.2)."""
    existing = db.find("audit_programme", year=year)
    if existing:
        return int(existing["id"])
    return db.insert("audit_programme", year=year)


def approve_programme(db: Database, *, year: int, multidisciplinary: bool = False) -> Row:
    """심사 프로그램을 승인한다.

    3년 프로그램은 매년 검토되어야 한다(9.2.3.2 마지막 문단).
    """
    programme = db.require("audit_programme", year=year)
    db.update(
        "audit_programme",
        programme["id"],
        approved_on=today(),
        reviewed_on=today(),
        multidisciplinary=int(multidisciplinary),
    )
    return db.fetch("audit_programme", programme["id"])


def register_auditor(
    db: Database,
    *,
    person_id: int,
    knows_audit_principles: bool,
    scope_knowledge: str,
    clause_knowledge: str,
    criteria_knowledge: str,
    audits_performed: int,
    home_processes: str,
    refresh_training_on: str | None = None,
) -> int:
    """심사원을 등록한다 (9.2.3.3.1 a, b / 9.2.3.3.2 c).

    소속 프로세스(home_processes)는 자기업무 심사 금지 판정에 사용된다.
    """
    enforce(
        "CTL-055",
        knows_audit_principles
        and bool(scope_knowledge.strip())
        and bool(clause_knowledge.strip())
        and bool(criteria_knowledge.strip()),
        "심사원 등록: 심사원칙·심사범위·해당 조항·심사기준 지식이 모두 필요합니다"
        " (9.2.3.3.1 a).",
        db=db,
        context=f"auditor:{person_id}",
    )
    existing = db.find("auditor", person_id=person_id)
    values = {
        "knows_audit_principles": int(knows_audit_principles),
        "scope_knowledge": scope_knowledge,
        "clause_knowledge": clause_knowledge,
        "criteria_knowledge": criteria_knowledge,
        "audits_performed": audits_performed,
        "home_processes": home_processes,
        "refresh_training_on": refresh_training_on,
    }
    if existing:
        db.update("auditor", existing["id"], **values)
        return int(existing["id"])
    return db.insert("auditor", person_id=person_id, **values)


def plan_audit(
    db: Database,
    *,
    audit_no: str,
    year: int,
    scope: str,
    criteria: str,
    planned_on: str,
    lead_auditor_id: int,
    team: str = "",
    process_code: str | None = None,
    project_code: str | None = None,
    shifts_covered: str = "",
) -> int:
    """심사를 계획한다 (9.2.2 a, b / 9.2.3.2 a, b, d, e).

    - 심사기준과 범위가 정의되어야 한다(9.2.2 b).
    - 심사원은 자신의 업무를 심사할 수 없다(9.2.3.2 d, CTL-022).
    - 심사팀은 역량 요건을 충족해야 한다(9.2.3.3.1, CTL-055).
    """
    programme = db.require("audit_programme", year=year)
    enforce(
        "CTL-021",
        bool(criteria.strip()) and bool(scope.strip()),
        f"심사 {audit_no}: 심사기준과 범위를 정의해야 합니다(9.2.2 b).",
        db=db,
        context=f"audit:{audit_no}",
    )
    if process_code:
        load_registry().process(process_code)  # 미정의 코드면 KeyError

    lead = db.require("auditor", person_id=lead_auditor_id)
    person = db.fetch("person", lead_auditor_id)
    enforce(
        "CTL-055",
        int(lead["audits_performed"]) >= MIN_AUDITS_PERFORMED,
        f"심사 {audit_no}: 선임심사원 {person['name']} 의 심사 경험이 부족합니다"
        f" (수행 {lead['audits_performed']}건 < {MIN_AUDITS_PERFORMED}건) — 9.2.3.3.1 b).",
        db=db,
        context=f"audit:{audit_no}",
    )
    if process_code:
        home = {p.strip() for p in (lead["home_processes"] or "").split(",") if p.strip()}
        enforce(
            "CTL-022",
            process_code not in home,
            f"심사 {audit_no}: {person['name']} 은 소속 프로세스 {process_code} 를"
            " 심사할 수 없습니다(9.2.3.2 d).",
            db=db,
            context=f"audit:{audit_no}",
        )
        for member_id in _team_ids(team):
            member = db.find("auditor", person_id=member_id)
            if member is None:
                continue
            member_home = {
                p.strip() for p in (member["home_processes"] or "").split(",") if p.strip()
            }
            member_person = db.fetch("person", member_id)
            enforce(
                "CTL-022",
                process_code not in member_home,
                f"심사 {audit_no}: {member_person['name']} 은 소속 프로세스"
                f" {process_code} 를 심사할 수 없습니다(9.2.3.2 d).",
                db=db,
                context=f"audit:{audit_no}",
            )

    project_id_code = None
    if project_code:
        db.require("project", code=project_code)
        project_id_code = project_code

    return db.insert(
        "internal_audit",
        audit_no=audit_no,
        programme_id=programme["id"],
        process_code=process_code,
        project_code=project_id_code,
        scope=scope,
        criteria=criteria,
        planned_on=planned_on,
        lead_auditor_id=lead_auditor_id,
        team=team,
        shifts_covered=shifts_covered,
    )


def perform_audit(
    db: Database, audit_no: str, *, report_doc_id: int, reported_to: str
) -> Row:
    """심사를 실시하고 결과를 관련 경영진에게 보고한다 (9.2.2 d, f)."""
    audit = db.require("internal_audit", audit_no=audit_no)
    documents.assert_usable(db, report_doc_id, f"심사보고서 {audit_no}")
    enforce(
        "CTL-021",
        bool(reported_to.strip()),
        f"심사 {audit_no}: 결과를 관련 경영진에게 보고해야 합니다(9.2.2 d).",
        db=db,
        context=f"audit:{audit_no}",
    )
    db.update(
        "internal_audit",
        audit["id"],
        performed_on=today(),
        report_doc_id=report_doc_id,
        reported_to=reported_to,
        status="performed",
    )
    lead = db.find("auditor", person_id=audit["lead_auditor_id"])
    if lead:
        db.update(
            "auditor", lead["id"], audits_performed=int(lead["audits_performed"]) + 1
        )
    return db.fetch("internal_audit", audit["id"])


def record_finding(
    db: Database,
    *,
    audit_no: str,
    clause_id: str,
    grade: str,
    description: str,
    capa_id: int | None = None,
) -> int:
    """심사 발견사항을 기록한다 (9.2.2 e, f).

    중부적합·경부적합은 시정조치가 지체 없이 연결되어야 한다(9.2.2 e).
    """
    if grade not in GRADES:
        raise ValueError(f"알 수 없는 발견사항 등급: {grade}")
    load_registry().clause(clause_id)  # 미정의 조항이면 KeyError
    audit = db.require("internal_audit", audit_no=audit_no)
    if grade in ("major", "minor"):
        enforce(
            "CTL-021",
            capa_id is not None,
            f"심사 {audit_no}: {grade} 발견사항은 지체 없이 시정조치를 취해야 합니다"
            " (9.2.2 e).",
            db=db,
            context=f"audit:{audit_no}",
        )
    return db.insert(
        "audit_finding",
        audit_id=audit["id"],
        clause_id=clause_id,
        grade=grade,
        description=description,
        capa_id=capa_id,
    )


def coverage_gaps(db: Database, *, as_of: str | None = None) -> list[dict[str, object]]:
    """3년 내 심사되지 않은 필수 프로세스 (9.2.3.2 c, CTL-021)."""
    reference = parse_date(as_of or today())
    gaps: list[dict[str, object]] = []
    for process in load_registry().mandatory_processes():
        last = db.scalar(
            "SELECT MAX(performed_on) FROM internal_audit "
            "WHERE process_code = ? AND performed_on IS NOT NULL",
            (process.code,),
        )
        if last is None:
            gaps.append({"process": process.code, "last_audit": None, "years": None})
            continue
        years = (reference - parse_date(last)).days / 365.25
        if years > MAX_AUDIT_INTERVAL_YEARS:
            gaps.append(
                {"process": process.code, "last_audit": last, "years": round(years, 1)}
            )
    return gaps


def assert_three_year_coverage(db: Database, *, as_of: str | None = None) -> None:
    """3년 커버리지 요건 충족을 강제한다 (CTL-021)."""
    gaps = coverage_gaps(db, as_of=as_of)
    enforce(
        "CTL-021",
        not gaps,
        "3년 내 심사되지 않은 필수 프로세스가 있습니다: "
        + ", ".join(str(g["process"]) for g in gaps),
        db=db,
        context="audit_programme",
    )


def execution_rate(db: Database, *, year: int) -> float | None:
    """심사 프로그램 이행률 (PI-AUD)."""
    programme = db.find("audit_programme", year=year)
    if programme is None:
        return None
    planned = db.count(
        "SELECT COUNT(*) FROM internal_audit WHERE programme_id = ?", (programme["id"],)
    )
    if planned == 0:
        return None
    performed = db.count(
        "SELECT COUNT(*) FROM internal_audit "
        "WHERE programme_id = ? AND performed_on IS NOT NULL",
        (programme["id"],),
    )
    return round(performed / planned * 100, 2)


def findings_without_capa(db: Database) -> list[Row]:
    """시정조치가 연결되지 않은 부적합 발견사항 (9.2.2 e)."""
    return db.query(
        "SELECT * FROM audit_finding WHERE grade IN ('major','minor') AND capa_id IS NULL"
    )


def _team_ids(team: str) -> list[int]:
    out = []
    for token in team.split(","):
        token = token.strip()
        if token.isdigit():
            out.append(int(token))
    return out
