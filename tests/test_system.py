"""시스템 수준 테스트 — 적합성, 문서 동기, CLI, 보고서."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from rqms import checks, cli, report
from rqms.conformity import (
    assess,
    control_matrix,
    gap_report,
    process_matrix,
    traceability_matrix,
)
from rqms.db import Database, open_database
from rqms.seed import build
from rqms.standard import load_registry

ROOT = Path(__file__).resolve().parent.parent


class EmptySystemTest(unittest.TestCase):
    """아무것도 구축하지 않은 시스템은 갭을 보고해야 한다 — 보고서가 무의미하지 않음을 확인."""

    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.db.init_schema()

    def tearDown(self) -> None:
        self.db.close()

    def test_empty_system_reports_gaps(self) -> None:
        result = assess(self.db)
        self.assertGreater(len(result.gaps), 0)
        self.assertLess(result.rate(), 100.0)

    def test_empty_system_reports_control_findings(self) -> None:
        findings = checks.run_checks(self.db)
        self.assertGreater(len(findings), 0)
        controls = {f.control_id for f in findings}
        # 아무 근거가 없으면 거버넌스·심사·검토 통제가 모두 위반으로 나와야 한다.
        for expected in ("CTL-021", "CTL-023", "CTL-024", "CTL-036", "CTL-037", "CTL-040"):
            self.assertIn(expected, controls)


class SeededSystemTest(unittest.TestCase):
    """시연 RQMS 는 모든 적용 조항에 대해 적합해야 한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = tempfile.TemporaryDirectory()
        cls.path = Path(cls._dir.name) / "rqms.db"
        cls.db = open_database(cls.path, create=True)
        cls.summary = build(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close()
        cls._dir.cleanup()

    def test_no_conformity_gaps(self) -> None:
        result = assess(self.db)
        detail = "\n".join(
            f"{g['clause']} {g['title']}: 증거 {g['missing_evidence']}"
            f" / 통제 {g['control_findings']}"
            for g in gap_report(self.db)
        )
        self.assertEqual(len(result.gaps), 0, f"\n{detail}")
        self.assertEqual(result.rate(), 100.0)
        self.assertEqual(result.rate(mandatory_only=True), 100.0)

    def test_no_control_findings(self) -> None:
        findings = checks.run_checks(self.db)
        self.assertEqual(
            findings, [], "\n".join(str(f) for f in findings)
        )

    def test_all_mandatory_processes_registered_with_owner(self) -> None:
        for row in process_matrix(self.db):
            if not str(row["obligation"]).startswith("mandatory"):
                continue
            with self.subTest(process=row["code"]):
                self.assertTrue(row["registered"])
                self.assertIsNotNone(row["owner"])
                self.assertIsNotNone(row["last_process_review"])
                self.assertIsNotNone(row["last_internal_audit"])

    def test_every_clause_evidence_present(self) -> None:
        for row in traceability_matrix(self.db):
            for evidence in row["evidence"]:
                with self.subTest(clause=row["clause"], evidence=evidence["key"]):
                    self.assertTrue(evidence["present"])

    def test_registers_are_populated(self) -> None:
        """핵심 등록부가 비어 있지 않다 — 시스템이 실제로 운영되었음을 확인."""
        expected = {
            "document": 50,
            "process_instance": 29,
            "risk_entry": 3,
            "measuring_resource": 3,
            "requirement": 18,
            "project": 1,
            "config_item": 7,
            "baseline": 2,
            "change_request": 2,
            "design": 1,
            "supplier": 2,
            "purchase_order": 2,
            "production_order": 1,
            "traceable_item": 3,
            "nonconformity": 3,
            "concession": 1,
            "capa": 4,
            "fai": 5,
            "internal_audit": 29,
            "process_review": 29,
            "management_review": 2,
        }
        for table, minimum in expected.items():
            with self.subTest(table=table):
                self.assertGreaterEqual(
                    self.db.count(f"SELECT COUNT(*) FROM {table}"), minimum
                )

    def test_three_year_audit_coverage(self) -> None:
        """9.2.3.2 c) — 모든 필수 프로세스가 3년 내 심사되었다."""
        from rqms.services import audit as audit_service

        self.assertEqual(audit_service.coverage_gaps(self.db), [])

    def test_all_kpis_measured(self) -> None:
        """5.3.1 a) KPI 는 모두 측정 기록이 있다."""
        registry = load_registry()
        for kpi in registry.kpis():
            with self.subTest(kpi=kpi.code):
                self.assertIsNotNone(
                    self.db.find("indicator_measurement", indicator_code=kpi.code)
                )

    def test_unmet_indicator_has_linked_capa(self) -> None:
        """9.1.3.1 — 목표 미달 지표에는 시정조치가 연결되어 있다."""
        unmet = self.db.query("SELECT * FROM indicator_measurement WHERE met = 0")
        self.assertTrue(unmet, "시연 데이터는 목표 미달 사례를 1건 이상 포함해야 한다.")
        for row in unmet:
            with self.subTest(indicator=row["indicator_code"]):
                self.assertIsNotNone(row["capa_id"])

    def test_safety_nonconformity_triggered_extraordinary_review(self) -> None:
        """9.3.1.1 — 중대 품질사고 발생 시 추가 경영검토가 실시되었다."""
        safety_ncs = self.db.query("SELECT * FROM nonconformity WHERE safety_impact = 1")
        self.assertTrue(safety_ncs)
        for nc in safety_ncs:
            row = self.db.one(
                "SELECT 1 FROM management_review WHERE review_kind = 'extraordinary' "
                "AND trigger LIKE ?",
                (f"%{nc['nc_no']}%",),
            )
            self.assertIsNotNone(row, f"{nc['nc_no']} 에 대한 추가 경영검토 누락")

    def test_no_control_violations_logged_during_build(self) -> None:
        """시연 데이터 구축 과정에서 통제 위반이 발생하지 않았다."""
        rows = self.db.query(
            "SELECT * FROM control_violation_log WHERE control_id != 'CTL-056'"
        )
        self.assertEqual([dict(r) for r in rows], [])

    def test_control_matrix_has_no_violations(self) -> None:
        for row in control_matrix(self.db):
            with self.subTest(control=row["control"]):
                self.assertEqual(row["violations"], 0)

    def test_report_renders(self) -> None:
        html = report.render(self.db)
        self.assertIn("ISO 22163:2023 철도용 품질경영시스템 적합성 보고서", html)
        self.assertIn("100.0%", html)
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertNotIn("<td class=\"wrap\">", html)  # .wrap 은 페이지 컨테이너 전용
        self.assertGreater(len(html), 50_000)


class CliTest(unittest.TestCase):
    """CLI 종료 코드 및 JSON 출력 검증."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = tempfile.TemporaryDirectory()
        cls.path = Path(cls._dir.name) / "cli.db"
        db = open_database(cls.path, create=True)
        build(db)
        db.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dir.cleanup()

    def run_cli(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main([*args, "--db", str(self.path)])
        return code, buffer.getvalue()

    def test_conformity_exits_zero_when_conformant(self) -> None:
        code, out = self.run_cli("conformity")
        self.assertEqual(code, 0)
        self.assertIn("갭 없음", out)

    def test_conformity_json(self) -> None:
        code, out = self.run_cli("conformity", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["gaps"], 0)
        self.assertEqual(payload["gaps"], [])

    def test_check_exits_zero(self) -> None:
        code, out = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("위반 없음", out)

    def test_matrix_kinds(self) -> None:
        for kind in ("clause", "control", "process"):
            with self.subTest(kind=kind):
                code, out = self.run_cli("matrix", kind, "--json")
                self.assertEqual(code, 0)
                self.assertTrue(json.loads(out))

    def test_clause_detail(self) -> None:
        code, out = self.run_cli("clause", "8.7.3", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["id"], "8.7.3")
        self.assertIn("CTL-018", [c["id"] for c in payload["controls"]])
        self.assertTrue(all(e["present"] for e in payload["evidence"]))

    def test_unknown_clause_exits_two(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["clause", "99.9", "--db", str(self.path)])
        self.assertEqual(code, 2)

    def test_indicators_and_registers(self) -> None:
        code, out = self.run_cli("indicators", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), len(load_registry().indicators))

        code, out = self.run_cli("register", "concession", "--json")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out))

    def test_unknown_register_exits_two(self) -> None:
        code, _ = self.run_cli("register", "nope")
        self.assertEqual(code, 2)

    def test_missing_db_reports_error(self) -> None:
        code = cli.main(["conformity", "--db", "/nonexistent/path/rqms.db"])
        self.assertEqual(code, 2)

    def test_report_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "nested" / "report.html"
            code, _ = self.run_cli("report", "--out", str(out_path))
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists())


class GeneratedDocsTest(unittest.TestCase):
    """생성된 QMS 문서가 레지스트리와 동기화되어 있다."""

    def test_generated_docs_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "generate_qms_docs.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_process_has_description_document(self) -> None:
        for process in load_registry().processes:
            path = ROOT / "qms" / "20_processes" / f"RQMS-PRC-{process.code}.md"
            with self.subTest(process=process.code):
                self.assertTrue(path.exists())
                text = path.read_text(encoding="utf-8")
                self.assertIn(process.clause, text)
                self.assertIn("4.4.1 항목", text)

    def test_core_documents_exist(self) -> None:
        for relative in (
            "qms/README.md",
            "qms/00_manual/RQMS-MAN-001_품질매뉴얼.md",
            "qms/10_policy/RQMS-POL-001_품질및제품안전방침.md",
            "qms/40_indicators/RQMS-PI-001_성과지표정의서.md",
            "qms/30_templates/RQMS-FRM-001_부적합보고서.md",
        ):
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).exists())


if __name__ == "__main__":
    unittest.main()
