"""로컬 운영 웹 서버.

`python -m rqms serve --db rqms.db` 로 기동하고 브라우저에서 접속한다.
표준 라이브러리 `http.server` 만 사용한다.

보안 주의
    이 서버는 **인증이 없고 기본적으로 127.0.0.1 에만 바인딩**한다. 사내 네트워크나
    인터넷에 노출하면 안 된다. 다중 사용자·권한 분리가 필요하면 인증을 갖춘 서버로
    옮겨야 한다(README 참조).
"""

from __future__ import annotations

import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from .. import conformity as conformity_mod
from .. import report as report_mod
from ..checks import run_checks
from ..db import Database
from ..errors import ControlViolation, NotFound, RqmsError
from ..standard import load_registry
from . import views
from .actions import (
    ACTION_BY_ID,
    ACTIONS,
    SECTION_BY_KEY,
    Action,
    Field,
    actions_for,
    ref_options,
)

#: 값이 입력되지 않았음을 뜻하는 표식 (서비스 함수의 기본값을 쓰게 한다)
_OMIT = object()


class _FormError(RqmsError):
    """폼 입력 단계의 검증 오류."""


def coerce(fld: Field, raw: dict[str, list[str]]) -> Any:
    """폼 원시값을 서비스 함수 인자로 변환한다."""
    if fld.widget == "bool":
        return bool(raw.get(fld.name))

    if fld.widget == "dict":
        collected = {}
        for key in fld.dict_keys:
            value = (raw.get(f"{fld.name}__{key}", [""])[0] or "").strip()
            if value:
                collected[key] = value
        if not collected and not fld.required:
            return _OMIT
        return collected

    if fld.widget == "pairs":
        text = (raw.get(fld.name, [""])[0] or "").strip()
        if not text:
            return _OMIT
        collected = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            collected[key.strip()] = value.strip()
        if fld.name == "operator_ids":
            return {k: int(v) for k, v in collected.items() if v.isdigit()}
        return collected

    if fld.widget == "list":
        text = (raw.get(fld.name, [""])[0] or "").strip()
        if not text:
            return _OMIT if not fld.required else []
        items = [
            part.strip()
            for line in text.splitlines()
            for part in line.split(",")
            if part.strip()
        ]
        return items

    value = (raw.get(fld.name, [""])[0] or "").strip()
    if not value:
        if fld.required:
            raise _FormError(f"필수 항목입니다: {fld.label}")
        return _OMIT
    if fld.cast == "int":
        try:
            return int(value)
        except ValueError as exc:
            raise _FormError(f"{fld.label}: 정수를 입력하십시오.") from exc
    if fld.cast == "float":
        try:
            return float(value)
        except ValueError as exc:
            raise _FormError(f"{fld.label}: 숫자를 입력하십시오.") from exc
    return value


def build_values(action: Action, raw: dict[str, list[str]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for fld in action.fields:
        result = coerce(fld, raw)
        if result is not _OMIT:
            values[fld.name] = result
    return values


def pending_work(db: Database) -> list[tuple[str, int, str]]:
    """대시보드의 '처리 대기' 목록."""
    queries = [
        ("미종결 부적합", "SELECT COUNT(*) FROM nonconformity WHERE status != 'closed'", "8.7"),
        ("미종결 시정조치", "SELECT COUNT(*) FROM capa WHERE status != 'closed'", "10.2"),
        (
            "시정조치 필요성 미평가 부적합",
            "SELECT COUNT(*) FROM nonconformity WHERE capa_needed IS NULL",
            "10.2.3 b)",
        ),
        (
            "미종결 프로젝트 미결사항",
            "SELECT COUNT(*) FROM open_issue WHERE closed_on IS NULL",
            "8.1.3.1.1 g)",
        ),
        (
            "승인 대기 문서",
            "SELECT COUNT(*) FROM document WHERE status IN ('draft','in_review')",
            "7.5.2",
        ),
        (
            "확인서 미수령 발주",
            "SELECT COUNT(*) FROM purchase_order WHERE acknowledged_on IS NULL",
            "8.4.4 a)",
        ),
        (
            "접수 통보 누락 고객불만",
            "SELECT COUNT(*) FROM complaint WHERE acknowledged_on IS NULL",
            "9.1.2.1 b)",
        ),
        (
            "실행 검증 누락 변경",
            "SELECT COUNT(*) FROM change_request "
            "WHERE implemented_on IS NOT NULL AND implementation_verified_on IS NULL",
            "8.1.4.2 j)",
        ),
        (
            "미해소 역량 갭",
            "SELECT COUNT(*) FROM competence_gap WHERE closed_on IS NULL",
            "7.2.1.1 b)",
        ),
        (
            "목표 미달 지표",
            "SELECT COUNT(*) FROM indicator_measurement WHERE met = 0",
            "9.1.3.1",
        ),
        (
            "미종결 고위험 단산 리스크",
            "SELECT COUNT(*) FROM obsolescence_risk "
            "WHERE risk_level = 'high' AND status = 'open'",
            "8.10",
        ),
    ]
    out: list[tuple[str, int, str]] = []
    for label, sql, clause in queries:
        try:
            out.append((label, db.count(sql), clause))
        except Exception:  # pragma: no cover
            continue
    return out


class RqmsHandler(BaseHTTPRequestHandler):
    """RQMS 웹 요청 처리기."""

    server_version = "RQMS"
    db_path: str = ""

    # ----------------------------------------------------------------- 유틸
    def _db(self) -> Database:
        return Database(self.db_path)

    def _send(self, html: str, status: int = HTTPStatus.OK) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:  # 접속 로그를 간결하게
        print(f"  {self.address_string()} {fmt % args}")

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:  # noqa: N802 - http.server 규약
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        flash = ""
        if query.get("ok"):
            flash = views.banner("ok", "처리되었습니다", query["ok"][0])

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        try:
            with self._db() as db:
                if path == "/":
                    report = conformity_mod.assess(db)
                    findings = run_checks(db)
                    body = views.dashboard(db, report, findings, pending_work(db))
                    self._send(views.page("대시보드", body, active="home", flash=flash))
                    return
                if path == "/conformity":
                    body = views.conformity_page(conformity_mod.assess(db))
                    self._send(views.page("적합성 평가", body, active="conformity"))
                    return
                if path == "/checks":
                    body = views.checks_page(run_checks(db))
                    self._send(views.page("통제 점검", body, active="checks"))
                    return
                if path == "/report":
                    self._send(report_mod.render(db))
                    return
                if path.startswith("/s/"):
                    key = path[3:]
                    section = SECTION_BY_KEY.get(key)
                    if section is None:
                        self._send(views.page("없음", views.not_found(path)),
                                   HTTPStatus.NOT_FOUND)
                        return
                    body = views.section_page(db, section, actions_for(key))
                    self._send(views.page(section.title, body, active=key, flash=flash))
                    return
                if path.startswith("/a/"):
                    self._render_form(db, path[3:], {}, flash=flash)
                    return
                if path.startswith("/clause/"):
                    self._render_clause(db, path[len("/clause/"):])
                    return
            self._send(views.page("없음", views.not_found(path)), HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - 개발 중 오류 표면화
            traceback.print_exc()
            self._send(
                views.page("오류", views.error_page("처리 중 오류", str(exc))),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802 - http.server 규약
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not path.startswith("/a/"):
            self._send(views.page("없음", views.not_found(path)), HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length).decode("utf-8") if length else ""
        raw = parse_qs(raw_body, keep_blank_values=True)

        action_id = path[3:]
        action = ACTION_BY_ID.get(action_id)
        if action is None:
            self._send(views.page("없음", views.not_found(path)), HTTPStatus.NOT_FOUND)
            return

        try:
            with self._db() as db:
                try:
                    values = build_values(action, raw)
                    result = action.call(db, values)
                except ControlViolation as violation:
                    error = views.violation_banner(
                        violation.control_id,
                        violation.clauses,
                        str(violation).split(": ", 1)[-1],
                    )
                    self._render_form(db, action_id, raw, error=error)
                    return
                except (_FormError, ValueError, NotFound) as exc:
                    error = views.banner("err", "입력을 확인하십시오", str(exc))
                    self._render_form(db, action_id, raw, error=error)
                    return
                except Exception as exc:  # pragma: no cover
                    traceback.print_exc()
                    error = views.banner("err", "처리 중 오류", f"{type(exc).__name__}: {exc}")
                    self._render_form(db, action_id, raw, error=error)
                    return

            message = f"{action.label} 완료"
            if isinstance(result, int):
                message += f" (기록 #{result})"
            self._redirect(f"/s/{action.section}?ok={quote(message)}")
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self._send(
                views.page("오류", views.error_page("처리 중 오류", str(exc))),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------ 내부
    def _render_form(
        self,
        db: Database,
        action_id: str,
        raw: dict[str, list[str]],
        *,
        error: str = "",
        flash: str = "",
    ) -> None:
        action = ACTION_BY_ID.get(action_id)
        if action is None:
            self._send(
                views.page("없음", views.not_found(f"/a/{action_id}")),
                HTTPStatus.NOT_FOUND,
            )
            return
        fields = action.fields
        options: dict[str, list[tuple[str, str]]] = {}
        for fld in fields:
            if fld.widget == "ref" and fld.ref:
                options[fld.name] = ref_options(db, fld.ref)
        values = {k: v[0] for k, v in raw.items() if v}
        body = views.action_form(action, fields, options, values, error=error)
        self._send(views.page(action.label, body, active=action.section, flash=flash))

    def _render_clause(self, db: Database, clause_id: str) -> None:
        registry = load_registry()
        try:
            clause = registry.clause(clause_id)
        except KeyError:
            self._send(
                views.page("없음", views.not_found(f"/clause/{clause_id}")),
                HTTPStatus.NOT_FOUND,
            )
            return
        detail = {
            "title_ko": clause.title_ko,
            "title_en": clause.title_en,
            "obligation": clause.obligation,
            "source": clause.source,
            "processes": list(clause.processes),
            "modules": list(clause.modules),
            "controls": [
                {
                    "id": cid,
                    "kind": registry.control(cid).kind,
                    "severity": registry.control(cid).severity,
                    "title": registry.control(cid).title,
                }
                for cid in clause.controls
            ],
            "evidence": [
                {
                    "key": key,
                    "label": conformity_mod.EVIDENCE_SOURCES.get(key, ("", "", key))[2],
                    "present": conformity_mod.evidence_present(db, key),
                }
                for key in clause.documented_info
            ],
        }
        related = tuple(a for a in ACTIONS if clause_id in a.clause)
        body = views.clause_page(clause_id, detail, related)
        self._send(views.page(f"{clause_id} 조항", body))


def serve(db_path: str | Path, *, host: str = "127.0.0.1", port: int = 8000) -> None:
    """웹 서버를 기동한다 (Ctrl+C 로 종료)."""
    path = Path(db_path)
    if not path.exists():
        raise RqmsError(
            f"데이터베이스 {path} 가 없습니다. 먼저 `python -m rqms init --db {path}` 를"
            " 실행하십시오."
        )

    handler = type("BoundRqmsHandler", (RqmsHandler,), {"db_path": str(path)})
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"RQMS 운영 화면: http://{host}:{port}/")
    print(f"  데이터베이스: {path}")
    print(f"  입력 화면 {len(ACTIONS)}개 · 등록부 {len(SECTION_BY_KEY)}개 영역")
    print("  종료: Ctrl+C")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("  주의: 이 서버는 인증이 없습니다. 신뢰할 수 없는 네트워크에 노출하지 마십시오.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        httpd.server_close()
