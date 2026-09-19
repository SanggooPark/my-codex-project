"""표준 레지스트리 정합성 및 커버리지 테스트."""

from __future__ import annotations

import unittest

from rqms import checks
from rqms.conformity import EVIDENCE_SOURCES
from rqms.services import MODULES
from rqms.standard import load_registry


class RegistryStructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry()

    def test_annex_a_process_counts(self) -> None:
        """Annex A.1 필수 23개, A.2 권고 6개."""
        self.assertEqual(len(self.registry.mandatory_processes()), 23)
        self.assertEqual(len(self.registry.recommended_processes()), 6)

    def test_all_chapters_present(self) -> None:
        """4~10장 조항이 모두 등재되어 있다."""
        chapters = {c.id.split(".")[0] for c in self.registry.clauses}
        self.assertEqual(chapters, {"4", "5", "6", "7", "8", "9", "10"})

    def test_mandatory_clauses_dominate(self) -> None:
        """대부분의 조항은 shall 이며 should 조항도 누락 없이 관리된다."""
        shall = [c for c in self.registry.clauses if c.is_mandatory]
        should = [c for c in self.registry.clauses if c.obligation == "should"]
        self.assertGreater(len(shall), len(should))
        self.assertGreater(len(should), 0)

    def test_every_process_has_indicator(self) -> None:
        """4.4.1 c) — 모든 프로세스는 최소 1개 성과지표를 가진다."""
        for process in self.registry.processes:
            with self.subTest(process=process.code):
                self.assertTrue(self.registry.indicators_for_process(process.code))

    def test_every_mandatory_process_has_clause_link(self) -> None:
        """필수 프로세스는 근거 조항과 연결된다."""
        for process in self.registry.mandatory_processes():
            with self.subTest(process=process.code):
                self.assertIn(process.clause, {c.id for c in self.registry.clauses})

    def test_required_indicators_from_9_1_1_1_1(self) -> None:
        """9.1.1.1.1 h)~o) 8개 필수 측정 항목이 모두 정의되어 있다."""
        required = [i for i in self.registry.indicators if i.mandate == "required"]
        self.assertEqual(len(required), 8)
        clauses = {i.mandate_clause for i in required}
        for letter in "hijklmno":
            self.assertIn(f"9.1.1.1.1 {letter})", clauses)

    def test_recommended_indicators_from_9_1_1_1_2(self) -> None:
        """9.1.1.1.2 a)~d) 권고 측정 항목이 정의되어 있다."""
        recommended = [i for i in self.registry.indicators if i.mandate == "recommended"]
        self.assertEqual(len(recommended), 4)

    def test_indicator_definitions_complete(self) -> None:
        """9.1.1.1.1 a)~g) 정의 항목이 모두 채워져 있다."""
        for indicator in self.registry.indicators:
            with self.subTest(indicator=indicator.code):
                self.assertEqual(indicator.missing_definition_fields(), [])

    def test_kpis_exist(self) -> None:
        """5.3.1 a) — 최고경영자가 지정한 KPI 가 존재한다."""
        self.assertTrue(self.registry.kpis())

    def test_every_control_is_referenced(self) -> None:
        """미사용 통제가 없다(레지스트리 검증에 포함되지만 명시적으로 확인)."""
        for control in self.registry.controls:
            with self.subTest(control=control.id):
                self.assertTrue(self.registry.clauses_for_control(control.id))

    def test_control_clauses_exist(self) -> None:
        known = {c.id for c in self.registry.clauses}
        for control in self.registry.controls:
            for clause_id in control.clauses:
                with self.subTest(control=control.id, clause=clause_id):
                    self.assertIn(clause_id, known)

    def test_every_audit_control_has_check(self) -> None:
        """kind=audit 통제는 모두 점검 함수를 갖는다."""
        self.assertEqual(checks.unchecked_audit_controls(), [])

    def test_every_evidence_key_is_mapped(self) -> None:
        """조항이 요구하는 모든 증거 키가 저장 위치와 연결되어 있다."""
        keys = {e for c in self.registry.clauses for e in c.documented_info}
        self.assertEqual(keys - set(EVIDENCE_SOURCES), set())
        self.assertEqual(set(EVIDENCE_SOURCES) - keys, set())

    def test_clause_modules_importable(self) -> None:
        """조항이 지정한 구현 모듈이 실제로 존재한다."""
        import importlib

        paths = {m for c in self.registry.clauses for m in c.modules}
        paths |= {p.module for p in self.registry.processes}
        for path in sorted(paths):
            with self.subTest(module=path):
                importlib.import_module(path)

    def test_service_module_list_matches_registry(self) -> None:
        """services.MODULES 목록이 레지스트리 참조와 일치한다."""
        referenced = {m.rsplit(".", 1)[-1] for c in self.registry.clauses for m in c.modules}
        referenced |= {p.module.rsplit(".", 1)[-1] for p in self.registry.processes}
        self.assertEqual(referenced, set(MODULES))

    def test_safety_process_is_conditional(self) -> None:
        """8.8.3 안전 관리 프로세스는 조건부 필수로 관리된다."""
        safety = self.registry.process("SAF")
        self.assertEqual(safety.obligation, "mandatory_conditional")
        self.assertTrue(safety.applicability_condition)


if __name__ == "__main__":
    unittest.main()
