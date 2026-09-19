"""조직 상황·리더십·프로세스 거버넌스 (4장, 5장, 6.2).

강제 통제
    CTL-031  공정·생산 정지 권한을 가진 독립 대표자 지정 (5.3.1 d)
    CTL-036  요약 사업계획 문서화 및 연간 검토 (4.1.1.1)
    CTL-037  RQMS 적용범위 문서화 및 비적용 조항 정당화 (4.3, 4.3.1)
    CTL-038  프로세스 기술서 최소항목·계층구조 (4.4.1, 4.4.3)
    CTL-039  프로세스 오너 임명 및 프로세스 교육 (4.4.3, 5.3.2)
    CTL-040  품질방침 필수 주제 (5.2.3)
    CTL-041  KPI 지정 (5.3.1 a)
    CTL-043  품질목표 달성 기획 (6.2)
"""

from __future__ import annotations

import json
from sqlite3 import Row

from ..db import Database, today
from ..standard import load_registry
from . import documents
from ._base import enforce

#: 4.1.1.1 사업계획이 고려해야 하는 항목 a)~l)
BUSINESS_PLAN_TOPICS = (
    "business_objectives",
    "market_strategy",
    "product_service_strategy",
    "management_review_outputs",
    "resource_planning",
    "risks_opportunities",
    "business_continuity",
    "customer_needs",
    "interested_party_inputs",
    "technology_and_regulatory_changes",
    "capacity_vs_forecast",
    "merger_outsourcing_transfer",
)

#: 5.2.3 품질방침이 다루어야 하는 주제
POLICY_TOPICS = ("failure_prevention", "customer_expectations", "safety")

#: 4.4.1 a)~e) 프로세스 기술서 최소 항목
PROCESS_DESCRIPTION_FIELDS = (
    "inputs",
    "outputs",
    "sequence_note",
    "criteria",
    "resources",
)


# --------------------------------------------------------------- 4.1 / 4.2 상황
def record_context_issue(
    db: Database, *, origin: str, name: str, requirement: str = ""
) -> int:
    """외부·내부 이슈를 등록한다 (4.1)."""
    return db.insert(
        "context_entry",
        kind="issue",
        origin=origin,
        name=name,
        requirement=requirement,
        reviewed_on=today(),
    )


def record_interested_party(
    db: Database, *, origin: str, name: str, requirement: str
) -> int:
    """이해관계자와 그 요구사항을 등록한다 (4.2)."""
    return db.insert(
        "context_entry",
        kind="interested_party",
        origin=origin,
        name=name,
        requirement=requirement,
        reviewed_on=today(),
    )


# ------------------------------------------------------------- 4.1.1.1 사업계획
def record_business_plan(
    db: Database, *, year: int, doc_id: int, topics: dict[str, str]
) -> int:
    """요약 사업계획을 등록한다 (4.1.1.1).

    a)~l) 항목을 모두 다루어야 하며, 문서는 승인된 상태여야 한다.
    """
    documents.assert_usable(db, doc_id, f"사업계획 {year}")
    missing = [t for t in BUSINESS_PLAN_TOPICS if not topics.get(t)]
    enforce(
        "CTL-036",
        not missing,
        f"{year}년 사업계획에 누락된 고려사항: {', '.join(missing)}",
        db=db,
        context=f"business_plan:{year}",
    )
    return db.insert(
        "governance_record",
        kind="business_plan",
        ref_year=year,
        doc_id=doc_id,
        payload=json.dumps(topics, ensure_ascii=False),
        reviewed_on=today(),
    )


# ------------------------------------------------------------ 4.3 적용범위
def record_scope(
    db: Database,
    *,
    year: int,
    doc_id: int,
    products_services: str,
    exclusions: dict[str, str] | None = None,
) -> int:
    """RQMS 적용범위를 등록한다 (4.3, 4.3.1).

    비적용 조항은 정당화 사유가 반드시 있어야 하며, 정당화 없는 비적용은 거부된다.
    """
    documents.assert_usable(db, doc_id, f"RQMS 적용범위 {year}")
    exclusions = exclusions or {}
    registry = load_registry()
    unjustified = [cid for cid, reason in exclusions.items() if not reason]
    enforce(
        "CTL-037",
        not unjustified,
        f"정당화 사유가 없는 비적용 조항: {', '.join(unjustified)}",
        db=db,
        context=f"rqms_scope:{year}",
    )
    unknown = [cid for cid in exclusions if cid not in {c.id for c in registry.clauses}]
    enforce(
        "CTL-037",
        not unknown,
        f"표준에 존재하지 않는 조항을 비적용으로 선언했습니다: {', '.join(unknown)}",
        db=db,
        context=f"rqms_scope:{year}",
    )
    return db.insert(
        "governance_record",
        kind="rqms_scope",
        ref_year=year,
        doc_id=doc_id,
        payload=json.dumps(
            {"products_services": products_services, "exclusions": exclusions},
            ensure_ascii=False,
        ),
        reviewed_on=today(),
    )


def excluded_clauses(db: Database) -> dict[str, str]:
    """최신 적용범위 선언의 비적용 조항과 정당화 사유."""
    row = db.one(
        "SELECT payload FROM governance_record WHERE kind = 'rqms_scope' "
        "ORDER BY ref_year DESC LIMIT 1"
    )
    if row is None:
        return {}
    return dict(json.loads(row["payload"]).get("exclusions", {}))


# ------------------------------------------------------------- 5.2 품질방침
def record_quality_policy(
    db: Database, *, year: int, doc_id: int, topics: dict[str, str]
) -> int:
    """품질방침을 등록한다 (5.2.1, 5.2.3)."""
    documents.assert_usable(db, doc_id, f"품질방침 {year}")
    missing = [t for t in POLICY_TOPICS if not topics.get(t)]
    enforce(
        "CTL-040",
        not missing,
        f"품질방침이 다루지 않은 필수 주제: {', '.join(missing)} (5.2.3)",
        db=db,
        context=f"quality_policy:{year}",
    )
    return db.insert(
        "governance_record",
        kind="quality_policy",
        ref_year=year,
        doc_id=doc_id,
        payload=json.dumps(topics, ensure_ascii=False),
        reviewed_on=today(),
    )


def record_social_responsibility(db: Database, *, year: int, statement: str) -> int:
    """사회적 책임 고려사항을 등록한다 (4.1.2, 권고)."""
    return db.insert(
        "governance_record",
        kind="social_responsibility",
        ref_year=year,
        payload=json.dumps({"statement": statement}, ensure_ascii=False),
        reviewed_on=today(),
    )


# ------------------------------------------------- 5.3 역할·책임·권한 / 정지권한
def appoint_stop_authority(
    db: Database, *, person_id: int, scope: str, independent_of: str
) -> int:
    """공정·생산 정지 권한자를 임명한다 (5.3.1 d).

    프로세스 실행으로부터 독립적이어야 하므로, 정지 대상 조직과 동일한 소속은 거부한다.
    """
    person = db.fetch("person", person_id)
    enforce(
        "CTL-031",
        person["department"] != independent_of,
        f"{person['name']} 은 {independent_of} 소속이므로 해당 범위의 독립 대표자가 될 수 없습니다.",
        db=db,
        context=f"stop_authority:{scope}",
    )
    return db.insert(
        "stop_authority",
        person_id=person_id,
        scope=scope,
        independent_of=independent_of,
        appointed_on=today(),
    )


# --------------------------------------------- 4.4 프로세스 등록 / 오너 임명
def register_process(
    db: Database,
    *,
    code: str,
    owner_id: int,
    description_doc: int,
    inputs: str,
    outputs: str,
    sequence_note: str,
    criteria: str,
    resources: str,
    risk_criteria: str,
) -> str:
    """Annex A 프로세스를 조직 프로세스로 등록한다 (4.4.1, 4.4.3, 5.3.1 b).

    기술서는 4.4.1 a)~e) 를 모두 담아야 하며(4.4.3), 프로세스 오너가 임명되어야 한다.
    """
    registry = load_registry()
    process = registry.process(code)  # 미정의 코드면 KeyError
    documents.assert_usable(db, description_doc, f"프로세스 기술서 {code}")

    values = {
        "inputs": inputs,
        "outputs": outputs,
        "sequence_note": sequence_note,
        "criteria": criteria,
        "resources": resources,
    }
    missing = [f for f in PROCESS_DESCRIPTION_FIELDS if not values[f].strip()]
    enforce(
        "CTL-038",
        not missing,
        f"프로세스 {code} 기술서 누락 항목(4.4.1 a~e): {', '.join(missing)}",
        db=db,
        context=f"process:{code}",
    )
    enforce(
        "CTL-038",
        bool(risk_criteria.strip()),
        f"프로세스 {code} 는 리스크기반 통제 기준(4.4.3 f)을 정의해야 합니다.",
        db=db,
        context=f"process:{code}",
    )
    enforce(
        "CTL-039",
        bool(owner_id),
        f"프로세스 {code} 의 오너가 임명되지 않았습니다(5.3.1 b).",
        db=db,
        context=f"process:{code}",
    )

    db.execute(
        "INSERT OR REPLACE INTO process_instance "
        "(code, owner_id, description_doc, inputs, outputs, sequence_note, criteria, "
        " resources, risk_criteria, applicable, exclusion_reason) "
        "VALUES (?,?,?,?,?,?,?,?,?,1,NULL)",
        (
            code,
            owner_id,
            description_doc,
            inputs,
            outputs,
            sequence_note,
            criteria,
            resources,
            risk_criteria,
        ),
    )
    return process.code


def exclude_process(db: Database, *, code: str, reason: str) -> None:
    """프로세스를 비적용으로 선언한다 (4.3.1). 조건부 필수 프로세스에만 허용."""
    process = load_registry().process(code)
    enforce(
        "CTL-037",
        process.obligation != "mandatory",
        f"필수 프로세스 {code} 는 비적용으로 선언할 수 없습니다(Annex A.1).",
        db=db,
        context=f"process:{code}",
    )
    enforce(
        "CTL-037",
        bool(reason.strip()),
        f"프로세스 {code} 비적용에는 정당화 사유가 필요합니다.",
        db=db,
        context=f"process:{code}",
    )
    db.execute(
        "INSERT OR REPLACE INTO process_instance (code, applicable, exclusion_reason) "
        "VALUES (?, 0, ?)",
        (code, reason),
    )


def record_process_training(
    db: Database, *, process_code: str, person_id: int, understanding_evidence: str
) -> int:
    """프로세스 교육 및 이해 증거를 기록한다 (4.4.3 c, 7.2.1.1 d) 2)."""
    enforce(
        "CTL-039",
        bool(understanding_evidence.strip()),
        "프로세스 교육은 교육내용 이해 증거를 기록해야 합니다(7.2.1.1 d) 2).",
        db=db,
        context=f"process_training:{process_code}",
    )
    return db.insert(
        "process_training",
        process_code=process_code,
        person_id=person_id,
        trained_on=today(),
        understanding_evidence=understanding_evidence,
    )


def process_hierarchy(db: Database) -> list[dict[str, object]]:
    """프로세스 계층구조를 반환한다 (4.4.3 a)."""
    registry = load_registry()
    rows = {r["code"]: r for r in db.query("SELECT * FROM process_instance")}
    out: list[dict[str, object]] = []
    for process in registry.processes:
        row = rows.get(process.code)
        out.append(
            {
                "code": process.code,
                "name": process.name_ko,
                "clause": process.clause,
                "obligation": process.obligation,
                "level": process.level,
                "parent": process.parent,
                "registered": row is not None,
                "applicable": bool(row["applicable"]) if row else True,
                "owner_id": row["owner_id"] if row else None,
            }
        )
    return out


# --------------------------------------------------------------- 6.2 품질목표
def set_quality_objective(
    db: Database,
    *,
    code: str,
    description: str,
    level: str,
    target_value: float,
    unit: str,
    responsible_id: int,
    due_on: str,
    resources: str,
    evaluation_method: str,
    indicator_code: str | None = None,
    safety_related: bool = False,
) -> int:
    """품질목표를 수립한다 (6.2.1, 6.2.2).

    측정 가능해야 하며(6.2.1 b), 자원·책임·기한·평가방법이 정의되어야 한다(6.2.2 b~e).
    """
    missing = [
        name
        for name, value in (
            ("resources", resources),
            ("responsible", responsible_id),
            ("due_on", due_on),
            ("evaluation_method", evaluation_method),
        )
        if not value
    ]
    enforce(
        "CTL-043",
        not missing,
        f"품질목표 {code} 의 달성 기획 누락 항목(6.2.2): {', '.join(missing)}",
        db=db,
        context=f"quality_objective:{code}",
    )
    if indicator_code:
        load_registry().indicator(indicator_code)  # 미정의 지표면 KeyError
    return db.insert(
        "quality_objective",
        code=code,
        description=description,
        level=level,
        target_value=target_value,
        unit=unit,
        indicator_code=indicator_code,
        resources=resources,
        responsible_id=responsible_id,
        due_on=due_on,
        evaluation_method=evaluation_method,
        safety_related=int(safety_related),
    )


def evaluate_objective(db: Database, objective_id: int, *, achieved: bool) -> Row:
    """품질목표 달성 여부를 기록한다. 미달 시 시정조치가 필요하다 (9.3.3.1)."""
    db.update("quality_objective", objective_id, achieved=int(achieved))
    return db.fetch("quality_objective", objective_id)
