"""PRJ — 프로젝트 관리 프로세스 (8.1.3).

강제 통제
    CTL-004  이전 단계검토의 미결사항 미종결 시 단계검토 통과 금지
             (최고경영자 승인 시 예외) — 8.1.3.1.3 d)
    CTL-005  프로젝트 범위·일정·예산 변경은 승인된 변경요청에 의해서만
             (8.1.3.3, 8.1.3.4, 8.1.3.5)
    CTL-044  프로젝트 필수 계획서 보유 (8.1.3.2, .6, .7, .8)
    CTL-045  진행 중 프로젝트의 정기 프로젝트 검토 (8.1.3.11)
"""

from __future__ import annotations

import json
from sqlite3 import Row

from ..db import Database, today
from . import change, documents
from ._base import add_months, enforce, is_past

#: 8.1.3 게이트 방식 프로젝트 단계
PHASES = (
    "tender",
    "planning",
    "design",
    "industrialization",
    "production",
    "delivery",
    "warranty",
    "closure",
)

#: 8.1.3.1.1 e) 게이트 결정
DECISIONS = ("accepted", "conditional", "rejected")

#: 8.1.3 필수 계획서 (8.1.3.2 / .6 / .7 / .8)
REQUIRED_PLANS = ("management", "quality", "hr", "communication")

#: 8.1.3.2 프로젝트 관리계획서가 포함해야 하는 항목 a)~g)
PMP_TOPICS = (
    "organization_chart",
    "targets_and_frame_conditions",
    "responsibilities_and_authorities",
    "execution_rules",
    "aligned_function_plans",
    "deliverables_per_phase",
    "change_control",
)

#: 8.1.3.2 h)~k) 다중 사이트·컨소시엄 추가 항목
MULTI_SITE_TOPICS = (
    "work_split_and_interfaces",
    "specific_responsibilities",
    "communication_channels",
    "applicable_processes",
)

#: 8.1.3.11 프로젝트 검토 주기(개월)
REVIEW_CYCLE_MONTHS = 3


def create(
    db: Database,
    *,
    code: str,
    name: str,
    customer: str,
    tender_no: str | None = None,
    budget: float = 0.0,
    planned_margin_pct: float = 0.0,
    multi_site: bool = False,
    safety_related: bool = False,
) -> int:
    """프로젝트를 개설한다 (8.1.3.1.1)."""
    return db.insert(
        "project",
        code=code,
        name=name,
        customer=customer,
        tender_no=tender_no,
        budget=budget,
        planned_margin_pct=planned_margin_pct,
        multi_site=int(multi_site),
        safety_related=int(safety_related),
        phase="tender",
        status="active",
    )


def attach_plan(
    db: Database,
    *,
    project_code: str,
    plan_kind: str,
    doc_id: int,
    covers: dict[str, str] | None = None,
) -> int:
    """프로젝트 계획서를 등록한다 (8.1.3.2, .6, .7, .8).

    관리계획서는 8.1.3.2 a)~g) 를 담아야 하며, 다중사이트·컨소시엄 프로젝트는
    h)~k) 도 필요하다.
    """
    project = db.require("project", code=project_code)
    documents.assert_usable(db, doc_id, f"{project_code} {plan_kind} 계획서")
    covers = covers or {}
    if plan_kind == "management":
        required = list(PMP_TOPICS)
        if project["multi_site"]:
            required += list(MULTI_SITE_TOPICS)
        missing = [t for t in required if not covers.get(t)]
        enforce(
            "CTL-044",
            not missing,
            f"{project_code} 프로젝트 관리계획서 누락 항목(8.1.3.2): {', '.join(missing)}",
            db=db,
            context=f"project:{project_code}",
        )
    if plan_kind == "quality":
        enforce(
            "CTL-044",
            bool(covers.get("quality_assurance")) and bool(covers.get("quality_control")),
            f"{project_code} 프로젝트 품질계획서는 품질보증·품질관리 활동을 포함해야 합니다"
            " (8.1.3.6).",
            db=db,
            context=f"project:{project_code}",
        )
    existing = db.find("project_plan", project_id=project["id"], plan_kind=plan_kind)
    if existing:
        db.update(
            "project_plan",
            existing["id"],
            doc_id=doc_id,
            covers=json.dumps(covers, ensure_ascii=False),
        )
        return int(existing["id"])
    return db.insert(
        "project_plan",
        project_id=project["id"],
        plan_kind=plan_kind,
        doc_id=doc_id,
        covers=json.dumps(covers, ensure_ascii=False),
    )


def missing_plans(db: Database, project_code: str) -> list[str]:
    """누락된 필수 계획서 목록 (CTL-044)."""
    project = db.require("project", code=project_code)
    present = {
        r["plan_kind"]
        for r in db.query(
            "SELECT plan_kind FROM project_plan WHERE project_id = ?", (project["id"],)
        )
    }
    return [k for k in REQUIRED_PLANS if k not in present]


def add_work_package(
    db: Database,
    *,
    project_code: str,
    wbs_code: str,
    name: str,
    owner_id: int,
    duration_days: int,
    start_on: str,
    finish_on: str,
    predecessors: str = "",
    on_critical_path: bool = False,
    external_provider: str | None = None,
) -> int:
    """작업패키지를 등록하고 담당자를 지정한다 (8.1.3.3 c, d)."""
    project = db.require("project", code=project_code)
    enforce(
        "CTL-005",
        owner_id is not None,
        f"{project_code}/{wbs_code}: 작업패키지 담당자를 지정해야 합니다(8.1.3.3 d).",
        db=db,
        context=f"project:{project_code}",
    )
    return db.insert(
        "work_package",
        project_id=project["id"],
        wbs_code=wbs_code,
        name=name,
        owner_id=owner_id,
        duration_days=duration_days,
        start_on=start_on,
        finish_on=finish_on,
        predecessors=predecessors,
        on_critical_path=int(on_critical_path),
        external_provider=external_provider,
    )


def verify_work_package(db: Database, work_package_id: int) -> None:
    """작업패키지 검증을 기록한다 (8.1.3.3 e)."""
    db.update("work_package", work_package_id, verified_on=today())


def set_schedule(
    db: Database,
    *,
    project_code: str,
    start_on: str,
    finish_on: str,
    customer_delivery_on: str,
    critical_path: str,
) -> Row:
    """프로젝트 일정을 확정한다 (8.1.3.4 d, e). 주공정이 정의되어야 한다."""
    project = db.require("project", code=project_code)
    enforce(
        "CTL-005",
        bool(critical_path.strip()),
        f"{project_code}: 프로젝트 일정은 주공정(critical path)을 포함해야 합니다(8.1.3.4 e).",
        db=db,
        context=f"project:{project_code}",
    )
    db.update(
        "project",
        project["id"],
        start_on=start_on,
        finish_on=finish_on,
        customer_delivery_on=customer_delivery_on,
        critical_path=critical_path,
    )
    return db.fetch("project", project["id"])


def change_scope(db: Database, *, project_code: str, note: str) -> Row:
    """프로젝트 범위를 변경한다. 승인된 변경요청이 필요하다 (8.1.3.3, CTL-005)."""
    project = db.require("project", code=project_code)
    change.assert_approved_change(
        db,
        scope="project_scope",
        target_ref=project_code,
        control_id="CTL-005",
        purpose=f"{project_code} 범위 변경",
    )
    db.insert(
        "communication_entry",
        kind="record",
        topic=f"프로젝트 범위 변경: {note}",
        timing="as_occurred",
        audience="project_team",
        method="project_review",
        communicator="project_manager",
        project_code=project_code,
        occurred_on=today(),
    )
    return db.fetch("project", project["id"])


def change_customer_delivery(db: Database, *, project_code: str, new_date: str) -> Row:
    """고객 인도일을 변경한다. 승인된 변경요청 + 고객 통보가 필요하다 (8.1.3.4)."""
    project = db.require("project", code=project_code)
    request = change.assert_approved_change(
        db,
        scope="project_schedule",
        target_ref=project_code,
        control_id="CTL-005",
        purpose=f"{project_code} 고객 인도일 변경",
    )
    enforce(
        "CTL-028",
        bool(request["customer_notified_on"]),
        f"{project_code}: 고객 인도일 변경은 적시에 고객에게 요청·통보되어야 합니다"
        " (8.1.3.4).",
        db=db,
        context=f"project:{project_code}",
    )
    db.update("project", project["id"], customer_delivery_on=new_date)
    return db.fetch("project", project["id"])


def increase_budget(db: Database, *, project_code: str, new_budget: float) -> Row:
    """프로젝트 예산을 증액한다. 승인된 변경요청이 필요하다 (8.1.3.5, CTL-005)."""
    project = db.require("project", code=project_code)
    if new_budget > float(project["budget"]):
        change.assert_approved_change(
            db,
            scope="project_budget",
            target_ref=project_code,
            control_id="CTL-005",
            purpose=f"{project_code} 예산 증액",
        )
    db.update("project", project["id"], budget=new_budget)
    return db.fetch("project", project["id"])


def record_cost(
    db: Database,
    *,
    project_code: str,
    cost_account: str,
    period: str,
    budget: float,
    actual: float,
    estimate_at_completion: float,
) -> int:
    """원가계정 구조에 따라 원가를 기록한다 (8.1.3.5 b, c)."""
    project = db.require("project", code=project_code)
    return db.insert(
        "project_cost",
        project_id=project["id"],
        cost_account=cost_account,
        period=period,
        budget=budget,
        actual=actual,
        estimate_at_completion=estimate_at_completion,
    )


# ------------------------------------------------------------ 단계검토 / 미결사항
def plan_phase_review(
    db: Database,
    *,
    project_code: str,
    phase: str,
    planned_on: str,
    mandatory_participants: str,
    gate_checklist_doc: int | None = None,
    wbs_level: int = 1,
) -> int:
    """단계검토를 계획한다 (8.1.3.1.1 d, e / 8.1.3.1.3 c)."""
    if phase not in PHASES:
        raise ValueError(f"알 수 없는 프로젝트 단계: {phase}")
    project = db.require("project", code=project_code)
    enforce(
        "CTL-004",
        bool(mandatory_participants.strip()),
        f"{project_code}/{phase}: 단계검토의 필수 참석자를 정의해야 합니다(8.1.3.1.3).",
        db=db,
        context=f"project:{project_code}",
    )
    return db.insert(
        "phase_review",
        project_id=project["id"],
        phase=phase,
        wbs_level=wbs_level,
        planned_on=planned_on,
        mandatory_participants=mandatory_participants,
        gate_checklist_doc=gate_checklist_doc,
    )


def raise_open_issue(
    db: Database,
    *,
    project_code: str,
    description: str,
    owner_id: int,
    due_on: str,
    phase: str | None = None,
    resource_note: str = "",
) -> int:
    """미결사항을 등록한다 (8.1.3.1.1 g) — 종결 자원을 함께 기록한다."""
    project = db.require("project", code=project_code)
    review_id = None
    if phase:
        review = db.find("phase_review", project_id=project["id"], phase=phase)
        review_id = review["id"] if review else None
    return db.insert(
        "open_issue",
        project_id=project["id"],
        phase_review_id=review_id,
        description=description,
        owner_id=owner_id,
        resource_note=resource_note,
        raised_on=today(),
        due_on=due_on,
    )


def close_open_issue(db: Database, issue_id: int) -> None:
    db.update("open_issue", issue_id, closed_on=today())


def open_issues(db: Database, project_code: str, *, before_phase: str | None = None) -> list[Row]:
    """미종결 미결사항 목록. before_phase 지정 시 그 이전 단계의 것만 반환한다."""
    project = db.require("project", code=project_code)
    rows = db.query(
        "SELECT oi.*, pr.phase AS review_phase FROM open_issue oi "
        "LEFT JOIN phase_review pr ON pr.id = oi.phase_review_id "
        "WHERE oi.project_id = ? AND oi.closed_on IS NULL",
        (project["id"],),
    )
    if before_phase is None:
        return rows
    limit = PHASES.index(before_phase)
    out = []
    for row in rows:
        phase = row["review_phase"]
        # 단계 귀속이 없는 미결사항은 현재 단계 이전으로 간주한다(보수적 판단).
        if phase is None or PHASES.index(phase) < limit:
            out.append(row)
    return out


def hold_phase_review(
    db: Database,
    *,
    project_code: str,
    phase: str,
    decision: str,
    actual_participants: str,
    top_management_override_by: int | None = None,
) -> Row:
    """단계검토를 실시하고 게이트 결정을 기록한다 (8.1.3.1.1 e, 8.1.3.1.3 d).

    이전 단계의 미결사항이 종결되지 않았으면 통과(accepted/conditional)할 수 없다.
    다만 최고경영자 또는 권한을 위임받은 고위 대표자의 승인이 있으면 예외로 통과한다.
    """
    if decision not in DECISIONS:
        raise ValueError(f"알 수 없는 게이트 결정: {decision}")
    project = db.require("project", code=project_code)
    review = db.find("phase_review", project_id=project["id"], phase=phase)
    enforce(
        "CTL-004",
        review is not None,
        f"{project_code}/{phase}: 계획되지 않은 단계검토는 실시할 수 없습니다.",
        db=db,
        context=f"project:{project_code}",
    )
    assert review is not None

    # 8.1.3.1.3 — 필수 참석자가 실제로 참석해야 한다.
    required = {p.strip() for p in review["mandatory_participants"].split(",") if p.strip()}
    actual = {p.strip() for p in actual_participants.split(",") if p.strip()}
    absent = sorted(required - actual)
    enforce(
        "CTL-004",
        not absent,
        f"{project_code}/{phase}: 단계검토 필수 참석자 불참 — {', '.join(absent)}",
        db=db,
        context=f"project:{project_code}",
    )

    if decision in ("accepted", "conditional"):
        prior = open_issues(db, project_code, before_phase=phase)
        if prior and top_management_override_by is None:
            detail = "; ".join(str(i["description"]) for i in prior)
            enforce(
                "CTL-004",
                False,
                f"{project_code}/{phase}: 이전 단계 미결사항이 종결되지 않았습니다"
                f" — {detail}. 통과하려면 최고경영자 승인이 필요합니다(8.1.3.1.3 d).",
                db=db,
                context=f"project:{project_code}",
            )

    db.update(
        "phase_review",
        review["id"],
        held_on=today(),
        decision=decision,
        actual_participants=actual_participants,
        top_management_override_by=top_management_override_by,
        escalated=int(decision == "rejected"),
    )
    if decision in ("accepted", "conditional"):
        db.update("project", project["id"], phase=phase)
    return db.fetch("phase_review", review["id"])


# ------------------------------------------------------- 8.1.3.11 프로젝트 검토
def hold_project_review(
    db: Database,
    *,
    project_code: str,
    performance: str,
    forecast: str,
    risk_status: str,
    open_issue_followup: str,
    reported_to: str,
    core_team_present: bool = True,
    countermeasures: str = "",
) -> int:
    """정기 프로젝트 검토를 실시한다 (8.1.3.11 a~d).

    핵심팀(또는 권한 있는 대리인) 참석이 필요하며, 네 가지 검토항목이 모두 있어야 한다.
    """
    project = db.require("project", code=project_code)
    enforce(
        "CTL-045",
        core_team_present,
        f"{project_code}: 프로젝트 검토는 핵심팀(또는 권한 있는 대리인) 참석이 필요합니다"
        " (8.1.3.11).",
        db=db,
        context=f"project:{project_code}",
    )
    missing = [
        name
        for name, value in (
            ("performance", performance),
            ("forecast", forecast),
            ("risk_status", risk_status),
            ("open_issue_followup", open_issue_followup),
        )
        if not value.strip()
    ]
    enforce(
        "CTL-045",
        not missing,
        f"{project_code} 프로젝트 검토 누락 항목(8.1.3.11): {', '.join(missing)}",
        db=db,
        context=f"project:{project_code}",
    )
    return db.insert(
        "project_review",
        project_id=project["id"],
        held_on=today(),
        performance=performance,
        forecast=forecast,
        risk_status=risk_status,
        open_issue_followup=open_issue_followup,
        core_team_present=int(core_team_present),
        countermeasures=countermeasures,
        reported_to=reported_to,
    )


def overdue_project_reviews(db: Database, *, as_of: str | None = None) -> list[Row]:
    """정기 검토 주기를 초과한 진행 중 프로젝트 (8.1.3.11, CTL-045)."""
    out = []
    for project in db.query("SELECT * FROM project WHERE status = 'active'"):
        last = db.scalar(
            "SELECT MAX(held_on) FROM project_review WHERE project_id = ?",
            (project["id"],),
        )
        if last is None or is_past(add_months(last, REVIEW_CYCLE_MONTHS), as_of=as_of):
            out.append(project)
    return out


def close(db: Database, project_code: str, *, actual_margin_pct: float) -> Row:
    """프로젝트를 종료한다. 미결사항이 남아 있으면 종료할 수 없다."""
    project = db.require("project", code=project_code)
    remaining = open_issues(db, project_code)
    enforce(
        "CTL-004",
        not remaining,
        f"{project_code}: 미종결 미결사항 {len(remaining)}건이 남아 프로젝트를 종료할 수"
        " 없습니다(8.1.3.1.1 g).",
        db=db,
        context=f"project:{project_code}",
    )
    db.update(
        "project",
        project["id"],
        status="closed",
        phase="closure",
        actual_margin_pct=actual_margin_pct,
    )
    return db.fetch("project", project["id"])
