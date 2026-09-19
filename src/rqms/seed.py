"""시연·검증용 조직 데이터 구축.

가상의 철도차량 부품 제조사 "한빛레일"의 RQMS 를 ISO 22163:2023 요구사항에 맞게
처음부터 구축한다. 입찰 → 프로젝트 → 설계 → 조달 → 생산 → 출하 → 인도 후 활동 →
성과평가 → 심사 → 경영검토까지 전체 수명주기를 실제 서비스 API 로 실행하므로,
모든 통제가 실제로 통과된 상태의 데이터가 만들어진다.

`rqms init --seed` 로 실행되며, 구축 후 `rqms conformity` 는 갭 0 을 보고해야 한다.
"""

from __future__ import annotations

from .db import Database, today
from .services import (
    audit,
    calibration,
    capa,
    change,
    competence,
    configuration,
    customer,
    design,
    documents,
    fai,
    governance,
    indicators,
    nonconformity,
    obsolescence,
    post_delivery,
    production,
    projects,
    rams,
    release,
    requirements,
    review,
    risk,
    special_processes,
    suppliers,
    support,
    tender,
    transfer,
)
from .services._base import add_months
from .standard import load_registry

ORG = "한빛레일"
YEAR = int(today()[:4])
PERIOD = today()[:7]
PRODUCT = "HR-DOOR-2000 전동차 출입문 시스템"


def build(db: Database) -> dict[str, object]:
    """전체 RQMS 를 구축하고 요약 정보를 반환한다."""
    people = _people(db)
    _governance(db, people)
    _support(db, people)
    _risk(db, people)
    tender_no = _tender(db, people)
    project_code = _project(db, people, tender_no)
    _configuration(db, project_code)
    _design(db, people, project_code)
    _suppliers(db, people, project_code)
    _special_processes(db, people)
    _production(db, people, project_code)
    _delivery_and_nonconformity(db, people, project_code)
    _rams_and_obsolescence(db, people)
    _transfer(db, people)
    _customer(db, people)
    _indicators(db, people)
    _audits(db, people)
    _reviews(db, people, project_code)
    return {
        "organization": ORG,
        "project": project_code,
        "tender": tender_no,
        "people": len(people),
        "documents": db.count("SELECT COUNT(*) FROM document"),
        "processes": db.count("SELECT COUNT(*) FROM process_instance"),
    }


# ------------------------------------------------------------------ 문서 헬퍼
def _doc(
    db: Database,
    people: dict[str, int],
    *,
    doc_no: str,
    title: str,
    doc_type: str,
    author: str = "qe1",
    verifier: str = "qm",
    approver: str = "ceo",
    record_type: str | None = None,
    retention_months: int | None = None,
    content: str = "",
) -> int:
    """문서를 생성하고 검토·승인까지 진행한다 (7.5.2)."""
    doc_id = documents.create(
        db,
        doc_no=doc_no,
        title=title,
        doc_type=doc_type,
        version="1.0",
        author_id=people[author],
        content=content or f"{title} 본문",
        record_type=record_type,
        retention_months=retention_months,
    )
    documents.submit_for_review(db, doc_id, people[verifier])
    documents.approve(db, doc_id, people[approver])
    return doc_id


# ------------------------------------------------------------------- 7.1.2 인원
def _people(db: Database) -> dict[str, int]:
    roster = [
        ("ceo", "E001", "김대표", "top_management", "경영진"),
        ("qm", "E002", "이품질", "quality_director", "품질보증"),
        ("qe1", "E003", "박검사", "quality_engineer", "품질보증"),
        ("qe2", "E004", "정시험", "quality_engineer", "품질보증"),
        ("pm", "E005", "최프로", "pmo_head", "사업관리"),
        ("eng", "E006", "한설계", "engineering_director", "기술개발"),
        ("eng2", "E007", "오구조", "design_engineer", "기술개발"),
        ("prod", "E008", "강생산", "production_director", "생산"),
        ("op1", "E009", "윤용접", "operator", "생산"),
        ("proc", "E010", "서구매", "procurement_director", "구매"),
        ("rams", "E011", "노신뢰", "rams_manager", "기술개발"),
        ("safety", "E012", "구안전", "safety_manager", "안전"),
        ("hr", "E013", "장인사", "hr_manager", "경영지원"),
        ("metro", "E014", "표계측", "metrology_manager", "품질보증"),
        ("cfg", "E015", "형상관", "configuration_manager", "기술개발"),
        ("ops", "E016", "운영총", "operations_director", "생산"),
        ("svc", "E017", "봉서비", "service_director", "서비스"),
        ("sales", "E018", "판영업", "sales_director", "영업"),
        ("maint", "E019", "설정비", "maintenance_manager", "생산"),
        ("audit1", "E020", "감사일", "lead_auditor", "품질보증"),
        ("audit2", "E021", "감사이", "lead_auditor", "경영지원"),
        ("audit3", "E022", "감사삼", "lead_auditor", "기술개발"),
    ]
    people: dict[str, int] = {}
    for key, emp_no, name, role, department in roster:
        people[key] = competence.add_person(
            db, emp_no=emp_no, name=name, role=role, department=department
        )
    return people


# ---------------------------------------------- 4장·5장·6장 거버넌스 및 기획
def _governance(db: Database, people: dict[str, int]) -> None:
    manual = _doc(
        db,
        people,
        doc_no="RQMS-MAN-001",
        title=f"{ORG} 철도용 품질경영시스템 매뉴얼",
        doc_type="manual",
        author="qm",
        verifier="qe1",
        approver="ceo",
    )
    governance.record_scope(
        db,
        year=YEAR,
        doc_id=manual,
        products_services=(
            "전동차 출입문 시스템(설계·개발, 제조, 시운전 지원, 보증 및 유지보수 지원)"
        ),
        exclusions={},
    )

    policy_doc = _doc(
        db,
        people,
        doc_no="RQMS-POL-001",
        title="품질 및 제품안전 방침",
        doc_type="policy",
        author="qm",
        verifier="qe1",
        approver="ceo",
    )
    governance.record_quality_policy(
        db,
        year=YEAR,
        doc_id=policy_doc,
        topics={
            "failure_prevention": "설계 FMEA·공정 FMEA 및 초도품 검사로 고장을 사전 예방한다.",
            "customer_expectations": "고객 요구사항을 조항별로 확인하고 납기·품질을 준수한다.",
            "safety": "IEC 62278 에 따라 제품 안전 무결성을 확보하고 안전 목표를 관리한다.",
        },
    )

    plan_doc = _doc(
        db,
        people,
        doc_no="RQMS-BP-001",
        title=f"{YEAR} 요약 사업계획",
        doc_type="procedure",
        author="ops",
        verifier="qm",
        approver="ceo",
    )
    governance.record_business_plan(
        db,
        year=YEAR,
        doc_id=plan_doc,
        topics={
            "business_objectives": "출입문 시스템 매출 20% 성장, 영업이익률 8% 달성",
            "market_strategy": "국내 광역철도 및 동남아 수출 시장 동시 공략",
            "product_service_strategy": "HR-DOOR-2000 플랫폼 확장, 구형 모델 단계적 단산",
            "management_review_outputs": f"{YEAR - 1} 경영검토 결정사항 12건 반영",
            "resource_planning": "생산인력 8명 증원, 조립 라인 1개 증설",
            "risks_opportunities": "SWOT 및 FMEA 기반 전사 리스크 등록부 운영",
            "business_continuity": "핵심 부품 이원화 및 재해복구 계획 운영",
            "customer_needs": "정비 편의성(MTTR 단축) 및 LCC 절감 요구 증가",
            "interested_party_inputs": "핵심 공급자 합동 성과검토 의견 반영",
            "technology_and_regulatory_changes": "CLC/TS 50701 사이버보안 요구 대응",
            "capacity_vs_forecast": "수주잔고 대비 생산능력 92% 가동 예상",
            "merger_outsourcing_transfer": "표면처리 공정 외부 이전 검토(8.1.1.2 적용)",
        },
    )
    governance.record_social_responsibility(
        db,
        year=YEAR,
        statement="ISO 26000 핵심 주제(지배구조·인권·노동관행·환경·공정운영) 준수 선언",
    )

    for origin, name, requirement in [
        ("external", "철도안전법 및 국토교통부 형식승인 요건", "형식승인 유지"),
        ("external", "원자재 가격 변동", "원가 변동 리스크 관리"),
        ("internal", "설계 인력 고령화", "지식 이전 및 승계계획 필요"),
    ]:
        governance.record_context_issue(
            db, origin=origin, name=name, requirement=requirement
        )
    for origin, name, requirement in [
        ("external", "발주처(도시철도운영기관)", "납기 준수, RAMS 목표 충족, LCC 절감"),
        ("external", "핵심 외부공급자", "요구사항 조기 공유 및 납기 예측 제공"),
        ("internal", "생산 부문", "설계 출력의 생산 적합성 및 작업지침 명확화"),
        ("external", "규제기관", "안전 승인 및 형상 추적성"),
    ]:
        governance.record_interested_party(
            db, origin=origin, name=name, requirement=requirement
        )

    governance.appoint_stop_authority(
        db, person_id=people["qm"], scope="생산 및 출하", independent_of="생산"
    )

    objectives = [
        ("QO-01", "고객 납기준수율 95% 이상 달성", "organization", 95.0, "%", "PI-COTD", False),
        ("QO-02", "품질실패비용률 1.5% 이하 유지", "organization", 1.5, "%", "PI-QDC", False),
        ("QO-03", "안전관련 부적합 0건 유지", "organization", 0.0, "건", "PI-CNC", True),
        ("QO-04", "고객만족도 85점 이상", "organization", 85.0, "점", "PI-CSAT", False),
    ]
    for code, desc, level, target, unit, pi, safety in objectives:
        objective_id = governance.set_quality_objective(
            db,
            code=code,
            description=desc,
            level=level,
            target_value=target,
            unit=unit,
            responsible_id=people["qm"],
            due_on=add_months(today(), 12),
            resources="품질보증팀 3명, 품질정보시스템",
            evaluation_method="월간 PI 측정 및 분기 프로세스 검토",
            indicator_code=pi,
            safety_related=safety,
        )
        governance.evaluate_objective(db, objective_id, achieved=True)

    # 4.4 / 5.3.1 b) — 프로세스 등록 및 오너 임명
    owner_by_role = {
        "quality_director": "qm",
        "operations_director": "ops",
        "metrology_manager": "metro",
        "hr_manager": "hr",
        "pmo_head": "pm",
        "configuration_manager": "cfg",
        "engineering_director": "eng",
        "procurement_director": "proc",
        "production_director": "prod",
        "service_director": "svc",
        "rams_manager": "rams",
        "safety_manager": "safety",
        "sales_director": "sales",
    }
    for process in load_registry().processes:
        proc_doc = _doc(
            db,
            people,
            doc_no=f"RQMS-PRC-{process.code}",
            title=f"{process.name_ko} 기술서",
            doc_type="procedure",
            author="qe1",
            verifier="qm",
            approver="ceo",
        )
        owner_key = owner_by_role.get(process.owner_role, "qm")
        governance.register_process(
            db,
            code=process.code,
            owner_id=people[owner_key],
            description_doc=proc_doc,
            inputs=f"{process.name_ko} 입력: 상위 프로세스 출력, 고객·법규 요구사항",
            outputs=f"{process.name_ko} 출력: 승인된 기록 및 후속 프로세스 입력",
            sequence_note=f"상위: {process.parent or 'RQMS 최상위'} / 후속: 성과평가(9장)",
            criteria="프로세스 PI 목표 달성 및 부적합 0건",
            resources="지정 인원, 정보시스템, 설비",
            risk_criteria="FMEA 기반 등급 9 이상 시 통제 강화(4.4.3 f)",
        )
        governance.record_process_training(
            db,
            process_code=process.code,
            person_id=people[owner_key],
            understanding_evidence=f"{process.code} 프로세스 교육 필기평가 90점",
        )


def _support(db: Database, people: dict[str, int]) -> None:
    """7장 지원 — 자원, 역량, 측정자원, 지식, 의사소통."""
    resource_doc = _doc(
        db,
        people,
        doc_no="RQMS-RES-001",
        title=f"{YEAR} 자원 계획서",
        doc_type="procedure",
        author="qe1",
        verifier="ops",
        approver="ceo",
    )
    support.record_resource_plan(
        db,
        year=YEAR,
        doc_id=resource_doc,
        topics={
            "people_and_infrastructure": "프로세스별 필요 인원 62명, 조립라인 3기, 시험설비 5기",
            "order_book_and_forecast": "수주잔고 420억, 차년도 예측 480억 반영",
            "risk_provision": "핵심 인력 이탈·설비 고장 대비 예비 자원 5% 확보",
        },
    )
    support.record_work_environment(
        db,
        year=YEAR,
        description="조립장 온도 18~26℃, 습도 40~60%, 조도 500lx 이상 유지 및 안전보건 관리",
    )

    # 7.2 역량 — 업무별 필요역량 정의 후 배정
    requirements_map = [
        ("welding", "welding_qualification", 3, True),
        ("inspection", "measurement_technique", 3, True),
        ("design", "structural_analysis", 3, True),
        ("audit", "iso22163_requirements", 3, True),
        ("configuration", "configuration_management", 2, False),
    ]
    for task, comp, level, relevant in requirements_map:
        competence.define_requirement(
            db,
            task_code=task,
            competence_code=comp,
            min_level=level,
            quality_or_safety_relevant=relevant,
        )

    grants = [
        ("op1", "welding_qualification", 4, "welding", "KS B 0885 용접기능 자격 취득"),
        ("qe1", "measurement_technique", 3, "inspection", "3차원 측정 사내인증 통과"),
        ("eng2", "structural_analysis", 3, "design", "구조해석 실무 3년 및 사내평가 합격"),
        ("audit1", "iso22163_requirements", 4, "audit", "ISO 22163 내부심사원 과정 수료"),
        ("audit2", "iso22163_requirements", 3, "audit", "ISO 22163 내부심사원 과정 수료"),
        ("audit3", "iso22163_requirements", 3, "audit", "ISO 22163 내부심사원 과정 수료"),
        ("cfg", "configuration_management", 3, "configuration", "ISO 10007 교육 수료"),
    ]
    for key, comp, level, task, evidence in grants:
        competence.record_competence(
            db,
            person_id=people[key],
            competence_code=comp,
            level=level,
            evidence=evidence,
            valid_until=add_months(today(), 36),
        )
        competence.assign_task(db, person_id=people[key], task_code=task)

    # 7.1.5 측정자원
    for ident, kind, location in [
        ("MR-001", "3차원 측정기", "품질보증 계측실"),
        ("MR-002", "토크 렌치", "조립 2라인"),
        ("MR-003", "절연저항 시험기", "전장 시험실"),
    ]:
        resource_id = calibration.register_resource(
            db,
            ident=ident,
            resource_type=kind,
            location=location,
            interval_months=12,
            custodian_id=people["metro"],
            used_in_special_process=ident == "MR-002",
        )
        calibration.record_calibration(
            db,
            resource_id=resource_id,
            result="pass",
            reference_standard="KRISS 소급 표준기 (게이지블록 세트 GB-12)",
            procedure_ref="RQMS-INS-CAL-01",
            performed_by_id=people["metro"],
            internal=True,
            acceptance_criteria="최대허용오차 ±0.01mm",
            ambient_suitable=True,
        )

    # 7.1.6 지식 / 7.4 의사소통 / 8.1.1.1 혁신
    support.capture_lesson(
        db,
        source_type="project",
        source_ref="PRJ-2023-01",
        description="출입문 가이드 레일 공차 누적으로 재작업 발생 — 공차 배분 표준화",
        is_good_practice=True,
        communicated_to="기술개발, 생산, 품질보증",
    )
    support.capture_lesson(
        db,
        source_type="nonconformity",
        source_ref="NC-2024-018",
        description="전장 커넥터 압착 불량 — 압착 공정을 특수공정으로 지정",
        communicated_to="생산, 품질보증",
    )
    support.plan_communication(
        db,
        topic="RQMS 방침·목표 및 프로세스 변경",
        timing="분기 1회 및 변경 시",
        audience="전 직원",
        method="사내 포털 및 부서 회의",
        communicator="품질보증 책임자",
    )
    support.record_communication(
        db,
        topic=f"{YEAR} 품질방침 및 품질목표 공표",
        audience="전 직원",
        method="사내 포털 공지 및 교육",
        communicator="품질보증 책임자",
    )
    support.propose_innovation(
        db,
        ref_no="INN-001",
        title="출입문 구동부 예지정비 알고리즘 적용",
        business_env_change="운영기관의 예지정비 요구 증가 및 센서 단가 하락",
        priority=1,
        resources="기술개발 2명, 현장 데이터 수집 인프라",
        stakeholders="발주처 정비부서, 센서 공급자",
    )


def _risk(db: Database, people: dict[str, int]) -> None:
    """6.1 리스크·기회 및 사업연속성."""
    risk.register(
        db,
        ref_no="R-ORG-001",
        kind="risk",
        scope="organization",
        description="핵심 구동모터 단일 공급처 의존",
        method="FMEA",
        likelihood=3,
        impact=4,
        action="제2 공급처 승인 및 6개월 안전재고 확보",
        action_owner_id=people["proc"],
        due_on=add_months(today(), 6),
    )
    opportunity = risk.register(
        db,
        ref_no="R-ORG-002",
        kind="opportunity",
        scope="organization",
        description="해외 운영기관의 LCC 기반 발주 확대",
        method="SWOT",
        likelihood=3,
        impact=3,
        action="LCC 산정 역량 강화 및 제안서 표준화",
        action_owner_id=people["rams"],
        due_on=add_months(today(), 9),
    )
    risk.review(
        db,
        opportunity,
        effectiveness_note="LCC 제안 표준화로 수주 2건 확보 — 조치 효과 확인",
        close=True,
    )
    risk.register(
        db,
        ref_no="R-PRC-001",
        kind="risk",
        scope="process",
        scope_ref="SPP",
        description="용접 작업자 자격 만료 누락으로 특수공정 중단",
        method="FMEA",
        likelihood=2,
        impact=4,
        action="자격 만료 60일 전 자동 알림 및 재자격 계획 수립",
        action_owner_id=people["prod"],
        due_on=add_months(today(), 3),
    )

    bcp_doc = _doc(
        db,
        people,
        doc_no="RQMS-BCP-001",
        title="사업연속성 계획",
        doc_type="procedure",
        author="qe1",
        verifier="ops",
        approver="ceo",
    )
    record_id = risk.record_continuity_plan(
        db,
        year=YEAR,
        doc_id=bcp_doc,
        topics={
            "interruptions": "라인 정지 시 대체 라인 전환 절차",
            "supply_chain": "핵심 부품 이원화 및 안전재고",
            "labour_shortage": "다기능 작업자 양성 및 협력사 인력 지원",
            "critical_technologies": "설계 데이터 이중 백업 및 원격 접근",
            "key_equipment_failure": "핵심 설비 예비품 확보 및 긴급 정비 계약",
            "field_returns": "현장 회수품 격리·분석 절차",
            "succession_plan": "품질·설계 핵심 직무 후임자 지정",
            "information_technology": "재해복구센터 및 RPO 4시간",
            "communication": "비상 연락망 및 고객 통보 절차",
            "emergency_or_crisis": "위기관리위원회 운영 규정",
        },
        responsibilities="위기관리위원회(위원장: 대표이사), 부문별 BCP 담당자 지정",
    )
    risk.verify_continuity_plan(
        db, record_id, evidence=f"{YEAR}년 상반기 라인 전환 모의훈련 결과 보고서"
    )


# ------------------------------------------------------------- 8.1.2 입찰 관리
def _tender(db: Database, people: dict[str, int]) -> str:
    tender_no = f"TDR-{YEAR}-001"
    tender.open_tender(
        db,
        tender_no=tender_no,
        customer="○○도시철도운영기관",
        title="전동차 출입문 시스템 120편성 공급",
    )
    _register_requirements(db, owner_scope="tender", owner_ref=tender_no)
    spec_doc = _doc(
        db,
        people,
        doc_no=f"RQMS-SPEC-{tender_no}",
        title=f"{tender_no} 기술규격서",
        doc_type="procedure",
        author="eng2",
        verifier="eng",
        approver="ceo",
    )
    requirements.document_specification(
        db, owner_scope="tender", owner_ref=tender_no, doc_id=spec_doc
    )
    tender.complete_review(
        db,
        tender_no,
        control_extent="리스크 등급 A 프로젝트 — 게이트 5단계 및 고객 입회검사 적용",
        risk_entry_ref="R-ORG-001, R-ORG-002",
        monetary_risk_eval="리스크 예비비 3.2억, 기회 이익 1.5억 반영",
        knowledge_input="PRJ-2023-01 교훈(공차 배분 표준화) 반영",
        deliverable_cost_plan="인도물 12종, 표준 원가계정 구조 기준 총원가 372억",
        resource_plan="계약 이행 인원 34명, 조립 2라인 및 시험설비 3기 배정",
    )
    tender.approve_offer(db, tender_no, approver_id=people["ceo"])
    tender.submit(db, tender_no)
    tender.record_outcome(db, tender_no, won=True)
    return tender_no


def _register_requirements(db: Database, *, owner_scope: str, owner_ref: str) -> None:
    """Annex B 범주를 포괄하는 요구사항을 등록하고 조항별 검토를 수행한다 (8.2)."""
    items = [
        ("F-01", "functional", "출입문은 비상 시 수동으로 개방 가능해야 한다", "customer"),
        ("P-01", "performance", "개폐 시간 3.0초 이내", "customer"),
        ("I-01", "integration", "TCMS 와 RS-485 프로토콜로 연동", "customer"),
        ("N-01", "non_functional", "EMI/EMC: EN 50121-3-2 만족", "statutory"),
        ("RA-01", "rams", "MTBF 200,000시간 이상, MTTR 30분 이내, SIL 2", "customer"),
        ("LC-01", "lcc", "30년 수명주기비용 편성당 1.8억 이하", "customer"),
        ("OB-01", "obsolescence", "보증기간 종료 후 10년간 예비품 공급 보장", "customer"),
        ("CC-01", "critical_characteristic", "가이드 레일 직진도 0.2mm/m 이내", "organization"),
        ("NT-01", "non_technical", "보증기간 24개월 및 현장 기술교육 제공", "customer"),
    ]
    for suffix, req_type, text, source in items:
        req_id = requirements.register(
            db,
            req_no=f"{owner_ref}-{suffix}",
            owner_scope=owner_scope,
            owner_ref=owner_ref,
            req_type=req_type,
            text=text,
            source=source,
            operational_maturity="ready_to_use",
        )
        requirements.review_clause_by_clause(
            db,
            req_id,
            result="조항별 확인 완료 — 충족 가능",
            risk_assessed=True,
            verifiable=True,
            cascaded=True,
            verification_method="해석·계산 및 설계검증 시험",
            validation_method="형식시험 및 시운전 검증",
        )


# ------------------------------------------------------------ 8.1.3 프로젝트
def _project(db: Database, people: dict[str, int], tender_no: str) -> str:
    project_code = f"PRJ-{YEAR}-001"
    projects.create(
        db,
        code=project_code,
        name="○○ 전동차 출입문 시스템 공급",
        customer="○○도시철도운영기관",
        tender_no=tender_no,
        budget=37_200_000_000,
        planned_margin_pct=8.0,
        multi_site=True,
        safety_related=True,
    )

    plan_specs = [
        (
            "management",
            "프로젝트 관리계획서",
            {
                "organization_chart": "PM 1, 설계 4, 생산 6, 품질 3, 구매 2",
                "targets_and_frame_conditions": "납기 24개월, 매출총이익 8%, 제외: 차량 개조",
                "responsibilities_and_authorities": "PM 승인한도 5억, 초과 시 경영진 승인",
                "execution_rules": "게이트 5단계, 주간 진도회의, 변경은 CCB 승인",
                "aligned_function_plans": "영업·설계·생산·품질·구매 및 컨소시엄 계획 통합",
                "deliverables_per_phase": "단계별 인도물 12종(고객 승인 대상 5종 포함)",
                "change_control": "범위·일정·원가 변경은 8.1.4.2 변경관리 적용",
                "work_split_and_interfaces": "본사 설계 / 창원공장 제조 / 협력사 전장",
                "specific_responsibilities": "사이트별 책임자 및 인터페이스 담당 지정",
                "communication_channels": "고객 단일 창구(PM), 사이트 간 주간 협의체",
                "applicable_processes": "RQMS 전 프로세스 적용, 사이트 고유 지침 병행",
            },
        ),
        (
            "quality",
            "프로젝트 품질계획서",
            {
                "quality_assurance": "설계검토 3단계, 공정 FMEA, FAI, 고객 입회검사",
                "quality_control": "검사·시험계획(ITP) 기반 공정검사 및 최종검사",
            },
        ),
        (
            "hr",
            "프로젝트 인력계획서",
            {
                "core_team": "PM, 설계책임, 생산책임, 품질책임, 구매책임 지명",
                "required_competence": "프로젝트관리 도구, WBS, 출입문 제품지식",
                "training": "프로젝트 착수 교육 및 특수공정 자격 유지",
            },
        ),
        (
            "communication",
            "프로젝트 의사소통계획서",
            {
                "internal": "주간 진도회의, 월간 경영보고",
                "external": "고객 월간 공정회의, 지연 시 즉시 통보(8.2.1.1)",
            },
        ),
        (
            "configuration",
            "형상관리 계획서",
            {"baselines": "as-designed / as-built / as-maintained", "ccb": "월 2회 운영"},
        ),
    ]
    for kind, title, covers in plan_specs:
        doc_id = _doc(
            db,
            people,
            doc_no=f"RQMS-{project_code}-{kind.upper()}",
            title=f"{project_code} {title}",
            doc_type="procedure",
            author="pm",
            verifier="qm",
            approver="ceo",
        )
        projects.attach_plan(
            db, project_code=project_code, plan_kind=kind, doc_id=doc_id, covers=covers
        )

    wbs = [
        ("1000", "프로젝트 관리", "pm", 720, True, None),
        ("2000", "시스템 설계", "eng", 240, True, None),
        ("3000", "전장 부품 조달", "proc", 180, False, "SUP-ELEC"),
        ("4000", "제조 및 조립", "prod", 300, True, None),
        ("5000", "시험 및 인도", "qm", 120, True, None),
    ]
    start = today()
    for code, name, owner, duration, critical, provider in wbs:
        wp_id = projects.add_work_package(
            db,
            project_code=project_code,
            wbs_code=code,
            name=name,
            owner_id=people[owner],
            duration_days=duration,
            start_on=start,
            finish_on=add_months(start, max(1, duration // 30)),
            predecessors="",
            on_critical_path=critical,
            external_provider=provider,
        )
        projects.verify_work_package(db, wp_id)

    projects.set_schedule(
        db,
        project_code=project_code,
        start_on=start,
        finish_on=add_months(start, 24),
        customer_delivery_on=add_months(start, 22),
        critical_path="1000 → 2000 → 4000 → 5000 (주공정, 총 24개월)",
    )
    projects.record_cost(
        db,
        project_code=project_code,
        cost_account="4000-제조",
        period=PERIOD,
        budget=18_000_000_000,
        actual=4_200_000_000,
        estimate_at_completion=17_800_000_000,
    )

    # 8.1.3.1 게이트 방식 단계검토 — 미결사항 종결 후 통과
    projects.plan_phase_review(
        db,
        project_code=project_code,
        phase="planning",
        planned_on=today(),
        mandatory_participants="pm,qm,eng,prod,proc",
        gate_checklist_doc=_doc(
            db,
            people,
            doc_no=f"RQMS-GATE-{project_code}-PLANNING",
            title=f"{project_code} 기획 단계 게이트 체크리스트",
            doc_type="template",
            author="pm",
            verifier="qm",
            approver="ceo",
        ),
    )
    issue_id = projects.raise_open_issue(
        db,
        project_code=project_code,
        description="컨소시엄 파트너 인터페이스 정의 미완료",
        owner_id=people["pm"],
        due_on=add_months(today(), 1),
        phase="planning",
        resource_note="시스템 엔지니어 1명 2주 투입",
    )
    projects.close_open_issue(db, issue_id)
    projects.hold_phase_review(
        db,
        project_code=project_code,
        phase="planning",
        decision="accepted",
        actual_participants="pm,qm,eng,prod,proc",
    )
    projects.hold_project_review(
        db,
        project_code=project_code,
        performance="요구사항 100% 검토 완료, 일정 준수, 원가 계획 대비 △1.1%",
        forecast="완성시점 추정원가 178억, 매출총이익 8.3% 예상",
        risk_status="R-ORG-001 완화 진행(제2 공급처 평가 중)",
        open_issue_followup="이전 미결사항 1건 종결, 신규 0건",
        reported_to="경영진(대표이사 및 운영총괄)",
        countermeasures="해당 없음",
    )
    return project_code


# ----------------------------------------------------- 8.1.4 형상관리·변경관리
def _configuration(db: Database, project_code: str) -> None:
    configuration.add_item(
        db,
        project_code=project_code,
        part_no="HR-DOOR-2000",
        name="출입문 시스템(상위)",
        traceability_method="시스템 시리얼 라벨",
        revision="A",
    )
    items = [
        ("HR-DR-PANEL", "도어 패널", False, "로트번호", False),
        ("HR-DR-DRIVE", "구동 유닛", True, "시리얼 각인", False),
        ("HR-DR-CTRL", "제어 보드", True, "시리얼 바코드", False),
        ("HR-DR-SENSOR", "장애물 감지 센서", True, "시리얼 바코드", True),
        ("HR-DR-RAIL", "가이드 레일", False, "로트번호", True),
    ]
    for part_no, name, safety, method, llru in items:
        configuration.add_item(
            db,
            project_code=project_code,
            part_no=part_no,
            name=name,
            parent_part_no="HR-DOOR-2000",
            safety_related=safety,
            traceability_method=method,
            is_llru=llru,
        )
    configuration.add_item(
        db,
        project_code=project_code,
        part_no="TOOL-CRIMP-01",
        name="압착 공구(형상항목)",
        parent_part_no="HR-DOOR-2000",
        traceability_method="공구 관리번호",
        is_tool=True,
    )

    configuration.establish_baseline(
        db,
        project_code=project_code,
        name="BL-AS-DESIGNED-1.0",
        kind="as_designed",
        part_numbers=[p[0] for p in items] + ["HR-DOOR-2000"],
    )

    change.raise_change(
        db,
        change_no="CR-001",
        scope="configuration",
        target_ref="HR-DR-CTRL",
        description="제어 보드 MCU 단산 대응 — 후속 모델로 대체",
        technical=True,
        customer_impact=True,
        from_failure=False,
    )
    change.analyse_impact(
        db,
        "CR-001",
        impact_analysis="기능 동등, 소프트웨어 재컴파일 필요. 리스크 등급 6(중).",
        proposal_verified=True,
        impact_on_delivered="기납품 0편성(양산 전 변경) — 영향 없음",
        revalidation_note="SIL 2 관련 기능 재유효성확인 시험 필요",
        affected_serials="양산 1호기 이후 전량",
    )
    change.notify_customer(db, "CR-001", agreed=True)
    change.approve(db, "CR-001", approver_id=1)
    change.implement(db, "CR-001")
    change.verify_implementation(db, "CR-001", effective=True)
    configuration.revise_item_in_baseline(
        db,
        project_code=project_code,
        baseline_name="BL-AS-DESIGNED-1.0",
        part_no="HR-DR-CTRL",
        new_revision="B",
    )
    configuration.establish_baseline(
        db,
        project_code=project_code,
        name="BL-AS-BUILT-1.0",
        kind="as_built",
        part_numbers=[p[0] for p in items],
    )


# --------------------------------------------------------------- 8.3 설계·개발
def _design(db: Database, people: dict[str, int], project_code: str) -> None:
    _register_requirements(db, owner_scope="product", owner_ref=PRODUCT)
    product_spec = _doc(
        db,
        people,
        doc_no="RQMS-SPEC-PRODUCT-001",
        title=f"{PRODUCT} 기술규격서",
        doc_type="procedure",
        author="eng2",
        verifier="eng",
        approver="ceo",
    )
    requirements.document_specification(
        db, owner_scope="product", owner_ref=PRODUCT, doc_id=product_spec
    )

    plan_doc = _doc(
        db,
        people,
        doc_no="RQMS-DND-PLAN-001",
        title=f"{PRODUCT} 설계·개발 계획서",
        doc_type="procedure",
        author="eng2",
        verifier="eng",
        approver="ceo",
    )
    design_no = "DSN-001"
    design.create(
        db,
        design_no=design_no,
        item=PRODUCT,
        project_code=project_code,
        architecture_level="system",
        plan_doc_id=plan_doc,
        new_technology=True,
        safety_related=True,
        safety_standard="IEC 62278, IEC 62425 (SIL 2)",
    )
    design.confirm_inputs(
        db, design_no, conflicts_resolved=True, requirement_owner_ref=PRODUCT
    )
    design.hold_design_review(
        db,
        design_no=design_no,
        level="system",
        acceptance_criteria="설계검토 체크리스트 전 항목 충족, 미결사항 0건",
        mandatory_participants="eng,rams,safety,prod,qm",
        actual_participants="eng,rams,safety,prod,qm,eng2",
        decision="accepted",
        decision_authority_present=True,
        multidisciplinary=True,
    )

    baseline_id = int(
        db.require(
            "baseline",
            project_id=db.require("project", code=project_code)["id"],
            name="BL-AS-DESIGNED-1.0",
        )["id"]
    )
    test_plan_doc = _doc(
        db,
        people,
        doc_no="RQMS-TP-001",
        title=f"{PRODUCT} 설계검증 시험계획서",
        doc_type="procedure",
        author="qe2",
        verifier="eng",
        approver="ceo",
    )
    for kind in ("verification", "validation"):
        test_id = design.plan_test(
            db,
            design_no=design_no,
            kind=kind,
            plan_doc_id=test_plan_doc,
            objectives="개폐시간·내구·EMC 요구사항 충족 확인",
            conditions="상온 23±2℃, 습도 50±10%, 전원 DC 100V",
            product_under_test="HR-DOOR-2000 시작품 #1 (BL-AS-DESIGNED-1.0)",
            resources="내구시험기, EMC 챔버, 3차원 측정기(MR-001)",
            acceptance_criteria="개폐시간 ≤ 3.0초, 100만회 내구 후 기능 정상, EN 50121-3-2 만족",
            recorded_parameters="개폐시간, 구동전류, 소음, 방사성 방출",
            method="RQMS-INS-TEST-01 절차에 따른 단계별 시험",
            baseline_id=baseline_id,
        )
        design.record_test_result(db, test_id, result="pass", criteria_met=True)

    design.complete_verification(db, design_no)
    design.complete_validation(db, design_no)
    for row in db.query(
        "SELECT * FROM requirement WHERE owner_scope = 'product'"
    ):
        if row["verification_method"]:
            requirements.mark_verified(db, int(row["id"]))
        if row["validation_method"]:
            requirements.mark_validated(db, int(row["id"]))

    safety_case_doc = _doc(
        db,
        people,
        doc_no="RQMS-SAF-CASE-001",
        title=f"{PRODUCT} 안전 케이스 (SIL 2)",
        doc_type="procedure",
        author="safety",
        verifier="rams",
        approver="ceo",
    )
    output_doc = _doc(
        db,
        people,
        doc_no="RQMS-DND-OUT-001",
        title=f"{PRODUCT} 운전·정비 매뉴얼 및 설계 출력 묶음",
        doc_type="instruction",
        author="eng2",
        verifier="eng",
        approver="ceo",
    )
    design.release_outputs(
        db,
        design_no,
        approver_id=people["eng"],
        production_input_verified=True,
        application_doc_id=output_doc,
        safety_case_doc_id=safety_case_doc,
    )
    rams.record_safety_case(
        db,
        product=PRODUCT,
        applicable_standards="IEC 62278, IEC 62425, IEC 62279",
        safety_case_doc_id=safety_case_doc,
        sil_level="SIL 2",
        hazard_log="위험원 24건 식별, 잔여 리스크 모두 허용 수준(ALARP) 확인",
    )


# ------------------------------------------------------------- 8.4 외부공급
def _suppliers(db: Database, people: dict[str, int], project_code: str) -> None:
    catalogue = [
        ("SUP-ELEC", "한빛전장", "key", "전장 부품(제어 보드, 센서)"),
        ("SUP-MECH", "대성정밀", "standard", "기계 가공품(가이드 레일)"),
    ]
    for code, name, classification, scope in catalogue:
        suppliers.register(db, code=code, name=name)
        suppliers.classify(
            db,
            code,
            classification=classification,
            criteria_note=(
                "요구사항 충족능력, 전략적 중요도, 과거 실적, 시장정보 및 운용성숙도 평가"
            ),
        )
        suppliers.evaluate(
            db,
            code,
            people_infrastructure_processes=(
                "인원 자격, SMT 라인 및 시험설비, 공정관리 수준 현장 심사로 확인"
            ),
            certifications="ISO 9001 보유, ISO 22163 취득 추진 중(목표 공급자)",
            targeted=True,
        )
        suppliers.approve(
            db, code, approver_id=people["proc"], approval_scope=scope
        )
        suppliers.select_offer(
            db,
            code,
            analysis={
                "clause_by_clause_conformity": "기술요구 42개 조항 전수 확인, 충족",
                "total_cost_of_ownership": "LCC 포함 총소유비용 최저",
                "past_qcd_performance": "납기 97%, 부적합 320ppm, 품질실패비용 0.4%",
                "supplier_classification": f"{classification} 등급",
            },
        )

    requirement_pack = {
        key: "계약 부속서로 전달"
        for key in suppliers.REQUIRED_COMMUNICATION
    }
    po_no = "PO-2026-0001"
    suppliers.issue_purchase_order(
        db,
        po_no=po_no,
        supplier_code="SUP-ELEC",
        item="제어 보드 HR-DR-CTRL Rev.B",
        qty=480,
        required_on=add_months(today(), 4),
        requirements_communicated=requirement_pack,
        criticality="safety_critical",
        project_code=project_code,
        config_part_no="HR-DR-CTRL",
        is_new_or_modified=True,
        special_process_approval="압착 공정 사전 승인(RQMS-SPP-APR-01)",
    )
    suppliers.acknowledge_order(db, po_no)

    po_no2 = "PO-2026-0002"
    suppliers.issue_purchase_order(
        db,
        po_no=po_no2,
        supplier_code="SUP-MECH",
        item="가이드 레일 HR-DR-RAIL",
        qty=960,
        required_on=add_months(today(), 3),
        requirements_communicated=requirement_pack,
        project_code=project_code,
        config_part_no="HR-DR-RAIL",
    )
    suppliers.acknowledge_order(db, po_no2)

    # 8.4.2.1 신규/변경 EPPPS 출시 승인 — FAI 선행
    fai_plan = _doc(
        db,
        people,
        doc_no="RQMS-FAI-PLAN-001",
        title=f"{po_no} 제어 보드 FAI 계획서",
        doc_type="procedure",
        author="qe1",
        verifier="qm",
        approver="ceo",
    )
    fai.plan(
        db,
        fai_no="FAI-EPP-001",
        target_kind="eppps",
        target_ref=po_no,
        trigger="new_product",
        plan_doc_id=fai_plan,
        participants="품질보증, 구매, 기술개발, 공급자 품질담당",
        representative_serial="CTRL-B-0001",
    )
    fai.confirm_preconditions(
        db, "FAI-EPP-001", evidence="공급자 공정 준비도 점검표 및 설비 검증 결과 확인"
    )
    fai.perform_inspection(db, "FAI-EPP-001", process_review_done=True)
    fai.decide(db, "FAI-EPP-001", decision="approved", decided_by_id=people["qm"])

    project_id = int(db.require("project", code=project_code)["id"])
    as_built = int(db.require("baseline", project_id=project_id, name="BL-AS-BUILT-1.0")["id"])
    fai_id = int(db.require("fai", fai_no="FAI-EPP-001")["id"])
    suppliers.approve_release(
        db,
        po_no=po_no,
        approval_method="FAI + 초도 로트 전수검사 후 양산 승인",
        fai_id=fai_id,
        validated_before_first_use=True,
        baseline_id=as_built,
        approver_id=people["qm"],
    )

    suppliers.delegate_verification(
        db,
        supplier_code="SUP-ELEC",
        scope="제어 보드 출하검사(기능·절연시험)",
        requirements_text="RQMS-INS-EPP-01 에 따른 전수 기능시험 및 성적서 제출",
        supplier_acceptance_evidence="위임 합의서 SUP-ELEC-DEL-2026-01 (공급자 서명본)",
        control_measure="연 1회 공급자 현장 심사 및 월간 성적서 표본 검증",
    )
    suppliers.record_incoming_inspection(
        db,
        po_no=po_no,
        result="pass",
        evidence="공급자 성적서 및 입고 표본 검사(AQL 1.0) 합격",
        released_by_id=people["qe1"],
        planned_extent="초도 로트 전수, 이후 AQL 1.0 표본",
        delegated=True,
    )
    suppliers.record_incoming_inspection(
        db,
        po_no=po_no2,
        result="pass",
        evidence="재질 성적서 및 직진도 측정(MR-001) 합격",
        released_by_id=people["qe1"],
        planned_extent="로트별 표본 검사",
    )
    suppliers.assert_verified_for_use(db, po_no, "제조 투입")

    for code in ("SUP-ELEC", "SUP-MECH"):
        suppliers.review_performance(
            db,
            code,
            score=92.5 if code == "SUP-ELEC" else 88.0,
            ranking="A" if code == "SUP-ELEC" else "B",
            audit_criteria="부적합률, 납기준수율, 시정조치 대응시간 기준 연 1회 심사",
            feedback_given=True,
            development_plan="ISO 22163 취득 지원 및 공정능력 개선 과제 2건 합의",
        )


# ------------------------------------------------------- 8.5.1.3 특수공정
def _special_processes(db: Database, people: dict[str, int]) -> None:
    wi_doc = _doc(
        db,
        people,
        doc_no="RQMS-WI-CRIMP-01",
        title="전장 커넥터 압착 작업지침",
        doc_type="instruction",
        author="prod",
        verifier="qm",
        approver="ceo",
    )
    special_processes.register(
        db,
        code="SP-CRIMP",
        name="전장 커넥터 압착",
        applicable_standard="",
        risk_assessment="공정 FMEA 결과 RPN 96 — 압착 높이 100% 자동 검사 적용",
        owner_id=people["prod"],
        work_instruction_doc_id=wi_doc,
        six_m_covered={
            "management": "공정 책임자 및 승인 권한 정의",
            "manpower": "압착 자격자만 작업(자격 유효기간 24개월)",
            "machine": "압착 공구 TOOL-CRIMP-01, 토크렌치 MR-002 사용",
            "methods": "압착 높이 1.45±0.05mm, 인장력 120N 이상",
            "material": "지정 단자 및 전선 규격만 사용",
            "mother_nature": "온도 18~26℃, 습도 40~60% 유지",
        },
    )
    special_processes.register(
        db,
        code="SP-WELD",
        name="구조물 용접",
        applicable_standard="ISO 3834-2, KS B 0885",
        risk_assessment="공정 FMEA 결과 RPN 72 — 비파괴검사 10% 적용",
        owner_id=people["prod"],
    )
    for code in ("SP-CRIMP", "SP-WELD"):
        special_processes.qualify_process(
            db,
            code,
            valid_until=add_months(today(), 24),
            evidence="공정 자격 시험(시편 인장·단면 검사) 합격 보고서",
        )
        special_processes.qualify_operator(
            db,
            code=code,
            person_id=people["op1"],
            qualified_until=add_months(today(), 24),
        )
    special_processes.revalidate(
        db,
        "SP-CRIMP",
        reason="CR-001 제어 보드 변경에 따른 단자 규격 변경 — 재유효성확인 실시",
        valid_until=add_months(today(), 24),
    )


# ------------------------------------------------------------- 8.5 생산
def _production(db: Database, people: dict[str, int], project_code: str) -> None:
    # 8.5.1.4 생산설비
    for ident, name in [("EQ-ASSY-01", "출입문 조립 지그"), ("EQ-TEST-01", "내구 시험기")]:
        production.register_equipment(
            db,
            ident=ident,
            name=name,
            acceptance_criteria="치수 정밀도 ±0.05mm, 반복 정밀도 CMK ≥ 1.33",
            verification_interval_months=12,
            preventive_plan="월간 점검, 반기 정밀도 검증, 연간 오버홀",
            spare_parts_secured=True,
        )
        eq_fai_plan = _doc(
            db,
            people,
            doc_no=f"RQMS-FAI-PLAN-{ident}",
            title=f"{ident} 설비 FAI 계획서",
            doc_type="procedure",
            author="qe1",
            verifier="prod",
            approver="ceo",
        )
        fai_no = f"FAI-EQ-{ident}"
        fai.plan(
            db,
            fai_no=fai_no,
            target_kind="production_equipment",
            target_ref=ident,
            trigger="new_product",
            plan_doc_id=eq_fai_plan,
            participants="생산, 품질보증, 설비담당",
        )
        fai.confirm_preconditions(db, fai_no, evidence="설비 설치·시운전 점검표 합격")
        fai.perform_inspection(db, fai_no, process_review_done=True)
        fai.decide(db, fai_no, decision="approved", decided_by_id=people["qm"])
        production.validate_equipment_before_first_use(
            db, ident, fai_id=int(db.require("fai", fai_no=fai_no)["id"])
        )
        production.record_maintenance(
            db, ident=ident, kind="preventive", result="정상", downtime_hours=2.0
        )

    # 8.5.4 보존 규격
    preservation_doc = _doc(
        db,
        people,
        doc_no="RQMS-PRSV-001",
        title="제품 보존 규격",
        doc_type="instruction",
        author="prod",
        verifier="qm",
        approver="ceo",
    )
    production.define_preservation(
        db,
        scope="출입문 시스템 및 구성품",
        marking="품번·로트·시리얼 라벨 및 취급주의 표시",
        special_handling="제어 보드는 ESD 포장, 도어 패널은 전용 랙 수직 보관",
        cleaning="조립 전 이물 제거 및 청정도 등급 관리",
        shelf_life_control="접착제·씰 6개월 선입선출, 유효기간 표시 관리",
        environment="온도 5~35℃, 습도 70% 이하, 직사광선 차단",
        doc_id=preservation_doc,
        config_part_no="HR-DOOR-2000",
        project_code=project_code,
    )

    # 8.5.3 고객 소유물
    production.receive_external_property(
        db,
        ref_no="CP-001",
        owner_kind="customer",
        owner_name="○○도시철도운영기관",
        description="TCMS 인터페이스 시험용 통신 시뮬레이터 1식",
        protection_measure="전용 보관함 시건 관리, 반기 상태 점검, 반환 전 기능 확인",
    )

    # 8.5.1 생산 오더
    order_no = "PO-PRD-0001"
    prod_data = _doc(
        db,
        people,
        doc_no="RQMS-PRD-DATA-001",
        title="출입문 조립 생산 데이터(도면·BOM·공정흐름도)",
        doc_type="instruction",
        author="prod",
        verifier="eng",
        approver="ceo",
    )
    itp_doc = _doc(
        db,
        people,
        doc_no="RQMS-ITP-001",
        title="출입문 시스템 검사·시험계획(ITP)",
        doc_type="instruction",
        author="qe1",
        verifier="qm",
        approver="ceo",
    )
    production.create_order(
        db,
        order_no=order_no,
        item=PRODUCT,
        qty=120,
        approved_data_doc_id=prod_data,
        itp_doc_id=itp_doc,
        risk_assessment="공정 FMEA 및 유예작업 리스크 평가 완료(RPN 최대 96)",
        tool_program_list="TOOL-CRIMP-01, NC 프로그램 RAIL-01, 조립 지그 EQ-ASSY-01",
        project_code=project_code,
        config_part_no="HR-DOOR-2000",
        special_process_codes="SP-CRIMP,SP-WELD",
        is_first_run=True,
        scheduled_start_on=today(),
        scheduled_finish_on=add_months(today(), 18),
        shift="day",
    )
    production.verify_process(
        db,
        order_no,
        design_input_complete=True,
        equipment_capable=True,
        process_fmea="생산 공정 FMEA 개정 1.0 — 검출도 개선 조치 3건 반영",
    )

    prod_fai_plan = _doc(
        db,
        people,
        doc_no="RQMS-FAI-PLAN-PRD-001",
        title="출입문 시스템 초도품 FAI 계획서",
        doc_type="procedure",
        author="qe1",
        verifier="qm",
        approver="ceo",
    )
    fai.plan(
        db,
        fai_no="FAI-PRD-001",
        target_kind="internal_product",
        target_ref=order_no,
        trigger="new_product",
        plan_doc_id=prod_fai_plan,
        participants="품질보증, 생산, 기술개발, 고객 입회",
        representative_serial="HRD-0001",
    )
    fai.confirm_preconditions(
        db, "FAI-PRD-001", evidence="작업자 자격·설비 검증·자재 입고검사 완료 확인"
    )
    fai.perform_inspection(db, "FAI-PRD-001", process_review_done=True)
    fai.decide(db, "FAI-PRD-001", decision="approved", decided_by_id=people["qm"])

    production.validate_process(
        db,
        order_no,
        fai_id=int(db.require("fai", fai_no="FAI-PRD-001")["id"]),
        design_requirements_met=True,
        controlled_conditions_met=True,
        design_feedback="조립 공차 누적 개선 요청 2건 설계에 반영(도면 개정 A→B)",
    )
    production.release_serial_production(db, order_no)
    production.start_order(
        db, order_no, operator_ids={"SP-CRIMP": people["op1"], "SP-WELD": people["op1"]}
    )

    for serial in ("HRD-0001", "HRD-0002", "HRD-0003"):
        production.create_item(
            db,
            serial_no=serial,
            order_no=order_no,
            identification_method="기계판독 2D 코드 라벨",
            warranty_months=24,
        )
        production.record_inspection(
            db,
            order_no=order_no,
            serial_no=serial,
            itp_step="최종검사-기능시험",
            acceptance_criteria="개폐시간 ≤ 3.0초, 장애물 감지 100% 동작",
            result="pass",
            actual_data="개폐시간 2.82초, 감지 20/20 정상",
            inspector_id=people["qe1"],
            measuring_resource_id=int(db.require("measuring_resource", ident="MR-001")["id"]),
        )


def _delivery_and_nonconformity(
    db: Database, people: dict[str, int], project_code: str
) -> None:
    """8.6 출하, 8.7 부적합, 10.2 시정조치."""
    release.release_item(
        db,
        serial_no="HRD-0001",
        authorized_by_id=people["qm"],
        conformity_evidence="ITP 전 단계 합격, 최종검사 성적서 QR-2026-0001",
        design_no="DSN-001",
    )
    release.deliver_item(db, "HRD-0001", design_no="DSN-001")

    # 내부 부적합 → 시정조치 → 종결
    nonconformity.raise_nonconformity(
        db,
        nc_no="NC-2026-001",
        source="internal",
        description="가이드 레일 직진도 0.24mm/m (규격 0.20mm/m 초과)",
        qty=4,
        ref="PO-PRD-0001",
        detected_at_stage="공정검사",
        serial_no="HRD-0002",
        cost=1_200_000,
    )
    decision = nonconformity.evaluate_capa_need(
        db, "NC-2026-001", repeated=True, note="동일 부적합 3개월 내 2회 발생 — 시정조치 필수"
    )
    capa.open_capa(
        db,
        capa_no="CAPA-2026-001",
        source_type="nonconformity",
        source_ref="NC-2026-001",
        description="가이드 레일 직진도 초과 재발 방지",
        criteria_applied="반복 발생 및 중요특성 관련 — 10.2.3 b) 기준 충족",
        method="8D",
        owner_id=people["prod"],
        due_on=add_months(today(), 2),
        escalation_level=int(decision["escalation_level"]),
    )
    capa.record_analysis(
        db,
        "CAPA-2026-001",
        root_cause="가공 지그 마모로 클램프 압력 저하(8D D4)",
        actions="지그 교체, 마모 한도 기준 신설, 주간 점검 항목 추가(8D D5~D6)",
        similar_checked=True,
        risk_updated=True,
    )
    capa.close_capa(
        db,
        "CAPA-2026-001",
        effective=True,
        evidence="후속 3로트 직진도 0.12~0.15mm/m, 재발 0건 — 효과성 확인(8D D7)",
    )
    capa_id = int(db.require("capa", capa_no="CAPA-2026-001")["id"])
    nonconformity.link_capa(db, "NC-2026-001", capa_id=capa_id)
    nonconformity.decide_disposition(
        db,
        "NC-2026-001",
        disposition="rework",
        authority_id=people["qm"],
    )
    nonconformity.verify_correction(db, "NC-2026-001")
    nonconformity.close(db, "NC-2026-001")

    # 고객 특채로 출하하는 경로 (8.6.1, 8.7.3 g)
    nonconformity.raise_nonconformity(
        db,
        nc_no="NC-2026-002",
        source="internal",
        description="도어 패널 도장 색차 ΔE 1.4 (규격 1.0 이하)",
        qty=1,
        ref="PO-PRD-0001",
        detected_at_stage="최종검사",
        serial_no="HRD-0003",
        cost=300_000,
    )
    nonconformity.evaluate_capa_need(
        db, "NC-2026-002", note="외관 특성, 안전·기능 영향 없음 — 시정조치 불요"
    )
    concession_id = nonconformity.raise_concession(
        db,
        concession_no="CON-2026-001",
        kind="customer",
        nc_no="NC-2026-002",
        description="색차 ΔE 1.4 상태로 1편성 한정 특채 출하",
        qty_authorized=1,
        valid_until=add_months(today(), 3),
        customer_approval_required=True,
        identification_agreed=True,
        recorded_on_doc="제품 적합성 선언서 DOC-2026-0003 에 특채 기재",
    )
    nonconformity.approve_concession_internally(
        db, "CON-2026-001", approver_id=people["qm"]
    )
    nonconformity.approve_concession_by_customer(db, "CON-2026-001")
    nonconformity.decide_disposition(
        db,
        "NC-2026-002",
        disposition="concession",
        authority_id=people["qm"],
        customer_informed=True,
        concession_id=concession_id,
    )
    release.release_item(
        db,
        serial_no="HRD-0003",
        authorized_by_id=people["qm"],
        conformity_evidence="기능 전 항목 합격, 외관 색차는 고객 승인 특채 CON-2026-001 적용",
        concession_id=concession_id,
        design_no="DSN-001",
    )
    nonconformity.close(db, "NC-2026-002")

    # 안전영향 부적합 → 추가 경영검토 대상 (9.3.1.1)
    nonconformity.raise_nonconformity(
        db,
        nc_no="NC-2026-003",
        source="customer",
        description="장애물 감지 센서 오작동 현장 신고 — 안전기능 영향 가능",
        qty=2,
        ref=project_code,
        detected_at_stage="현장 운용",
        cost=8_000_000,
        safety_impact=True,
    )
    safety_decision = nonconformity.evaluate_capa_need(
        db, "NC-2026-003", note="안전기능 영향 — 10.2.3 b) 기준 충족, 최고경영자 에스컬레이션"
    )
    capa.open_capa(
        db,
        capa_no="CAPA-2026-002",
        source_type="nonconformity",
        source_ref="NC-2026-003",
        description="장애물 감지 센서 오작동 근본원인 제거",
        criteria_applied="안전영향 부적합 — 10.2.3 b), e) 기준 충족",
        method="FRACAS",
        owner_id=people["safety"],
        due_on=add_months(today(), 1),
        escalation_level=int(safety_decision["escalation_level"]),
    )
    capa.record_analysis(
        db,
        "CAPA-2026-002",
        root_cause="센서 광학창 결로 — 방열 설계 및 히터 제어 로직 미흡",
        actions="히터 제어 로직 개정, 기납품 소프트웨어 업데이트, 설계 기준 반영",
        similar_checked=True,
        risk_updated=True,
    )
    capa.close_capa(
        db,
        "CAPA-2026-002",
        effective=True,
        evidence="업데이트 후 90일 무고장, 현장 데이터로 재발 없음 확인",
    )
    nonconformity.link_capa(
        db, "NC-2026-003", capa_id=int(db.require("capa", capa_no="CAPA-2026-002")["id"])
    )
    nonconformity.decide_disposition(
        db,
        "NC-2026-003",
        disposition="correction",
        authority_id=people["ceo"],
        customer_informed=True,
    )
    nonconformity.verify_correction(db, "NC-2026-003")
    nonconformity.close(db, "NC-2026-003")

    capa.record_improvement(
        db,
        ref_no="IMP-2026-001",
        kind="continual",
        description="조립 공차 배분 표준화로 재작업률 40% 감소",
        owner_id=people["prod"],
        source="CAPA-2026-001 후속 개선",
        benefit_note="연간 품질실패비용 3,200만원 절감",
    )

    # 8.5.5 인도 후 활동
    tech_doc = _doc(
        db,
        people,
        doc_no="RQMS-PDA-MAN-001",
        title="출입문 시스템 정비 매뉴얼 및 예비품 목록",
        doc_type="instruction",
        author="svc",
        verifier="eng",
        approver="ceo",
    )
    repair_doc = _doc(
        db,
        people,
        doc_no="RQMS-PDA-REP-001",
        title="출입문 시스템 수리 지침",
        doc_type="instruction",
        author="svc",
        verifier="qm",
        approver="ceo",
    )
    post_delivery.record(
        db,
        ref_no="PDA-2026-001",
        product=PRODUCT,
        customer="○○도시철도운영기관",
        activity_kind="maintenance",
        technical_doc_id=tech_doc,
        problem_solving_method="FRACAS",
        repair_instruction_doc_id=repair_doc,
        consignment_stock="현장 위탁재고 12품목 운영(협의서 SVC-2026-01)",
        feedback_to_rqms="센서 결로 현상 설계 기준 반영, 정비 매뉴얼 개정 요청",
    )


def _rams_and_obsolescence(db: Database, people: dict[str, int]) -> None:
    """8.8 RAMS/LCC, 8.10 단산 관리."""
    mtbf = rams.set_objective(
        db,
        product=PRODUCT,
        metric="MTBF",
        target=200_000,
        unit="시간",
        period=PERIOD,
        applicable_standard="IEC 62278 (EN 50126)",
        calculated=215_000,
        calculated_at_stage="design",
    )
    mttr = rams.set_objective(
        db,
        product=PRODUCT,
        metric="MTTR",
        target=30,
        unit="분",
        period=PERIOD,
        applicable_standard="IEC 62278 (EN 50126)",
        calculated=26,
        calculated_at_stage="design",
        direction="lower_is_better",
    )
    for occurred, symptom, category, component, severity in [
        (today(), "장애물 감지 센서 간헐 오작동", "electrical", "HR-DR-SENSOR", "major"),
        (today(), "구동 유닛 소음 증가", "mechanical", "HR-DR-DRIVE", "minor"),
    ]:
        rams.collect_field_data(
            db,
            product=PRODUCT,
            occurred_on=occurred,
            failure_symptom=symptom,
            failure_category=category,
            component=component,
            severity=severity,
            mileage_km=42_000,
            operating_hours=3_100,
            repair_cost=450_000,
        )
    rams.evaluate_objective(
        db,
        mtbf,
        field_value=208_000,
        analysis="현장 MTBF 208,000시간 — 목표 충족(FRACAS 분석 결과 반영)",
        feedback_to_design="센서 결로 대응 히터 로직 개정 반영",
        feedback_to_provider="SUP-ELEC 에 광학창 코팅 개선 요청",
    )
    rams.evaluate_objective(
        db,
        mttr,
        field_value=28,
        analysis="현장 MTTR 28분 — 목표 충족, LLRU 교체 절차 개선 효과",
        feedback_to_design="LLRU 접근성 개선안 차기 모델 반영",
    )
    rams.record_lcc(
        db,
        product=PRODUCT,
        period=PERIOD,
        calculated=1_750_000_000,
        actual=1_720_000_000,
        analysis="30년 LCC 편성당 17.2억 — 목표 18억 이하 충족(유사 제품 대비 4% 절감)",
    )

    obs_doc = _doc(
        db,
        people,
        doc_no="RQMS-OBS-PLAN-001",
        title=f"{PRODUCT} 단산 관리계획",
        doc_type="procedure",
        author="eng2",
        verifier="eng",
        approver="ceo",
    )
    obsolescence.create_plan(
        db,
        product=PRODUCT,
        version="1.0",
        strategy="second_source",
        support_until=add_months(today(), 144),
        doc_id=obs_doc,
    )
    risk_id = obsolescence.assess_risk(
        db,
        product=PRODUCT,
        part_no="HR-DR-CTRL MCU",
        risk_level="high",
        mitigation="후속 MCU 로 설계 변경(CR-001) 및 12개월 안전재고 확보",
        issue_kind="technical",
        config_part_no="HR-DR-CTRL",
        project_code=f"PRJ-{YEAR}-001",
    )
    obsolescence.communicate_to_customer(db, risk_id)
    obsolescence.close_risk(db, risk_id)
    obsolescence.assess_risk(
        db,
        product=PRODUCT,
        part_no="HR-DR-SENSOR 광학창",
        risk_level="medium",
        mitigation="대체 부품 2종 사전 평가",
        issue_kind="technical",
    )


def _transfer(db: Database, people: dict[str, int]) -> None:
    """8.1.1.2 프로세스 이전."""
    transfer_no = "TRF-2026-001"
    transfer.plan(
        db,
        transfer_no=transfer_no,
        process_code="SPP",
        from_site="본사 표면처리장",
        to_site="협력사 대성정밀 표면처리 라인",
        external=True,
        feasibility_study="원가·품질·납기 타당성 검토 결과 이전 타당(투자회수 2.1년)",
        risk_entry_ref="R-PRC-001",
        action_plan="설비 이설, 작업자 자격부여, FAI, 3개월 병행 생산 후 전환",
    )
    transfer.communicate_to_customer(db, transfer_no)

    change.raise_change(
        db,
        change_no="CR-002",
        scope="process_transfer",
        target_ref=transfer_no,
        description="표면처리 특수공정 외부 이전",
        origin="internal",
        customer_impact=True,
    )
    change.analyse_impact(
        db,
        "CR-002",
        impact_analysis="공정 위치 변경 — 제품 특성 영향 없음, 물류 리드타임 +2일",
        proposal_verified=True,
    )
    change.notify_customer(db, "CR-002", agreed=True)
    change.approve(db, "CR-002", approver_id=people["ceo"])
    change.implement(db, "CR-002")
    change.verify_implementation(db, "CR-002", effective=True)
    transfer.link_change(db, transfer_no, change_no="CR-002")

    trf_fai_plan = _doc(
        db,
        people,
        doc_no="RQMS-FAI-PLAN-TRF-001",
        title=f"{transfer_no} 이전 후 FAI 계획서",
        doc_type="procedure",
        author="qe1",
        verifier="qm",
        approver="ceo",
    )
    fai.plan(
        db,
        fai_no="FAI-TRF-001",
        target_kind="process_transfer",
        target_ref=transfer_no,
        trigger="transfer",
        plan_doc_id=trf_fai_plan,
        participants="품질보증, 생산, 구매, 협력사 품질담당",
    )
    fai.confirm_preconditions(
        db, "FAI-TRF-001", evidence="이설 설비 검증, 작업자 자격부여, 공정 조건 확인 완료"
    )
    fai.perform_inspection(db, "FAI-TRF-001", process_review_done=True)
    fai.decide(db, "FAI-TRF-001", decision="approved", decided_by_id=people["qm"])
    transfer.link_fai(
        db, transfer_no, fai_id=int(db.require("fai", fai_no="FAI-TRF-001")["id"])
    )
    transfer.approve(db, transfer_no)


def _customer(db: Database, people: dict[str, int]) -> None:
    """8.2.1 고객 의사소통, 9.1.2 고객만족."""
    customer.record_communication(
        db,
        topic="계약 인도물 목록 및 고객 승인 시점(PAP) 합의",
        customer="○○도시철도운영기관",
        method="공정회의 및 공문",
        communicator="프로젝트 관리자",
        project_code=f"PRJ-{YEAR}-001",
    )
    customer.notify_delay(
        db,
        customer="○○도시철도운영기관",
        project_code=f"PRJ-{YEAR}-001",
        reason="전장 부품 공급자 납기 지연(2주)",
        impact="3호기 조립 착수 2주 순연, 최종 인도일 영향 없음",
        countermeasure="조립 순서 재배열 및 특급 운송 적용",
    )

    customer.receive_complaint(
        db,
        complaint_no="CMP-2026-001",
        customer="○○도시철도운영기관",
        description="장애물 감지 센서 간헐 오작동 신고",
        nc_no="NC-2026-003",
    )
    customer.acknowledge(db, "CMP-2026-001")
    customer.link_capa(db, "CMP-2026-001", capa_no="CAPA-2026-002")
    customer.respond(db, "CMP-2026-001", lesson_shared=True)
    support.capture_lesson(
        db,
        source_type="complaint",
        source_ref="CMP-2026-001",
        description="센서 광학창 결로 — 방열·히터 설계 기준 신설",
        is_good_practice=True,
        communicated_to="기술개발, 서비스, 품질보증",
    )

    customer.record_satisfaction(
        db,
        customer="○○도시철도운영기관",
        period=PERIOD,
        method="연 2회 고객만족 설문(설계·납기·보증 항목)",
        score=88.0,
        note="납기 대응 만족, 정비 편의성 개선 요청",
    )


def _indicators(db: Database, people: dict[str, int]) -> None:
    """9.1.1 성과지표 측정 — 전 지표 측정 및 미달 지표 시정조치 연계."""
    registry = load_registry()
    values = {
        "PI-CSAT": 88.0,
        "PI-COTD": 96.4,
        "PI-CNC": 320.0,
        "PI-INC": 98.6,
        "PI-ENC": 640.0,
        "PI-EOTD": 96.0,
        "PI-QDC": 1.2,
        "PI-PC": 0.3,
        "PI-NCRT": 12.0,
        "PI-CAP": 92.0,
        "PI-RESOL": 24.0,
        "PI-EQDT": 1.8,
        "PI-DOC": 100.0,
        "PI-CAL": 100.0,
        "PI-CMP": 100.0,
        "PI-CHG": 100.0,
        "PI-REQ": 100.0,
        "PI-FAI": 100.0,
        "PI-RAM": 100.0,
        "PI-OBS": 50.0,  # 목표 90% 미달 — 시정조치 연계 시연
        "PI-AUD": 100.0,
    }
    indicators.record_failure_data(db, internal=2, external=1, period=PERIOD)

    for indicator in registry.indicators:
        value = values[indicator.code]
        capa_no = None
        if not indicator.is_met(value):
            capa_no = f"CAPA-PI-{indicator.code}"
            capa.open_capa(
                db,
                capa_no=capa_no,
                source_type="kpi" if indicator.is_kpi else "process_review",
                source_ref=f"{indicator.code}:{PERIOD}",
                description=f"{indicator.title_ko} 목표 미달 대응",
                criteria_applied="지표 목표 미달 — 9.1.3.1 기준에 따른 시정조치",
                method="4D",
                owner_id=people["qm"],
                due_on=add_months(today(), 3),
                escalation_level=1,
            )
            capa.record_analysis(
                db,
                capa_no,
                root_cause="단산 완화조치 승인 지연으로 완화율 저조",
                actions="완화조치 승인 절차 간소화 및 월간 추적 회의 신설",
                similar_checked=True,
            )
        indicators.record_measurement(
            db,
            indicator_code=indicator.code,
            period=PERIOD,
            value=value,
            analysis=f"{indicator.title_ko} {value}{indicator.unit} — "
            + ("목표 충족" if indicator.is_met(value) else "목표 미달, 시정조치 착수"),
            trend="전기 대비 개선" if indicator.is_met(value) else "전기 대비 악화",
            shared_with="최고경영자, 프로세스 오너, 관련 부문",
            capa_no=capa_no,
        )


def _audits(db: Database, people: dict[str, int]) -> None:
    """9.2 내부심사 — 필수·권고 프로세스 전체를 3년 프로그램으로 커버."""
    audit.create_programme(db, year=YEAR)
    auditor_specs = [
        ("audit1", "품질보증", "생산, 품질, 검사", "8.5, 8.6, 8.7, 9.1", "RQMS 절차 및 ISO 22163"),
        ("audit2", "경영지원", "경영, 인사, 문서, 구매", "4, 5, 6, 7, 8.4", "RQMS 절차 및 ISO 22163"),
        ("audit3", "기술개발", "설계, 형상, RAMS, 프로젝트", "8.1, 8.2, 8.3, 8.8", "RQMS 절차 및 ISO 22163"),
    ]
    home_by_key = {
        "audit1": "PSP,SPP,NCO,REL",
        "audit2": "DIC,CMP,RES,EPP,ROM",
        "audit3": "DND,CFG,RAM,PRJ,REQ",
    }
    for key, _dept, scope, clauses, criteria in auditor_specs:
        audit.register_auditor(
            db,
            person_id=people[key],
            knows_audit_principles=True,
            scope_knowledge=scope,
            clause_knowledge=clauses,
            criteria_knowledge=criteria,
            audits_performed=5,
            home_processes=home_by_key[key],
            refresh_training_on=today(),
        )

    audit.approve_programme(db, year=YEAR, multidisciplinary=True)

    report_doc = _doc(
        db,
        people,
        doc_no="RQMS-AUD-RPT-001",
        title=f"{YEAR} 내부심사 종합 보고서",
        doc_type="record",
        author="audit1",
        verifier="qm",
        approver="ceo",
        record_type="audit_report",
        retention_months=60,
    )

    # 심사원별로 자기 소속 프로세스를 제외하고 전 프로세스를 배분한다 (9.2.3.2 c, d).
    registry = load_registry()
    keys = ["audit1", "audit2", "audit3"]
    index = 0
    for process in registry.processes:
        chosen = None
        for _ in range(len(keys)):
            candidate = keys[index % len(keys)]
            index += 1
            home = set(home_by_key[candidate].split(","))
            if process.code not in home:
                chosen = candidate
                break
        assert chosen is not None
        audit_no = f"IA-{YEAR}-{process.code}"
        audit.plan_audit(
            db,
            audit_no=audit_no,
            year=YEAR,
            scope=f"{process.name_ko} 및 관련 조항",
            criteria="ISO 22163:2023 해당 조항 및 사내 프로세스 기술서",
            planned_on=today(),
            lead_auditor_id=people[chosen],
            team=str(people[chosen]),
            process_code=process.code,
            shifts_covered="주간/야간 교대 모두 포함" if process.code == "PSP" else "해당 없음",
        )
        audit.perform_audit(
            db, audit_no, report_doc_id=report_doc, reported_to="최고경영자 및 프로세스 오너"
        )

    # 심사 발견사항과 시정조치 연계 (9.2.2 e)
    capa.open_capa(
        db,
        capa_no="CAPA-AUD-001",
        source_type="audit",
        source_ref=f"IA-{YEAR}-OBS",
        description="단산 관리계획 검토 주기 기록 미비",
        criteria_applied="심사 경부적합 — 10.2.3 b) 기준 충족",
        method="4D",
        owner_id=people["eng"],
        due_on=add_months(today(), 2),
        escalation_level=1,
    )
    capa.record_analysis(
        db,
        "CAPA-AUD-001",
        root_cause="단산 관리계획 검토 주기가 절차에 명시되지 않음",
        actions="절차 개정 및 검토 알림 자동화",
        similar_checked=True,
    )
    capa.close_capa(
        db,
        "CAPA-AUD-001",
        effective=True,
        evidence="절차 개정 완료 및 후속 심사에서 재발 없음 확인",
    )
    audit.record_finding(
        db,
        audit_no=f"IA-{YEAR}-OBS",
        clause_id="8.10",
        grade="minor",
        description="단산 관리계획의 정기 검토 주기가 절차에 정의되지 않음",
        capa_id=int(db.require("capa", capa_no="CAPA-AUD-001")["id"]),
    )
    audit.record_finding(
        db,
        audit_no=f"IA-{YEAR}-KNW",
        clause_id="7.1.6.1.1",
        grade="opportunity",
        description="교훈 공유 범위를 협력사까지 확대할 기회",
    )


def _reviews(db: Database, people: dict[str, int], project_code: str) -> None:
    """9.4 프로세스 검토 및 9.3 경영검토."""
    registry = load_registry()
    for process in registry.processes:
        instance = db.require("process_instance", code=process.code)
        review.hold_process_review(
            db,
            process_code=process.code,
            owner_id=int(instance["owner_id"]),
            participants="프로세스 내부 이해관계자 대표(전·후속 프로세스 담당) 및 품질보증",
            fields={
                "conformity_note": "4.4.1 a), b), c), f) 요구사항 적합 확인",
                "previous_actions": "이전 검토 조치 전건 종결",
                "nonconforming_outputs": "프로세스 부적합 출력 모니터링 결과 이상 없음",
                "resources_note": "인원·정보시스템 자원 충분, 추가 소요 없음",
                "pi_analysis": "프로세스 PI 목표 대비 실적 분석 및 목표 달성 검토 완료",
                "pi_relevance_note": "PI 적절성 검토 — 변경 불요",
                "audit_capa_note": "심사 기인 시정조치 관리 상태 확인",
                "interested_party_input": "내·외부 이해관계자 요구사항 반영 확인",
                "decisions": "개선과제 1건 등록, 프로세스 기술서 유지",
            },
            reported_to_top_management=True,
        )

    mr_doc = _doc(
        db,
        people,
        doc_no="RQMS-MR-001",
        title=f"{YEAR} 연간 경영검토 보고서",
        doc_type="record",
        author="qm",
        verifier="qe1",
        approver="ceo",
        record_type="management_review_record",
        retention_months=120,
    )
    outputs = {
        "improvement_opportunities": "단산 완화 프로세스 자동화 및 협력사 지식 공유 확대",
        "qms_changes": "단산 관리 절차 개정, 압착 특수공정 지정 반영",
        "resource_needs": "품질정보시스템 고도화 예산 2억, 생산인력 8명 증원 승인",
        "objectives_achievement": "품질목표 4건 전건 달성(안전 목표 포함) 확인",
        "customer_satisfaction": "만족도 88점 — 정비 편의성 개선 과제 추진 결정",
    }
    review.hold_management_review(
        db,
        ref_no=f"MR-{YEAR}-01",
        inputs=review.management_review_inputs_snapshot(db),
        outputs=outputs,
        attendees="대표이사, 품질보증, 운영, 기술개발, 생산, 구매, 영업, 안전",
        doc_id=mr_doc,
        review_kind="annual",
    )
    review.hold_management_review(
        db,
        ref_no=f"MR-{YEAR}-02",
        inputs=review.management_review_inputs_snapshot(db),
        outputs=outputs,
        attendees="대표이사, 품질보증, 기술개발, 안전, 서비스",
        doc_id=mr_doc,
        review_kind="extraordinary",
        trigger=(
            "중대 품질사고 NC-2026-003(장애물 감지 센서 안전기능 영향)에 따른 추가 경영검토"
        ),
    )
