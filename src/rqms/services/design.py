"""DND — 제품·서비스 설계 및 개발 프로세스 (8.3).

강제 통제
    CTL-009  설계 출력은 검증·승인 후에만 출시 (8.3.5.1.1 a)
    CTL-010  설계 유효성확인 미완료 품목의 인도 금지 (8.3.4.4 b)
    CTL-047  검증·유효성확인 시험은 시험계획과 형상기준선 기록 필요 (8.3.4.5)
    CTL-057  안전관련 제품은 적용 안전표준 식별 및 안전 케이스 보유 (8.3.1.1 d, 8.8.3)
    CTL-058  설계검토는 승인기준·필수참석자(의사결정 권한) 요건 충족 (8.3.4.2)
    CTL-060  설계입력은 완전·명확해야 하며 상충 입력은 해결 (8.3.3)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import documents, requirements
from ._base import enforce

#: 8.3.2.1.1 NOTE — 설계 단계
STAGES = ("conceptual", "preliminary", "final")

#: 8.3.2.1.1 d) 제품 아키텍처 계층
LEVELS = ("component", "subsystem", "system")

#: 8.3.1.1 d) 안전관련 제품에 요구되는 표준 (또는 동등)
SAFETY_STANDARDS = ("IEC 62278", "IEC 62425", "IEC 62279", "EN 50126", "EN 50128", "EN 50129")


def create(
    db: Database,
    *,
    design_no: str,
    item: str,
    project_code: str | None = None,
    architecture_level: str = "component",
    plan_doc_id: int | None = None,
    new_technology: bool = False,
    safety_related: bool = False,
    safety_standard: str = "",
) -> int:
    """설계 건을 개설한다 (8.3.1, 8.3.2.1.1).

    안전관련 설계는 적용 안전표준을 식별해야 한다(8.3.1.1 d).
    """
    if architecture_level not in LEVELS:
        raise ValueError(f"알 수 없는 아키텍처 계층: {architecture_level}")
    if safety_related:
        enforce(
            "CTL-057",
            any(std in safety_standard for std in SAFETY_STANDARDS) or bool(safety_standard.strip()),
            f"설계 {design_no}: 안전관련 설계는 적용 안전표준(IEC 62278 또는 동등)을"
            " 식별해야 합니다(8.3.1.1 d).",
            db=db,
            context=f"design:{design_no}",
        )
    if plan_doc_id is not None:
        documents.assert_usable(db, plan_doc_id, f"설계계획 {design_no}")

    project_id = None
    if project_code:
        project_id = int(db.require("project", code=project_code)["id"])
    return db.insert(
        "design",
        design_no=design_no,
        project_id=project_id,
        item=item,
        architecture_level=architecture_level,
        plan_doc_id=plan_doc_id,
        new_technology=int(new_technology),
        safety_related=int(safety_related),
        safety_standard=safety_standard,
    )


def confirm_inputs(
    db: Database,
    design_no: str,
    *,
    conflicts_resolved: bool,
    requirement_owner_ref: str | None = None,
) -> Row:
    """설계 입력의 완전성·명확성을 확인한다 (8.3.3, 8.3.3.1.1).

    입력은 요구사항(8.2.2)에 근거해야 하므로, 해당 요구사항의 조항별 검토가 선행된다.
    상충하는 입력은 해결되어야 한다.
    """
    design = db.require("design", design_no=design_no)
    if requirement_owner_ref:
        requirements.assert_all_reviewed(
            db,
            owner_scope="product",
            owner_ref=requirement_owner_ref,
            purpose=f"설계 {design_no} 입력 확정",
        )
    enforce(
        "CTL-060",
        conflicts_resolved,
        f"설계 {design_no}: 상충하는 설계 입력이 해결되지 않았습니다(8.3.3).",
        db=db,
        context=f"design:{design_no}",
    )
    db.update(
        "design",
        design["id"],
        inputs_complete=1,
        input_conflicts_resolved=int(conflicts_resolved),
    )
    return db.fetch("design", design["id"])


def hold_design_review(
    db: Database,
    *,
    design_no: str,
    level: str,
    acceptance_criteria: str,
    mandatory_participants: str,
    actual_participants: str,
    decision: str,
    decision_authority_present: bool,
    multidisciplinary: bool = True,
) -> int:
    """설계검토를 실시한다 (8.3.4.2).

    다음 단계 진행 승인기준과 필수 참석자가 정의되어야 하고, 참석 기능 대표자는
    의사결정 권한을 가져야 한다.
    """
    design = db.require("design", design_no=design_no)
    enforce(
        "CTL-058",
        bool(acceptance_criteria.strip()) and bool(mandatory_participants.strip()),
        f"설계 {design_no}: 설계검토의 승인기준과 필수 참석자를 정의해야 합니다(8.3.4.2).",
        db=db,
        context=f"design:{design_no}",
    )
    required = {p.strip() for p in mandatory_participants.split(",") if p.strip()}
    actual = {p.strip() for p in actual_participants.split(",") if p.strip()}
    absent = sorted(required - actual)
    enforce(
        "CTL-058",
        not absent,
        f"설계 {design_no}: 설계검토 필수 참석자 불참 — {', '.join(absent)}",
        db=db,
        context=f"design:{design_no}",
    )
    enforce(
        "CTL-058",
        decision_authority_present,
        f"설계 {design_no}: 설계검토 참석 기능 대표자는 의사결정 권한을 가져야 합니다"
        " (8.3.4.2).",
        db=db,
        context=f"design:{design_no}",
    )
    return db.insert(
        "design_review",
        design_id=design["id"],
        level=level,
        held_on=today(),
        acceptance_criteria=acceptance_criteria,
        mandatory_participants=mandatory_participants,
        actual_participants=actual_participants,
        decision_authority_present=int(decision_authority_present),
        multidisciplinary=int(multidisciplinary),
        decision=decision,
    )


def plan_test(
    db: Database,
    *,
    design_no: str,
    kind: str,
    plan_doc_id: int,
    objectives: str,
    conditions: str,
    product_under_test: str,
    resources: str,
    acceptance_criteria: str,
    recorded_parameters: str,
    method: str,
    baseline_id: int,
) -> int:
    """검증·유효성확인 시험을 계획한다 (8.3.4.5 a, b).

    재현성을 위해 8.3.4.5 a) 1)~8) 항목이 모두 정의되어야 하고, 시험 대상 제품의
    형상은 기준선으로 기록되어야 한다.
    """
    if kind not in ("verification", "validation"):
        raise ValueError("kind 는 verification 또는 validation 여야 합니다.")
    design = db.require("design", design_no=design_no)
    documents.assert_usable(db, plan_doc_id, f"시험계획 {design_no}/{kind}")
    missing = [
        name
        for name, value in (
            ("objectives", objectives),
            ("conditions", conditions),
            ("product_under_test", product_under_test),
            ("resources", resources),
            ("acceptance_criteria", acceptance_criteria),
            ("recorded_parameters", recorded_parameters),
            ("method", method),
        )
        if not value.strip()
    ]
    enforce(
        "CTL-047",
        not missing,
        f"설계 {design_no} {kind} 시험계획 누락 항목(8.3.4.5 a): {', '.join(missing)}",
        db=db,
        context=f"design_test:{design_no}",
    )
    enforce(
        "CTL-047",
        baseline_id is not None,
        f"설계 {design_no}: 시험 대상 제품의 형상 기준선을 기록해야 합니다(8.3.4.5 b).",
        db=db,
        context=f"design_test:{design_no}",
    )
    db.fetch("baseline", baseline_id)
    return db.insert(
        "design_test",
        design_id=design["id"],
        kind=kind,
        plan_doc_id=plan_doc_id,
        objectives=objectives,
        conditions=conditions,
        product_under_test=product_under_test,
        resources=resources,
        acceptance_criteria=acceptance_criteria,
        recorded_parameters=recorded_parameters,
        method=method,
        baseline_id=baseline_id,
    )


def record_test_result(
    db: Database, test_id: int, *, result: str, criteria_met: bool
) -> Row:
    """시험 결과를 기록한다 (8.3.4.5 c)."""
    if result not in ("pass", "fail"):
        raise ValueError("result 는 pass 또는 fail 여야 합니다.")
    test = db.fetch("design_test", test_id)
    enforce(
        "CTL-047",
        bool(test["plan_doc_id"]) and bool(test["baseline_id"]),
        f"시험 {test_id}: 시험계획 또는 형상 기준선이 없어 결과를 기록할 수 없습니다"
        " (8.3.4.5).",
        db=db,
        context=f"design_test:{test_id}",
    )
    db.update(
        "design_test",
        test_id,
        performed_on=today(),
        result=result,
        criteria_met=int(criteria_met and result == "pass"),
    )
    return db.fetch("design_test", test_id)


def complete_verification(db: Database, design_no: str) -> Row:
    """설계 검증을 완료한다 (8.3.4.3).

    검증 시험이 합격기준을 충족해야 한다.
    """
    design = db.require("design", design_no=design_no)
    tests = db.query(
        "SELECT * FROM design_test WHERE design_id = ? AND kind = 'verification'",
        (design["id"],),
    )
    enforce(
        "CTL-047",
        bool(tests) and all(t["criteria_met"] for t in tests),
        f"설계 {design_no}: 모든 검증 시험이 합격기준을 충족해야 합니다(8.3.4.5 c).",
        db=db,
        context=f"design:{design_no}",
    )
    db.update("design", design["id"], verified_on=today())
    return db.fetch("design", design["id"])


def complete_validation(db: Database, design_no: str) -> Row:
    """설계 유효성확인을 완료한다 (8.3.4.4 a)."""
    design = db.require("design", design_no=design_no)
    tests = db.query(
        "SELECT * FROM design_test WHERE design_id = ? AND kind = 'validation'",
        (design["id"],),
    )
    enforce(
        "CTL-010",
        bool(tests) and all(t["criteria_met"] for t in tests),
        f"설계 {design_no}: 모든 유효성확인 시험이 합격기준을 충족해야 합니다(8.3.4.4 a).",
        db=db,
        context=f"design:{design_no}",
    )
    db.update("design", design["id"], validated_on=today())
    return db.fetch("design", design["id"])


def agree_validation_control_plan(db: Database, design_no: str) -> Row:
    """인도·시운전 종료 전 유효성확인을 마칠 수 없는 경우, 고객과 관리계획에 합의한다
    (8.3.4.4 b)."""
    design = db.require("design", design_no=design_no)
    db.update("design", design["id"], validation_waiver_agreed_on=today())
    return db.fetch("design", design["id"])


def release_outputs(
    db: Database,
    design_no: str,
    *,
    approver_id: int,
    production_input_verified: bool,
    application_doc_id: int,
    safety_case_doc_id: int | None = None,
) -> Row:
    """설계 출력을 출시한다 (8.3.5.1.1).

    검증·승인 전에는 출시할 수 없고(CTL-009), 생산 프로세스 입력 대비 검증이
    필요하며(8.3.5.1.1 b), 운전·정비 매뉴얼 등 적용 관련 문서가 포함되어야 한다(c).
    안전관련 설계는 안전 케이스를 보유해야 한다(8.8.3).
    """
    design = db.require("design", design_no=design_no)
    enforce(
        "CTL-009",
        bool(design["verified_on"]),
        f"설계 {design_no}: 검증 완료 전에는 출력을 출시할 수 없습니다(8.3.5.1.1 a).",
        db=db,
        context=f"design:{design_no}",
    )
    enforce(
        "CTL-009",
        production_input_verified,
        f"설계 {design_no}: 생산공정 입력 대비 검증이 필요합니다(8.3.5.1.1 b).",
        db=db,
        context=f"design:{design_no}",
    )
    documents.assert_usable(db, application_doc_id, f"설계 출력 문서 {design_no}")
    if design["safety_related"]:
        enforce(
            "CTL-057",
            safety_case_doc_id is not None,
            f"설계 {design_no}: 안전관련 설계는 안전 케이스를 보유해야 합니다(8.8.3).",
            db=db,
            context=f"design:{design_no}",
        )
        documents.assert_usable(db, safety_case_doc_id, f"안전 케이스 {design_no}")

    db.update(
        "design",
        design["id"],
        output_approved_by_id=approver_id,
        output_released_on=today(),
        production_input_verified_on=today(),
        safety_case_doc_id=safety_case_doc_id,
    )
    return db.fetch("design", design["id"])


def assert_ready_for_delivery(db: Database, design_no: str, purpose: str) -> Row:
    """인도 전 설계 유효성확인 완료를 확인한다 (8.3.4.4 b, CTL-010)."""
    design = db.require("design", design_no=design_no)
    enforce(
        "CTL-010",
        bool(design["validated_on"]) or bool(design["validation_waiver_agreed_on"]),
        f"{purpose}: 설계 {design_no} 의 유효성확인이 완료되지 않았고 고객 합의 관리계획도"
        " 없습니다(8.3.4.4 b).",
        db=db,
        context=purpose,
    )
    return design


def unreleased_verified_designs(db: Database) -> list[Row]:
    """검증은 되었으나 출시되지 않은 설계."""
    return db.query(
        "SELECT * FROM design WHERE verified_on IS NOT NULL AND output_released_on IS NULL"
    )
