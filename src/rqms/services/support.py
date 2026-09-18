"""지원 프로세스 — 자원(7.1.1, RES), 조직 지식(7.1.6, KNW), 의사소통(7.4, COM),
혁신(8.1.1.1, INN).

강제 통제
    CTL-038  자원 계획은 프로세스 실행 자원·수주잔고·리스크 충당을 포함 (7.1.1.1)
"""

from __future__ import annotations

import json
from sqlite3 import Row

from ..db import Database, today
from ._base import enforce

#: 7.1.1.1 자원 계획이 포함해야 하는 항목 a)~c)
RESOURCE_PLAN_TOPICS = ("people_and_infrastructure", "order_book_and_forecast", "risk_provision")

#: 7.1.6.1.1 a) 경험 환류의 출처 (NOTE)
EXPERIENCE_SOURCES = (
    "nonconformity",
    "audit",
    "project",
    "rams",
    "complaint",
    "benchmark",
)


# ------------------------------------------------------------- 7.1.1 자원 계획
def record_resource_plan(
    db: Database, *, year: int, doc_id: int, topics: dict[str, str]
) -> int:
    """자원 계획을 등록한다 (7.1.1.1 a~c)."""
    from . import documents

    documents.assert_usable(db, doc_id, f"자원 계획 {year}")
    missing = [t for t in RESOURCE_PLAN_TOPICS if not topics.get(t)]
    enforce(
        "CTL-038",
        not missing,
        f"{year}년 자원 계획 누락 항목(7.1.1.1): {', '.join(missing)}",
        db=db,
        context=f"resource_plan:{year}",
    )
    return db.insert(
        "governance_record",
        kind="resource_plan",
        ref_year=year,
        doc_id=doc_id,
        payload=json.dumps(topics, ensure_ascii=False),
        reviewed_on=today(),
    )


def record_work_environment(db: Database, *, year: int, description: str) -> int:
    """프로세스 운영 환경을 기록한다 (7.1.4)."""
    return db.insert(
        "governance_record",
        kind="work_environment",
        ref_year=year,
        payload=json.dumps({"description": description}, ensure_ascii=False),
        reviewed_on=today(),
    )


# ------------------------------------------------------------ 7.1.6 조직 지식
def capture_lesson(
    db: Database,
    *,
    source_type: str,
    source_ref: str,
    description: str,
    is_good_practice: bool = False,
    communicated_to: str = "",
) -> int:
    """교훈 또는 good practice 를 등록하고 관련 조직에 전달한다 (7.1.6.1.1 a)."""
    if source_type not in EXPERIENCE_SOURCES:
        raise ValueError(f"알 수 없는 경험 출처: {source_type}")
    return db.insert(
        "lesson_learned",
        source_type=source_type,
        source_ref=source_ref,
        description=description,
        is_good_practice=int(is_good_practice),
        communicated_to=communicated_to,
        created_on=today(),
    )


def uncommunicated_lessons(db: Database) -> list[Row]:
    """관련 프로세스·진행 프로젝트로 전달되지 않은 교훈 (7.1.6.1.1 a) 2)."""
    return db.query("SELECT * FROM lesson_learned WHERE TRIM(communicated_to) = ''")


# ---------------------------------------------------------------- 7.4 의사소통
def plan_communication(
    db: Database,
    *,
    topic: str,
    timing: str,
    audience: str,
    method: str,
    communicator: str,
    project_code: str | None = None,
) -> int:
    """의사소통 계획 항목을 등록한다 (7.4 a~e)."""
    return db.insert(
        "communication_entry",
        kind="plan",
        topic=topic,
        timing=timing,
        audience=audience,
        method=method,
        communicator=communicator,
        project_code=project_code,
    )


def record_communication(
    db: Database,
    *,
    topic: str,
    audience: str,
    method: str,
    communicator: str,
    project_code: str | None = None,
    occurred_on: str | None = None,
) -> int:
    """실제 의사소통 실시 기록 (7.4)."""
    return db.insert(
        "communication_entry",
        kind="record",
        topic=topic,
        timing="as_occurred",
        audience=audience,
        method=method,
        communicator=communicator,
        project_code=project_code,
        occurred_on=occurred_on or today(),
    )


# ------------------------------------------------------------- 8.1.1.1 혁신
def propose_innovation(
    db: Database,
    *,
    ref_no: str,
    title: str,
    business_env_change: str,
    priority: int,
    resources: str,
    stakeholders: str,
) -> int:
    """혁신 항목을 등록한다 (8.1.1.1 a~d, 권고)."""
    return db.insert(
        "innovation",
        ref_no=ref_no,
        title=title,
        business_env_change=business_env_change,
        priority=priority,
        resources=resources,
        stakeholders=stakeholders,
        status="proposed",
    )
