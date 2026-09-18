"""강제 통제(invariant) 테스트.

각 테스트는 ISO 22163 요구사항을 위반하는 업무 처리를 시도하고, 시스템이 이를
거부하며 올바른 통제 ID 와 근거 조항을 보고하는지 확인한다.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from rqms.db import open_database, today
from rqms.errors import ControlViolation
from rqms.seed import PRODUCT, build
from rqms.services import (
    audit,
    calibration,
    capa,
    change,
    competence,
    configuration,
    design,
    documents,
    governance,
    indicators,
    nonconformity,
    production,
    projects,
    rams,
    release,
    requirements,
    special_processes,
    suppliers,
    tender,
    transfer,
)
from rqms.services._base import add_months

YEAR = int(today()[:4])


class SeededCase(unittest.TestCase):
    """적합한 상태로 구축된 RQMS 를 각 테스트가 독립적으로 받는다."""

    _template: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = tempfile.TemporaryDirectory()
        cls._template = Path(cls._dir.name) / "template.db"
        db = open_database(cls._template, create=True)
        build(db)
        db.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dir.cleanup()

    def setUp(self) -> None:
        self._work_dir = tempfile.TemporaryDirectory()
        self._work = Path(self._work_dir.name) / "work.db"
        shutil.copy(self._template, self._work)
        self.db = open_database(self._work)

    def tearDown(self) -> None:
        self.db.close()
        self._work_dir.cleanup()

    # ------------------------------------------------------------------ 헬퍼
    def person(self, name: str) -> int:
        return int(self.db.require("person", name=name)["id"])

    def approved_doc(self, doc_no: str | None = None) -> int:
        if doc_no:
            return int(self.db.require("document", doc_no=doc_no, status="approved")["id"])
        row = self.db.one("SELECT id FROM document WHERE status = 'approved' LIMIT 1")
        assert row is not None
        return int(row["id"])

    def assertViolates(self, control_id: str, clause: str | None = None):
        """통제 위반을 기대하는 컨텍스트 매니저."""
        case = self

        class _Ctx:
            def __enter__(self) -> _Ctx:
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                case.assertIsNotNone(
                    exc, f"{control_id} 위반이 거부되지 않았습니다."
                )
                case.assertIsInstance(exc, ControlViolation)
                case.assertEqual(exc.control_id, control_id, str(exc))
                if clause is not None:
                    case.assertIn(clause, exc.clauses, str(exc))
                return True

        return _Ctx()


# ------------------------------------------------------- 7.5 문서화된 정보
class DocumentControlTest(SeededCase):
    def test_ctl001_cannot_approve_without_review(self) -> None:
        doc_id = documents.create(
            self.db,
            doc_no="T-001",
            title="검토 없이 승인 시도",
            doc_type="procedure",
            version="1.0",
            author_id=self.person("박검사"),
        )
        with self.assertViolates("CTL-001", "7.5.2"):
            documents.approve(self.db, doc_id, self.person("김대표"))

    def test_ctl001_author_cannot_approve(self) -> None:
        author = self.person("박검사")
        doc_id = documents.create(
            self.db,
            doc_no="T-002",
            title="작성자 자가 승인 시도",
            doc_type="procedure",
            version="1.0",
            author_id=author,
        )
        documents.submit_for_review(self.db, doc_id, self.person("이품질"))
        with self.assertViolates("CTL-001"):
            documents.approve(self.db, doc_id, author)

    def test_ctl001_unapproved_document_cannot_be_used(self) -> None:
        doc_id = documents.create(
            self.db,
            doc_no="T-003",
            title="미승인 생산데이터",
            doc_type="instruction",
            version="1.0",
            author_id=self.person("강생산"),
        )
        with self.assertViolates("CTL-001"):
            documents.assert_usable(self.db, doc_id, "생산 착수")

    def test_ctl002_tampered_document_is_detected(self) -> None:
        doc_id = self.approved_doc("RQMS-ITP-001")
        self.db.update("document", doc_id, content="승인 후 무단 변경된 내용")
        with self.assertViolates("CTL-002", "7.5.3.2"):
            documents.assert_usable(self.db, doc_id, "검사 수행")
        self.assertEqual(len(documents.broken_seals(self.db)), 1)

    def test_ctl003_record_needs_retention_period(self) -> None:
        with self.assertViolates("CTL-003", "7.5.3.3"):
            documents.create(
                self.db,
                doc_no="T-004",
                title="보존기간 없는 기록",
                doc_type="record",
                version="1.0",
                author_id=self.person("박검사"),
            )

    def test_ctl003_cannot_dispose_before_retention_expiry(self) -> None:
        doc_id = self.approved_doc("RQMS-MR-001")  # 보존 120개월
        with self.assertViolates("CTL-003"):
            documents.dispose(self.db, doc_id, self.person("이품질"))


# ---------------------------------------------------------- 8.1.3 프로젝트
class ProjectControlTest(SeededCase):
    PROJECT = f"PRJ-{YEAR}-001"

    def test_ctl004_gate_blocked_by_open_issue(self) -> None:
        projects.plan_phase_review(
            self.db,
            project_code=self.PROJECT,
            phase="design",
            planned_on=today(),
            mandatory_participants="pm,qm,eng",
        )
        projects.raise_open_issue(
            self.db,
            project_code=self.PROJECT,
            description="인터페이스 시험 미완료",
            owner_id=self.person("한설계"),
            due_on=add_months(today(), 1),
            phase="planning",
        )
        with self.assertViolates("CTL-004", "8.1.3.1.3"):
            projects.hold_phase_review(
                self.db,
                project_code=self.PROJECT,
                phase="design",
                decision="accepted",
                actual_participants="pm,qm,eng",
            )

    def test_ctl004_top_management_override_allows_gate(self) -> None:
        projects.plan_phase_review(
            self.db,
            project_code=self.PROJECT,
            phase="design",
            planned_on=today(),
            mandatory_participants="pm,qm,eng",
        )
        projects.raise_open_issue(
            self.db,
            project_code=self.PROJECT,
            description="인터페이스 시험 미완료",
            owner_id=self.person("한설계"),
            due_on=add_months(today(), 1),
            phase="planning",
        )
        review = projects.hold_phase_review(
            self.db,
            project_code=self.PROJECT,
            phase="design",
            decision="conditional",
            actual_participants="pm,qm,eng",
            top_management_override_by=self.person("김대표"),
        )
        self.assertEqual(review["decision"], "conditional")
        self.assertIsNotNone(review["top_management_override_by"])

    def test_ctl004_mandatory_participant_absence_blocks_gate(self) -> None:
        projects.plan_phase_review(
            self.db,
            project_code=self.PROJECT,
            phase="design",
            planned_on=today(),
            mandatory_participants="pm,qm,eng",
        )
        with self.assertViolates("CTL-004"):
            projects.hold_phase_review(
                self.db,
                project_code=self.PROJECT,
                phase="design",
                decision="accepted",
                actual_participants="pm,qm",
            )

    def test_ctl005_budget_increase_requires_approved_change(self) -> None:
        with self.assertViolates("CTL-005", "8.1.3.5"):
            projects.increase_budget(
                self.db, project_code=self.PROJECT, new_budget=50_000_000_000
            )

    def test_ctl005_scope_change_requires_approved_change(self) -> None:
        with self.assertViolates("CTL-005"):
            projects.change_scope(
                self.db, project_code=self.PROJECT, note="차량 개조 범위 추가"
            )

    def test_ctl004_cannot_close_project_with_open_issues(self) -> None:
        projects.raise_open_issue(
            self.db,
            project_code=self.PROJECT,
            description="보증 잔여 이슈",
            owner_id=self.person("최프로"),
            due_on=add_months(today(), 1),
        )
        with self.assertViolates("CTL-004"):
            projects.close(self.db, self.PROJECT, actual_margin_pct=8.1)


# -------------------------------------------- 8.1.4 형상관리 / 변경관리
class ChangeControlTest(SeededCase):
    PROJECT = f"PRJ-{YEAR}-001"

    def test_ctl006_frozen_baseline_needs_approved_change(self) -> None:
        with self.assertViolates("CTL-006", "8.1.4.1.1"):
            configuration.revise_item_in_baseline(
                self.db,
                project_code=self.PROJECT,
                baseline_name="BL-AS-DESIGNED-1.0",
                part_no="HR-DR-DRIVE",
                new_revision="C",
            )

    def test_ctl007_safety_item_needs_traceability_method(self) -> None:
        with self.assertViolates("CTL-007"):
            configuration.add_item(
                self.db,
                project_code=self.PROJECT,
                part_no="HR-DR-BRAKE",
                name="제동 연동 모듈",
                parent_part_no="HR-DOOR-2000",
                safety_related=True,
                traceability_method="",
            )

    def test_ctl027_cannot_implement_before_approval(self) -> None:
        change.raise_change(
            self.db,
            change_no="CR-T01",
            scope="design",
            target_ref="HR-DR-PANEL",
            description="패널 두께 변경",
        )
        with self.assertViolates("CTL-027", "8.1.4.2"):
            change.implement(self.db, "CR-T01")

    def test_ctl027_approval_requires_impact_analysis(self) -> None:
        change.raise_change(
            self.db,
            change_no="CR-T02",
            scope="design",
            target_ref="HR-DR-PANEL",
            description="패널 두께 변경",
        )
        with self.assertViolates("CTL-027"):
            change.approve(self.db, "CR-T02", approver_id=self.person("김대표"))

    def test_ctl028_customer_impact_requires_agreement(self) -> None:
        change.raise_change(
            self.db,
            change_no="CR-T03",
            scope="requirement",
            target_ref="F-01",
            description="개폐시간 요구 완화",
            customer_impact=True,
        )
        change.analyse_impact(
            self.db,
            "CR-T03",
            impact_analysis="고객 규격 변경 필요",
            proposal_verified=True,
        )
        with self.assertViolates("CTL-028", "8.1.4.2"):
            change.approve(self.db, "CR-T03", approver_id=self.person("김대표"))


# --------------------------------------------------- 8.1.2 / 8.2 요구사항
class RequirementControlTest(SeededCase):
    def test_ctl008_tender_review_requires_clause_by_clause(self) -> None:
        tender.open_tender(
            self.db, tender_no="TDR-T01", customer="△△운영기관", title="예비 입찰"
        )
        requirements.register(
            self.db,
            req_no="TDR-T01-F-01",
            owner_scope="tender",
            owner_ref="TDR-T01",
            req_type="functional",
            text="비상 개방 기능",
            source="customer",
        )
        with self.assertViolates("CTL-008", "8.2.5"):
            tender.complete_review(
                self.db,
                "TDR-T01",
                control_extent="A",
                risk_entry_ref="R-1",
                monetary_risk_eval="1억",
                knowledge_input="교훈 반영",
                deliverable_cost_plan="10억",
                resource_plan="10명",
            )

    def test_ctl008_cannot_submit_unapproved_tender(self) -> None:
        tender.open_tender(
            self.db, tender_no="TDR-T02", customer="△△운영기관", title="예비 입찰"
        )
        with self.assertViolates("CTL-008"):
            tender.submit(self.db, "TDR-T02")

    def test_ctl008_technical_requirement_needs_vv_method(self) -> None:
        req_id = requirements.register(
            self.db,
            req_no="PRD-T-P-01",
            owner_scope="product",
            owner_ref="TEST-PRODUCT",
            req_type="performance",
            text="개폐시간 2.5초 이내",
            source="customer",
        )
        with self.assertViolates("CTL-008"):
            requirements.review_clause_by_clause(
                self.db,
                req_id,
                result="충족 가능",
                risk_assessed=True,
                verifiable=True,
                cascaded=True,
                verification_method="",
                validation_method="",
            )

    def test_ctl046_specification_needs_all_categories(self) -> None:
        for suffix, req_type in (("F-01", "functional"), ("N-01", "non_functional")):
            req_id = requirements.register(
                self.db,
                req_no=f"PART-{suffix}",
                owner_scope="product",
                owner_ref="PARTIAL-PRODUCT",
                req_type=req_type,
                text="부분 요구사항",
                source="customer",
            )
            requirements.review_clause_by_clause(
                self.db,
                req_id,
                result="충족",
                risk_assessed=True,
                verifiable=True,
                cascaded=True,
                verification_method="해석",
                validation_method="형식시험",
            )
        with self.assertViolates("CTL-046", "8.2.2.1.1"):
            requirements.document_specification(
                self.db,
                owner_scope="product",
                owner_ref="PARTIAL-PRODUCT",
                doc_id=self.approved_doc("RQMS-SPEC-PRODUCT-001"),
            )


# ------------------------------------------------------- 8.3 설계 및 개발
class DesignControlTest(SeededCase):
    def test_ctl060_unresolved_input_conflicts_rejected(self) -> None:
        design.create(
            self.db,
            design_no="DSN-T01",
            item="시험용 서브시스템",
            architecture_level="subsystem",
        )
        with self.assertViolates("CTL-060", "8.3.3"):
            design.confirm_inputs(self.db, "DSN-T01", conflicts_resolved=False)

    def test_ctl057_safety_design_needs_standard(self) -> None:
        with self.assertViolates("CTL-057"):
            design.create(
                self.db,
                design_no="DSN-T02",
                item="안전관련 제어 모듈",
                safety_related=True,
                safety_standard="",
            )

    def test_ctl058_design_review_requires_decision_authority(self) -> None:
        design.create(self.db, design_no="DSN-T03", item="시험용 모듈")
        with self.assertViolates("CTL-058", "8.3.4.2"):
            design.hold_design_review(
                self.db,
                design_no="DSN-T03",
                level="component",
                acceptance_criteria="체크리스트 충족",
                mandatory_participants="eng,qm",
                actual_participants="eng,qm",
                decision="accepted",
                decision_authority_present=False,
            )

    def test_ctl047_test_plan_requires_all_items(self) -> None:
        design.create(self.db, design_no="DSN-T04", item="시험용 모듈")
        project_id = int(self.db.require("project", code=f"PRJ-{YEAR}-001")["id"])
        baseline_id = int(
            self.db.require("baseline", project_id=project_id, name="BL-AS-BUILT-1.0")["id"]
        )
        with self.assertViolates("CTL-047", "8.3.4.5"):
            design.plan_test(
                self.db,
                design_no="DSN-T04",
                kind="verification",
                plan_doc_id=self.approved_doc("RQMS-TP-001"),
                objectives="내구 확인",
                conditions="",
                product_under_test="시작품",
                resources="내구시험기",
                acceptance_criteria="100만회",
                recorded_parameters="구동전류",
                method="절차 준수",
                baseline_id=baseline_id,
            )

    def test_ctl009_outputs_cannot_be_released_before_verification(self) -> None:
        design.create(self.db, design_no="DSN-T05", item="시험용 모듈")
        with self.assertViolates("CTL-009", "8.3.5.1.1"):
            design.release_outputs(
                self.db,
                "DSN-T05",
                approver_id=self.person("한설계"),
                production_input_verified=True,
                application_doc_id=self.approved_doc("RQMS-DND-OUT-001"),
            )

    def test_ctl010_delivery_requires_validation(self) -> None:
        design.create(self.db, design_no="DSN-T06", item="시험용 모듈")
        with self.assertViolates("CTL-010", "8.3.4.4"):
            design.assert_ready_for_delivery(self.db, "DSN-T06", "인도")


# ------------------------------------------------------- 8.4 외부공급 관리
class SupplierControlTest(SeededCase):
    def _full_requirements(self) -> dict[str, str]:
        return {k: "전달" for k in suppliers.REQUIRED_COMMUNICATION}

    def test_ctl011_unapproved_supplier_cannot_receive_order(self) -> None:
        suppliers.register(self.db, code="SUP-NEW", name="신규협력사")
        with self.assertViolates("CTL-011", "8.4.1.1.4"):
            suppliers.issue_purchase_order(
                self.db,
                po_no="PO-T01",
                supplier_code="SUP-NEW",
                item="시험 부품",
                qty=10,
                required_on=add_months(today(), 2),
                requirements_communicated=self._full_requirements(),
            )

    def test_ctl048_approval_requires_classification_and_evaluation(self) -> None:
        suppliers.register(self.db, code="SUP-NEW2", name="신규협력사2")
        with self.assertViolates("CTL-048"):
            suppliers.approve(
                self.db,
                "SUP-NEW2",
                approver_id=self.person("서구매"),
                approval_scope="시험 부품",
            )

    def test_ctl049_order_requires_all_communicated_requirements(self) -> None:
        partial = self._full_requirements()
        partial.pop("right_of_access")
        with self.assertViolates("CTL-049", "8.4.3.1"):
            suppliers.issue_purchase_order(
                self.db,
                po_no="PO-T02",
                supplier_code="SUP-ELEC",
                item="제어 보드",
                qty=10,
                required_on=add_months(today(), 2),
                requirements_communicated=partial,
            )

    def test_ctl012_unverified_eppps_cannot_be_used(self) -> None:
        suppliers.issue_purchase_order(
            self.db,
            po_no="PO-T03",
            supplier_code="SUP-MECH",
            item="가이드 레일 추가분",
            qty=100,
            required_on=add_months(today(), 2),
            requirements_communicated=self._full_requirements(),
        )
        with self.assertViolates("CTL-012", "8.4.2.2"):
            suppliers.assert_verified_for_use(self.db, "PO-T03", "제조 투입")

    def test_ctl013_delegation_requires_supplier_acceptance(self) -> None:
        with self.assertViolates("CTL-013"):
            suppliers.delegate_verification(
                self.db,
                supplier_code="SUP-MECH",
                scope="출하검사",
                requirements_text="전수 검사",
                supplier_acceptance_evidence="",
                control_measure="연 1회 심사",
            )

    def test_ctl016_eppps_release_requires_approved_fai(self) -> None:
        suppliers.issue_purchase_order(
            self.db,
            po_no="PO-T04",
            supplier_code="SUP-ELEC",
            item="신규 센서",
            qty=50,
            required_on=add_months(today(), 3),
            requirements_communicated=self._full_requirements(),
            is_new_or_modified=True,
        )
        with self.assertViolates("CTL-016", "8.4.2.1.1"):
            suppliers.approve_release(
                self.db,
                po_no="PO-T04",
                approval_method="FAI",
                fai_id=None,
                validated_before_first_use=True,
                baseline_id=None,
                approver_id=self.person("이품질"),
            )


# ------------------------------------------------- 8.5 생산 / 8.6 출하
class ProductionControlTest(SeededCase):
    def test_ctl014_unqualified_operator_cannot_run_special_process(self) -> None:
        with self.assertViolates("CTL-014", "8.5.1.3"):
            special_processes.assert_executable(
                self.db,
                "SP-CRIMP",
                operator_id=self.person("박검사"),
                purpose="압착 작업",
            )

    def test_ctl014_expired_process_qualification_blocks_execution(self) -> None:
        self.db.execute(
            "UPDATE special_process SET qualification_valid_until = ? WHERE code = 'SP-WELD'",
            ("2020-01-01",),
        )
        with self.assertViolates("CTL-014"):
            special_processes.assert_executable(
                self.db, "SP-WELD", operator_id=self.person("윤용접"), purpose="용접"
            )

    def test_ctl050_production_order_requires_risk_assessment(self) -> None:
        with self.assertViolates("CTL-050", "8.5.1.1.2"):
            production.create_order(
                self.db,
                order_no="PO-PRD-T01",
                item="시험 생산",
                qty=1,
                approved_data_doc_id=self.approved_doc("RQMS-PRD-DATA-001"),
                itp_doc_id=self.approved_doc("RQMS-ITP-001"),
                risk_assessment="",
                tool_program_list="지그",
            )

    def test_ctl016_serial_release_requires_fai(self) -> None:
        production.create_order(
            self.db,
            order_no="PO-PRD-T02",
            item="시험 생산",
            qty=1,
            approved_data_doc_id=self.approved_doc("RQMS-PRD-DATA-001"),
            itp_doc_id=self.approved_doc("RQMS-ITP-001"),
            risk_assessment="공정 FMEA 완료",
            tool_program_list="지그",
        )
        with self.assertViolates("CTL-016", "8.9.3"):
            production.release_serial_production(self.db, "PO-PRD-T02")

    def test_ctl025_overdue_measuring_resource_cannot_be_used(self) -> None:
        resource_id = int(self.db.require("measuring_resource", ident="MR-001")["id"])
        self.db.update("measuring_resource", resource_id, next_due_on="2020-01-01")
        with self.assertViolates("CTL-025", "7.1.5.2"):
            calibration.assert_usable(self.db, resource_id, "최종검사")

    def test_ctl025_unfit_resource_cannot_be_used(self) -> None:
        resource_id = int(self.db.require("measuring_resource", ident="MR-002")["id"])
        calibration.record_calibration(
            self.db,
            resource_id=resource_id,
            result="fail",
            reference_standard="표준기",
            procedure_ref="RQMS-INS-CAL-01",
        )
        with self.assertViolates("CTL-025"):
            calibration.assert_usable(self.db, resource_id, "토크 확인")

    def test_ctl015_unknown_item_is_treated_as_nonconforming(self) -> None:
        item_id = int(self.db.require("traceable_item", serial_no="HRD-0002")["id"])
        self.db.update("traceable_item", item_id, status="unknown")
        with self.assertViolates("CTL-015", "8.5.2.1"):
            nonconformity.assert_item_identified(self.db, "HRD-0002", "출하")

    def test_ctl017_release_blocked_without_completed_inspection(self) -> None:
        production.create_item(
            self.db,
            serial_no="HRD-T001",
            order_no="PO-PRD-0001",
            identification_method="2D 코드",
            warranty_months=24,
        )
        production.record_inspection(
            self.db,
            order_no="PO-PRD-0001",
            serial_no="HRD-T001",
            itp_step="최종검사-기능시험",
            acceptance_criteria="개폐시간 ≤ 3.0초",
            result="fail",
            actual_data="개폐시간 3.4초",
            inspector_id=self.person("박검사"),
        )
        with self.assertViolates("CTL-017", "8.6"):
            release.release_item(
                self.db,
                serial_no="HRD-T001",
                authorized_by_id=self.person("이품질"),
                conformity_evidence="검사 미완료",
            )

    def test_ctl051_equipment_requires_validation_before_use(self) -> None:
        production.register_equipment(
            self.db,
            ident="EQ-T01",
            name="시험 지그",
            acceptance_criteria="±0.05mm",
            preventive_plan="월간 점검",
        )
        with self.assertViolates("CTL-051", "8.5.1.4.1"):
            production.assert_equipment_usable(self.db, "EQ-T01", "조립")


# ----------------------------------------------- 8.7 부적합 / 10.2 시정조치
class NonconformityControlTest(SeededCase):
    def _raise_nc(self, nc_no: str, **kwargs: object) -> None:
        nonconformity.raise_nonconformity(
            self.db,
            nc_no=nc_no,
            source=str(kwargs.pop("source", "internal")),
            description="시험용 부적합",
            qty=1,
            **kwargs,  # type: ignore[arg-type]
        )

    def test_ctl018_expired_concession_cannot_be_used(self) -> None:
        self._raise_nc("NC-T01")
        concession_id = nonconformity.raise_concession(
            self.db,
            concession_no="CON-T01",
            kind="internal",
            nc_no="NC-T01",
            description="경미한 외관 이탈",
            qty_authorized=5,
            valid_until=add_months(today(), 1),
            customer_approval_required=False,
        )
        nonconformity.approve_concession_internally(
            self.db, "CON-T01", approver_id=self.person("이품질")
        )
        self.db.update("concession", concession_id, valid_until="2020-01-01")
        with self.assertViolates("CTL-018", "8.7.3"):
            nonconformity.assert_concession_valid(
                self.db, concession_id, qty=1, purpose="출하"
            )

    def test_ctl018_quantity_limit_enforced(self) -> None:
        self._raise_nc("NC-T02")
        concession_id = nonconformity.raise_concession(
            self.db,
            concession_no="CON-T02",
            kind="internal",
            nc_no="NC-T02",
            description="경미한 외관 이탈",
            qty_authorized=2,
            valid_until=add_months(today(), 2),
            customer_approval_required=False,
        )
        nonconformity.approve_concession_internally(
            self.db, "CON-T02", approver_id=self.person("이품질")
        )
        nonconformity.consume_concession(self.db, concession_id, qty=2, purpose="출하")
        with self.assertViolates("CTL-018"):
            nonconformity.consume_concession(
                self.db, concession_id, qty=1, purpose="추가 출하"
            )

    def test_ctl019_customer_concession_requires_customer_approval(self) -> None:
        self._raise_nc("NC-T03")
        concession_id = nonconformity.raise_concession(
            self.db,
            concession_no="CON-T03",
            kind="customer",
            nc_no="NC-T03",
            description="색차 이탈",
            qty_authorized=1,
            valid_until=add_months(today(), 2),
            customer_approval_required=True,
            identification_agreed=True,
            recorded_on_doc="DOC-T-001",
        )
        nonconformity.approve_concession_internally(
            self.db, "CON-T03", approver_id=self.person("이품질")
        )
        with self.assertViolates("CTL-019", "8.7.3"):
            nonconformity.assert_concession_valid(
                self.db, concession_id, qty=1, purpose="인도"
            )

    def test_ctl019_provider_concession_needs_internal_approval_first(self) -> None:
        self._raise_nc("NC-T04", source="external_provider")
        nonconformity.raise_concession(
            self.db,
            concession_no="CON-T04",
            kind="external_provider",
            nc_no="NC-T04",
            description="공급자 특채",
            qty_authorized=1,
            valid_until=add_months(today(), 2),
            customer_approval_required=True,
            identification_agreed=True,
            recorded_on_doc="DOC-T-002",
        )
        with self.assertViolates("CTL-019"):
            nonconformity.approve_concession_by_customer(self.db, "CON-T04")

    def test_ctl033_cannot_close_nc_without_capa_evaluation(self) -> None:
        self._raise_nc("NC-T05")
        with self.assertViolates("CTL-033", "10.2.3"):
            nonconformity.close(self.db, "NC-T05")

    def test_ctl033_nc_requiring_capa_needs_linked_capa(self) -> None:
        self._raise_nc("NC-T06", source="customer")
        nonconformity.evaluate_capa_need(self.db, "NC-T06")
        with self.assertViolates("CTL-033"):
            nonconformity.close(self.db, "NC-T06")

    def test_ctl033_ineffective_capa_cannot_be_closed(self) -> None:
        capa.open_capa(
            self.db,
            capa_no="CAPA-T01",
            source_type="nonconformity",
            source_ref="NC-T07",
            description="시험용 시정조치",
            criteria_applied="반복 발생",
            method="8D",
            owner_id=self.person("강생산"),
            due_on=add_months(today(), 1),
        )
        capa.record_analysis(
            self.db,
            "CAPA-T01",
            root_cause="지그 마모",
            actions="지그 교체",
            similar_checked=True,
        )
        with self.assertViolates("CTL-033", "10.2.1"):
            capa.close_capa(
                self.db, "CAPA-T01", effective=False, evidence="재발 지속"
            )

    def test_safety_nc_escalates_to_top_management(self) -> None:
        """10.2.3 e) — 안전영향 부적합은 최고경영자 단계로 에스컬레이션된다."""
        nonconformity.raise_nonconformity(
            self.db,
            nc_no="NC-T08",
            source="customer",
            description="안전기능 영향 의심",
            qty=1,
            safety_impact=True,
        )
        decision = nonconformity.evaluate_capa_need(self.db, "NC-T08")
        self.assertTrue(decision["capa_needed"])
        self.assertEqual(decision["escalation_level"], 3)
        self.assertIn("safety_impact", decision["criteria"])


# --------------------------------------------- 8.8 RAMS / 8.10 단산 / 8.1.1.2
class RamsAndTransferControlTest(SeededCase):
    def test_ctl029_unmet_ram_objective_requires_capa(self) -> None:
        objective_id = rams.set_objective(
            self.db,
            product=PRODUCT,
            metric="availability",
            target=99.5,
            unit="%",
            period="2026-10",
            applicable_standard="IEC 62278",
            calculated=99.7,
        )
        with self.assertViolates("CTL-029", "8.8.2"):
            rams.evaluate_objective(
                self.db,
                objective_id,
                field_value=98.9,
                analysis="가용성 목표 미달",
                feedback_to_design="설계 개선 검토",
            )

    def test_ctl057_safety_case_requires_recognised_standard(self) -> None:
        with self.assertViolates("CTL-057", "8.8.3"):
            rams.record_safety_case(
                self.db,
                product="시험 제품",
                applicable_standards="사내 기준서만 적용",
                safety_case_doc_id=self.approved_doc("RQMS-SAF-CASE-001"),
                hazard_log="위험원 3건",
            )

    def test_ctl035_transfer_approval_requires_fai(self) -> None:
        transfer.plan(
            self.db,
            transfer_no="TRF-T01",
            process_code="PSP",
            from_site="본사",
            to_site="제2공장",
            external=False,
            feasibility_study="타당성 확인",
            risk_entry_ref="R-PRC-001",
            action_plan="설비 이설",
        )
        with self.assertViolates("CTL-035", "8.1.1.2"):
            transfer.approve(self.db, "TRF-T01")

    def test_ctl035_transfer_plan_requires_feasibility_and_risk(self) -> None:
        with self.assertViolates("CTL-035"):
            transfer.plan(
                self.db,
                transfer_no="TRF-T02",
                process_code="PSP",
                from_site="본사",
                to_site="제2공장",
                external=False,
                feasibility_study="",
                risk_entry_ref="",
                action_plan="",
            )


# --------------------------------------------- 7.2 역량 / 9.1 지표 / 9.2 심사
class SupportAndEvaluationControlTest(SeededCase):
    def test_ctl026_assignment_blocked_by_competence_gap(self) -> None:
        with self.assertViolates("CTL-026", "7.2"):
            competence.assign_task(
                self.db, person_id=self.person("박검사"), task_code="welding"
            )
        gaps = competence.open_gaps(self.db)
        self.assertTrue(any(g["competence_code"] == "welding_qualification" for g in gaps))

    def test_ctl026_expired_competence_blocks_work(self) -> None:
        row = self.db.require(
            "competence",
            person_id=self.person("윤용접"),
            competence_code="welding_qualification",
        )
        self.db.update("competence", int(row["id"]), valid_until="2020-01-01")
        with self.assertViolates("CTL-026"):
            competence.assert_competent(
                self.db, self.person("윤용접"), "welding", "용접 작업"
            )

    def test_ctl020_unmet_kpi_requires_capa(self) -> None:
        with self.assertViolates("CTL-020", "9.1.3.1"):
            indicators.record_measurement(
                self.db,
                indicator_code="PI-COTD",
                period="2026-10",
                value=80.0,
                analysis="공급자 지연으로 납기 미달",
                trend="악화",
                shared_with="최고경영자",
            )

    def test_ctl020_analysis_must_be_shared(self) -> None:
        with self.assertViolates("CTL-020"):
            indicators.record_measurement(
                self.db,
                indicator_code="PI-INC",
                period="2026-10",
                value=99.0,
                analysis="목표 충족",
                trend="개선",
                shared_with="",
            )

    def test_ctl022_auditor_cannot_audit_own_process(self) -> None:
        with self.assertViolates("CTL-022", "9.2.3.2"):
            audit.plan_audit(
                self.db,
                audit_no="IA-T01",
                year=YEAR,
                scope="생산 프로세스",
                criteria="ISO 22163 8.5",
                planned_on=today(),
                lead_auditor_id=self.person("감사일"),  # home: PSP,SPP,NCO,REL
                process_code="PSP",
            )

    def test_ctl055_auditor_needs_experience(self) -> None:
        audit.register_auditor(
            self.db,
            person_id=self.person("정시험"),
            knows_audit_principles=True,
            scope_knowledge="시험",
            clause_knowledge="8.3",
            criteria_knowledge="사내 절차",
            audits_performed=0,
            home_processes="",
            refresh_training_on=today(),
        )
        with self.assertViolates("CTL-055", "9.2.3.3.1"):
            audit.plan_audit(
                self.db,
                audit_no="IA-T02",
                year=YEAR,
                scope="설계 프로세스",
                criteria="ISO 22163 8.3",
                planned_on=today(),
                lead_auditor_id=self.person("정시험"),
                process_code="DND",
            )

    def test_ctl055_auditor_registration_requires_knowledge(self) -> None:
        with self.assertViolates("CTL-055"):
            audit.register_auditor(
                self.db,
                person_id=self.person("오구조"),
                knows_audit_principles=False,
                scope_knowledge="",
                clause_knowledge="",
                criteria_knowledge="",
                audits_performed=3,
                home_processes="DND",
            )

    def test_ctl021_audit_finding_requires_capa(self) -> None:
        with self.assertViolates("CTL-021", "9.2.3.1"):
            audit.record_finding(
                self.db,
                audit_no=f"IA-{YEAR}-PSP",
                clause_id="8.5.1.1.2",
                grade="major",
                description="승인된 생산데이터 미비",
            )


# ------------------------------------------------------- 4장·5장·6장 거버넌스
class GovernanceControlTest(SeededCase):
    def test_ctl040_policy_requires_all_topics(self) -> None:
        with self.assertViolates("CTL-040", "5.2.3"):
            governance.record_quality_policy(
                self.db,
                year=YEAR + 1,
                doc_id=self.approved_doc("RQMS-POL-001"),
                topics={
                    "failure_prevention": "예방 활동",
                    "customer_expectations": "고객 기대",
                },
            )

    def test_ctl037_mandatory_process_cannot_be_excluded(self) -> None:
        with self.assertViolates("CTL-037", "4.3"):
            governance.exclude_process(self.db, code="FAI", reason="해당 없음")

    def test_ctl037_exclusion_requires_justification(self) -> None:
        with self.assertViolates("CTL-037"):
            governance.record_scope(
                self.db,
                year=YEAR + 1,
                doc_id=self.approved_doc("RQMS-MAN-001"),
                products_services="출입문 시스템",
                exclusions={"8.8.4": ""},
            )

    def test_ctl031_stop_authority_must_be_independent(self) -> None:
        with self.assertViolates("CTL-031", "5.3.1"):
            governance.appoint_stop_authority(
                self.db,
                person_id=self.person("강생산"),
                scope="생산",
                independent_of="생산",
            )

    def test_ctl038_process_description_requires_all_fields(self) -> None:
        with self.assertViolates("CTL-038", "4.4.3"):
            governance.register_process(
                self.db,
                code="ROM",
                owner_id=self.person("이품질"),
                description_doc=self.approved_doc("RQMS-PRC-ROM"),
                inputs="입력",
                outputs="",
                sequence_note="순서",
                criteria="기준",
                resources="자원",
                risk_criteria="FMEA",
            )

    def test_ctl043_objective_requires_achievement_plan(self) -> None:
        with self.assertViolates("CTL-043", "6.2.2"):
            governance.set_quality_objective(
                self.db,
                code="QO-T01",
                description="시험 목표",
                level="organization",
                target_value=90.0,
                unit="%",
                responsible_id=self.person("이품질"),
                due_on="",
                resources="",
                evaluation_method="",
            )

    def test_ctl042_high_risk_requires_action_owner(self) -> None:
        from rqms.services import risk

        with self.assertViolates("CTL-042", "6.1.3.1"):
            risk.register(
                self.db,
                ref_no="R-T01",
                kind="risk",
                scope="organization",
                description="고등급 리스크",
                likelihood=4,
                impact=4,
            )

    def test_ctl034_continuity_plan_requires_all_topics(self) -> None:
        from rqms.services import risk

        with self.assertViolates("CTL-034", "6.1.4"):
            risk.record_continuity_plan(
                self.db,
                year=YEAR + 1,
                doc_id=self.approved_doc("RQMS-BCP-001"),
                topics={"interruptions": "대체 라인"},
                responsibilities="위기관리위원회",
            )


class ViolationLoggingTest(SeededCase):
    def test_violations_are_logged_as_failure_data(self) -> None:
        """9.1.1.1.1 — 내·외부 실패 데이터 수집을 위해 통제 위반이 기록된다."""
        before = self.db.count("SELECT COUNT(*) FROM control_violation_log")
        with self.assertViolates("CTL-011"):
            suppliers.register(self.db, code="SUP-LOG", name="미승인사")
            suppliers.issue_purchase_order(
                self.db,
                po_no="PO-LOG",
                supplier_code="SUP-LOG",
                item="부품",
                qty=1,
                required_on=add_months(today(), 1),
                requirements_communicated={
                    k: "전달" for k in suppliers.REQUIRED_COMMUNICATION
                },
            )
        after = self.db.count("SELECT COUNT(*) FROM control_violation_log")
        self.assertEqual(after, before + 1)
        row = self.db.one(
            "SELECT * FROM control_violation_log ORDER BY id DESC LIMIT 1"
        )
        assert row is not None
        self.assertEqual(row["control_id"], "CTL-011")
        self.assertIn("8.4.1.1.4", row["clauses"])


if __name__ == "__main__":
    unittest.main()
