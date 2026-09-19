"""운영 웹 UI 테스트.

화면이 뜨는지뿐 아니라, 화면을 통한 입력도 CLI·API 와 **동일한 통제**를 받는지
확인한다(통제가 화면 계층에서 우회되면 안 된다).
"""

from __future__ import annotations

import datetime
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from rqms.db import Database, open_database
from rqms.seed import build
from rqms.standard import load_registry
from rqms.web.actions import (
    ACTION_BY_ID,
    ACTIONS,
    REF_SOURCES,
    SECTION_BY_KEY,
    SECTIONS,
    actions_for,
    ref_options,
)
from rqms.web.server import RqmsHandler, _FormError, build_values, coerce, pending_work

REGISTRY_REF_NAMES = {"process_code", "indicator_code", "clause_id", "special_process_code"}


class ActionRegistryTest(unittest.TestCase):
    """액션 명세가 서비스 함수와 어긋나지 않는지 확인한다."""

    def test_every_action_builds_fields(self) -> None:
        for action in ACTIONS:
            with self.subTest(action=action.id):
                fields = action.fields
                self.assertTrue(fields, f"{action.id}: 입력 필드가 없습니다.")

    def test_action_ids_unique(self) -> None:
        self.assertEqual(len(ACTION_BY_ID), len(ACTIONS))

    def test_every_section_has_actions(self) -> None:
        for section in SECTIONS:
            with self.subTest(section=section.key):
                self.assertTrue(actions_for(section.key))

    def test_every_action_section_exists(self) -> None:
        for action in ACTIONS:
            with self.subTest(action=action.id):
                self.assertIn(action.section, SECTION_BY_KEY)

    def test_reference_fields_have_known_source(self) -> None:
        for action in ACTIONS:
            for fld in action.fields:
                if fld.widget != "ref":
                    continue
                with self.subTest(action=action.id, field=fld.name):
                    self.assertTrue(
                        fld.ref in REF_SOURCES or fld.ref in REGISTRY_REF_NAMES,
                        f"미정의 참조 원천: {fld.ref}",
                    )

    def test_dict_fields_have_keys(self) -> None:
        for action in ACTIONS:
            for fld in action.fields:
                if fld.widget == "dict":
                    with self.subTest(action=action.id, field=fld.name):
                        self.assertTrue(fld.dict_keys)

    def test_created_identifiers_are_free_text(self) -> None:
        """새 번호를 만드는 입력은 기존 목록 선택이 아니라 자유 입력이어야 한다."""
        expected = {
            "nonconformity.raise_nonconformity": "nc_no",
            "suppliers.issue_purchase_order": "po_no",
            "fai.plan": "fai_no",
            "capa.open_capa": "capa_no",
            "tender.open_tender": "tender_no",
            "audit.plan_audit": "audit_no",
            "production.create_item": "serial_no",
        }
        for action_id, name in expected.items():
            with self.subTest(action=action_id):
                fld = next(f for f in ACTION_BY_ID[action_id].fields if f.name == name)
                self.assertEqual(fld.widget, "text")
                self.assertIsNone(fld.ref)

    def test_existing_record_references_are_selects(self) -> None:
        """기존 기록을 고르는 입력은 선택 목록이어야 한다."""
        expected = {
            "nonconformity.close": "nc_no",
            "change.approve": "change_no",
            "suppliers.acknowledge_order": "po_no",
            "customer.acknowledge": "complaint_no",
        }
        for action_id, name in expected.items():
            with self.subTest(action=action_id):
                fld = next(f for f in ACTION_BY_ID[action_id].fields if f.name == name)
                self.assertEqual(fld.widget, "ref")

    def test_registry_backed_choices(self) -> None:
        """프로세스·지표·조항 선택지는 표준 레지스트리에서 온다."""
        db = Database(":memory:")
        db.init_schema()
        registry = load_registry()
        self.assertEqual(len(ref_options(db, "process_code")), len(registry.processes))
        self.assertEqual(len(ref_options(db, "indicator_code")), len(registry.indicators))
        self.assertEqual(len(ref_options(db, "clause_id")), len(registry.clauses))
        db.close()


class CoercionTest(unittest.TestCase):
    """폼 원시값 → 서비스 인자 변환."""

    def field(self, action_id: str, name: str):
        return next(f for f in ACTION_BY_ID[action_id].fields if f.name == name)

    def test_checkbox_absent_is_false(self) -> None:
        fld = self.field("nonconformity.raise_nonconformity", "safety_impact")
        self.assertFalse(coerce(fld, {}))
        self.assertTrue(coerce(fld, {"safety_impact": ["on"]}))

    def test_number_cast(self) -> None:
        fld = self.field("nonconformity.raise_nonconformity", "qty")
        self.assertEqual(coerce(fld, {"qty": ["3"]}), 3.0)

    def test_required_missing_raises(self) -> None:
        fld = self.field("nonconformity.raise_nonconformity", "nc_no")
        with self.assertRaises(_FormError) as ctx:
            coerce(fld, {"nc_no": [""]})
        self.assertIn("필수 항목입니다", str(ctx.exception))

    def test_dict_field_collects_subfields(self) -> None:
        action = ACTION_BY_ID["governance.record_quality_policy"]
        fld = next(f for f in action.fields if f.name == "topics")
        raw = {f"topics__{k}": [f"{k} 내용"] for k in fld.dict_keys}
        result = coerce(fld, raw)
        self.assertEqual(set(result), set(fld.dict_keys))

    def test_pairs_field_parses_lines(self) -> None:
        action = ACTION_BY_ID["production.start_order"]
        fld = next(f for f in action.fields if f.name == "operator_ids")
        result = coerce(fld, {"operator_ids": ["SP-CRIMP=7\nSP-WELD=7"]})
        self.assertEqual(result, {"SP-CRIMP": 7, "SP-WELD": 7})

    def test_list_field_splits(self) -> None:
        action = ACTION_BY_ID["configuration.establish_baseline"]
        fld = next(f for f in action.fields if f.name == "part_numbers")
        self.assertEqual(coerce(fld, {"part_numbers": ["A-1, A-2\nA-3"]}), ["A-1", "A-2", "A-3"])

    def test_optional_empty_is_omitted(self) -> None:
        action = ACTION_BY_ID["nonconformity.raise_nonconformity"]
        values = build_values(action, {"nc_no": ["NC-1"], "source": ["internal"],
                                       "description": ["내용"], "ref": [""]})
        self.assertNotIn("ref", values)
        self.assertEqual(values["nc_no"], "NC-1")


class WebServerTest(unittest.TestCase):
    """실제 HTTP 요청으로 화면과 입력을 검증한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = tempfile.TemporaryDirectory()
        cls.path = Path(cls._dir.name) / "web.db"
        db = open_database(cls.path, create=True)
        build(db)
        db.close()

        handler = type(
            "TestHandler",
            (RqmsHandler,),
            {"db_path": str(cls.path), "log_message": lambda *a, **k: None},
        )
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls._dir.cleanup()

    # ------------------------------------------------------------------ 유틸
    def get(self, path: str) -> tuple[int, str]:
        with urllib.request.urlopen(self.base + path, timeout=30) as response:
            return response.status, response.read().decode("utf-8")

    def post(self, path: str, data: dict[str, str]) -> tuple[int, str]:
        body = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=body, method="POST")
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    # ------------------------------------------------------------------ 화면
    def test_dashboard(self) -> None:
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("대시보드", body)
        self.assertIn("처리 대기", body)

    def test_all_section_pages_render(self) -> None:
        for section in SECTIONS:
            with self.subTest(section=section.key):
                status, body = self.get(f"/s/{section.key}")
                self.assertEqual(status, 200)
                self.assertNotIn("처리 중 오류", body)

    def test_all_action_forms_render(self) -> None:
        for action in ACTIONS:
            with self.subTest(action=action.id):
                status, body = self.get(f"/a/{action.id}")
                self.assertEqual(status, 200)
                self.assertNotIn("처리 중 오류", body)
                self.assertIn(action.clause, body)

    def test_conformity_and_checks_pages(self) -> None:
        for path, marker in (("/conformity", "적합성 평가"), ("/checks", "통제 점검")):
            status, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertIn(marker, body)

    def test_clause_page_links_controls(self) -> None:
        status, body = self.get("/clause/8.7.3")
        self.assertEqual(status, 200)
        self.assertIn("CTL-018", body)

    def test_unknown_paths_are_404(self) -> None:
        for path in ("/s/nope", "/a/nope.nope", "/clause/99.9", "/zzz"):
            with self.subTest(path=path):
                try:
                    status, _ = self.get(path)
                except urllib.error.HTTPError as exc:
                    status = exc.code
                self.assertEqual(status, 404)

    # ------------------------------------------------------------------ 입력
    def test_successful_input_redirects_and_persists(self) -> None:
        status, _ = self.post(
            "/a/nonconformity.raise_nonconformity",
            {
                "nc_no": "NC-WEBTEST-001",
                "source": "internal",
                "description": "웹 화면 입력 시험",
                "qty": "2",
            },
        )
        self.assertEqual(status, 303)
        with Database(str(self.path)) as db:
            row = db.find("nonconformity", nc_no="NC-WEBTEST-001")
        self.assertIsNotNone(row)

    def test_missing_required_field_is_rejected(self) -> None:
        status, body = self.post(
            "/a/nonconformity.raise_nonconformity",
            {"nc_no": "", "source": "internal", "description": "내용"},
        )
        self.assertEqual(status, 200)
        self.assertIn("필수 항목입니다", body)

    def test_control_violation_is_shown_with_clause(self) -> None:
        """화면 입력도 통제를 우회하지 못한다 (CTL-011)."""
        status, _ = self.post(
            "/a/suppliers.register", {"code": "SUP-WEBTEST", "name": "웹시험협력사"}
        )
        self.assertEqual(status, 303)

        from rqms.services.suppliers import REQUIRED_COMMUNICATION

        payload = {
            "po_no": "PO-WEBTEST-001",
            "supplier_code": "SUP-WEBTEST",
            "item": "시험 부품",
            "qty": "1",
            "required_on": "2026-12-31",
        }
        payload.update(
            {f"requirements_communicated__{k}": "전달" for k in REQUIRED_COMMUNICATION}
        )
        status, body = self.post("/a/suppliers.issue_purchase_order", payload)

        self.assertEqual(status, 200)
        self.assertIn("입력이 거부되었습니다", body)
        self.assertIn("CTL-011", body)
        self.assertIn("8.4.1.1.4", body)  # 근거 조항 링크
        self.assertIn("PO-WEBTEST-001", body)  # 입력값 보존

        with Database(str(self.path)) as db:
            self.assertIsNone(db.find("purchase_order", po_no="PO-WEBTEST-001"))

    def test_gate_control_enforced_through_web(self) -> None:
        """단계검토 미결사항 통제(CTL-004)도 화면에서 동일하게 작동한다."""
        project = f"PRJ-{datetime.date.today().year}-001"
        status, _ = self.post(
            "/a/projects.plan_phase_review",
            {
                "project_code": project,
                "phase": "design",
                "planned_on": "2026-10-01",
                "mandatory_participants": "pm,qm",
            },
        )
        self.assertEqual(status, 303)
        status, _ = self.post(
            "/a/projects.raise_open_issue",
            {
                "project_code": project,
                "description": "웹 시험 미결사항",
                "owner_id": "1",
                "due_on": "2026-11-01",
                "phase": "planning",
            },
        )
        self.assertEqual(status, 303)
        status, body = self.post(
            "/a/projects.hold_phase_review",
            {
                "project_code": project,
                "phase": "design",
                "decision": "accepted",
                "actual_participants": "pm,qm",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("CTL-004", body)

    def test_pending_work_lists_open_items(self) -> None:
        with Database(str(self.path)) as db:
            items = dict((label, count) for label, count, _ in pending_work(db))
        self.assertIn("미종결 부적합", items)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """303 리다이렉트를 따라가지 않고 그대로 확인하기 위한 핸들러."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
