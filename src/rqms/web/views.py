"""서버사이드 HTML 렌더링.

템플릿 엔진 없이 문자열로 조립한다(외부 의존성 없음). 사용자 입력은 모두
`html.escape` 로 이스케이프한다.
"""

from __future__ import annotations

import contextlib
from html import escape
from typing import Any

from ..checks import Finding
from ..conformity import ConformityReport
from ..db import Database
from ..standard import load_registry
from .actions import (
    SECTIONS,
    Action,
    Field,
    Section,
)

STYLE = """
:root {
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --accent:#2a78d6; --good:#0ca30c; --warning:#fab219; --critical:#d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10); --accent:#3987e5;
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink); line-height:1.55;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; font-size:15px; }
a { color:var(--accent); }
.shell { display:grid; grid-template-columns:266px 1fr; min-height:100vh; }
nav { background:var(--surface); border-right:1px solid var(--border); padding:18px 0 48px;
  position:sticky; top:0; height:100vh; overflow-y:auto; }
nav .brand { padding:0 18px 12px; }
nav .brand b { display:block; font-size:1rem; }
nav .brand span { color:var(--muted); font-size:0.76rem; }
nav .group { color:var(--muted); font-size:0.72rem; letter-spacing:.04em;
  padding:14px 18px 4px; text-transform:uppercase; }
nav a.item { display:block; padding:6px 18px; color:var(--ink-2); text-decoration:none;
  font-size:0.88rem; border-left:3px solid transparent; }
nav a.item:hover { background:var(--page); color:var(--ink); }
nav a.item.active { border-left-color:var(--accent); color:var(--ink); font-weight:600;
  background:var(--page); }
nav a.item small { color:var(--muted); font-weight:400; }
main { padding:26px 30px 72px; max-width:1180px; }
h1 { font-size:1.4rem; margin:0 0 2px; }
h2 { font-size:1.05rem; margin:30px 0 8px; }
.sub { color:var(--muted); font-size:0.85rem; margin:0 0 20px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(178px,1fr)); gap:12px; }
.tile { background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:14px 16px; }
.tile .label { color:var(--ink-2); font-size:0.8rem; }
.tile .value { font-size:1.7rem; font-weight:650; }
.tile .note { color:var(--muted); font-size:0.76rem; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:16px 18px; margin-bottom:14px; }
.scroll { overflow-x:auto; }
table { min-width:100%; width:max-content; border-collapse:collapse; background:var(--surface);
  border:1px solid var(--border); border-radius:10px; font-size:0.84rem; }
th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--grid);
  white-space:nowrap; vertical-align:middle; }
td.text { white-space:normal; max-width:420px; }
th { color:var(--ink-2); font-weight:600; background:var(--page); }
tr:last-child td { border-bottom:none; }
.empty { color:var(--muted); font-size:0.86rem; padding:10px 0; }
.actions { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 18px; }
.actions a { display:inline-block; background:var(--surface); border:1px solid var(--axis);
  border-radius:7px; padding:6px 11px; font-size:0.84rem; text-decoration:none; color:var(--ink); }
.actions a:hover { border-color:var(--accent); color:var(--accent); }
.actions a small { display:block; color:var(--muted); font-size:0.72rem; }
form .field { margin-bottom:14px; }
form label { display:block; font-size:0.86rem; margin-bottom:3px; }
form label .req { color:var(--critical); }
form .help { color:var(--muted); font-size:0.76rem; margin-top:2px; }
input[type=text],input[type=number],input[type=date],select,textarea {
  width:100%; max-width:620px; padding:7px 9px; border:1px solid var(--axis);
  border-radius:7px; background:var(--page); color:var(--ink); font:inherit; font-size:0.88rem; }
textarea { min-height:78px; resize:vertical; }
input[type=checkbox] { width:16px; height:16px; }
fieldset { border:1px solid var(--grid); border-radius:8px; padding:10px 12px; margin:0;
  max-width:620px; }
fieldset legend { color:var(--ink-2); font-size:0.8rem; padding:0 5px; }
button { background:var(--accent); color:#fff; border:none; border-radius:7px;
  padding:9px 18px; font:inherit; font-size:0.9rem; cursor:pointer; }
button.ghost { background:transparent; color:var(--ink-2); border:1px solid var(--axis); }
.banner { border-radius:9px; padding:12px 14px; margin-bottom:18px; font-size:0.88rem; }
.banner.ok { border:1px solid var(--good); }
.banner.err { border:1px solid var(--critical); }
.banner b { display:block; margin-bottom:3px; }
.banner code { font-size:0.82rem; }
.status { display:inline-flex; align-items:center; gap:5px; font-size:0.82rem; }
.status .dot { width:9px; height:9px; border-radius:50%; flex:none; }
.status.ok .dot { background:var(--good); } .status.ok { color:var(--good); }
.status.warn .dot { background:var(--warning); }
.status.bad .dot { background:var(--critical); } .status.bad { color:var(--critical); }
.tag { display:inline-block; border:1px solid var(--axis); border-radius:999px;
  padding:0 7px; font-size:0.73rem; color:var(--ink-2); }
.clausebar { color:var(--muted); font-size:0.8rem; margin-bottom:14px; }
@media (max-width:860px) {
  .shell { grid-template-columns:1fr; }
  nav { position:static; height:auto; }
  main { padding:20px 16px 60px; }
}
"""

#: 내비게이션 묶음
NAV_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("4~6장 기획", ("governance", "risk")),
    ("7장 지원", ("documents", "people", "calibration", "support")),
    ("8장 운용", (
        "tender", "requirements", "projects", "configuration", "change", "transfer",
        "design", "suppliers", "production", "special_processes", "release",
        "nonconformity", "rams", "fai", "obsolescence", "post_delivery",
    )),
    ("9장 성과평가", ("indicators", "customer", "audit", "review")),
    ("10장 개선", ("capa",)),
)


def page(title: str, body: str, *, active: str = "", flash: str = "") -> str:
    """공통 레이아웃."""
    nav = [
        '<nav><div class="brand"><b>RQMS</b>'
        '<span>ISO 22163:2023 철도용 품질경영시스템</span></div>',
        _nav_item("/", "대시보드", active == "home"),
        _nav_item("/conformity", "적합성 평가", active == "conformity"),
        _nav_item("/checks", "통제 점검", active == "checks"),
        _nav_item("/report", "적합성 보고서", active == "report"),
    ]
    by_key = {s.key: s for s in SECTIONS}
    for group, keys in NAV_GROUPS:
        nav.append(f'<div class="group">{escape(group)}</div>')
        for key in keys:
            section = by_key[key]
            nav.append(
                _nav_item(
                    f"/s/{key}",
                    f"{escape(section.title)}<small> · {escape(section.chapter)}</small>",
                    active == key,
                    raw=True,
                )
            )
    nav.append("</nav>")
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)} · RQMS</title><style>{STYLE}</style></head><body>"
        f"<div class='shell'>{''.join(nav)}<main>{flash}{body}</main></div></body></html>"
    )


def _nav_item(href: str, label: str, active: bool, *, raw: bool = False) -> str:
    text = label if raw else escape(label)
    return f'<a class="item{" active" if active else ""}" href="{href}">{text}</a>'


def banner(kind: str, title: str, detail: str = "") -> str:
    body = f"<b>{escape(title)}</b>" + (escape(detail) if detail else "")
    return f'<div class="banner {kind}">{body}</div>'


def violation_banner(control_id: str, clauses: tuple[str, ...], message: str) -> str:
    """통제 위반을 근거 조항과 함께 보여준다."""
    links = " · ".join(
        f'<a href="/clause/{escape(c)}">{escape(c)}</a>' for c in clauses
    )
    return (
        '<div class="banner err">'
        f"<b>입력이 거부되었습니다 — {escape(control_id)}</b>"
        f"{escape(message)}<br><span class='clausebar'>근거 조항: {links}</span>"
        "</div>"
    )


# ------------------------------------------------------------------------ 표
def table(rows: list[dict[str, Any]], columns: list[str], *, wrap: set[str] | None = None) -> str:
    if not rows:
        return '<div class="empty">등록된 기록이 없습니다.</div>'
    wrap = wrap or set()
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            text = "" if value is None else str(value)
            cls = ' class="text"' if column in wrap else ""
            cells.append(f"<td{cls}>{escape(text)}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f'<div class="scroll"><table><tr>{head}</tr>{"".join(body)}</table></div>'
    )


def register_table(db: Database, table_name: str, *, limit: int = 60) -> str:
    """등록부 테이블을 최근 기록부터 보여준다."""
    try:
        rows = db.query(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT ?", (limit,))
    except Exception as exc:  # pragma: no cover - 스키마 변경 시 화면은 살아 있어야 한다
        return f'<div class="empty">조회 실패: {escape(str(exc))}</div>'
    if not rows:
        return '<div class="empty">등록된 기록이 없습니다.</div>'
    # sqlite3.Row 는 순회 시 "값"을 내주므로 컬럼명을 얻으려면 .keys() 가 필요하다.
    columns = [c for c in rows[0].keys() if c != "id"][:9]  # noqa: SIM118
    data = [{c: _short(r[c]) for c in columns} for r in rows]
    return table(data, columns)


def _short(value: Any, width: int = 60) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


# ------------------------------------------------------------------- 대시보드
def dashboard(
    db: Database, report: ConformityReport, findings: list[Finding], todo: list[tuple[str, int, str]]
) -> str:
    summary = report.summary()
    registry = load_registry()
    kpi_unmet = db.count(
        "SELECT COUNT(*) FROM indicator_measurement WHERE met = 0"
    )
    tiles = [
        ("적용 조항 적합률", f"{summary['conformity_rate_pct']}%",
         f"적용 {summary['clauses_applicable']}개 중 적합 {summary['conformant']}개"),
        ("조항 갭", str(summary["gaps"]),
         "갭 없음" if summary["gaps"] == 0 else "시정조치 필요"),
        ("통제 위반", str(len(findings)),
         f"중 {sum(1 for f in findings if f.severity == 'major')} /"
         f" 경 {sum(1 for f in findings if f.severity == 'minor')}"),
        ("목표 미달 지표", str(kpi_unmet), "9.1.3.1 시정조치 대상"),
        ("등록 프로세스", str(db.count("SELECT COUNT(*) FROM process_instance")),
         f"Annex A 필수 {len(registry.mandatory_processes())} / 권고"
         f" {len(registry.recommended_processes())}"),
    ]
    tile_html = "".join(
        f'<div class="tile"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}</div>'
        f'<div class="note">{escape(note)}</div></div>'
        for label, value, note in tiles
    )

    todo_html = (
        table(
            [{"항목": t, "건수": n, "근거 조항": c} for t, n, c in todo if n],
            ["항목", "건수", "근거 조항"],
        )
        if any(n for _, n, _ in todo)
        else '<div class="empty">처리해야 할 항목이 없습니다.</div>'
    )

    finding_html = (
        table(
            [
                {
                    "통제": f.control_id,
                    "중요도": f.severity,
                    "조항": ", ".join(f.clauses),
                    "내용": f.detail,
                }
                for f in findings[:20]
            ],
            ["통제", "중요도", "조항", "내용"],
            wrap={"내용"},
        )
        if findings
        else '<div class="empty">통제 위반이 없습니다.</div>'
    )

    return (
        "<h1>대시보드</h1>"
        f"<p class='sub'>기준일 {escape(report.as_of)} · 조항 {summary['clauses_total']}개 ·"
        f" 통제 {len(registry.controls)}개</p>"
        f'<div class="tiles">{tile_html}</div>'
        "<h2>처리 대기</h2>"
        f"{todo_html}"
        "<h2>통제 위반</h2>"
        f"{finding_html}"
    )


# ------------------------------------------------------------------- 섹션 화면
def section_page(db: Database, section: Section, actions: tuple[Action, ...]) -> str:
    buttons = "".join(
        f'<a href="/a/{escape(a.id)}">{escape(a.label)}'
        f"<small>{escape(a.clause)}</small></a>"
        for a in actions
    )
    blocks = []
    for table_name, label in section.registers:
        count = 0
        with contextlib.suppress(Exception):  # pragma: no cover
            count = db.count(f"SELECT COUNT(*) FROM {table_name}")
        blocks.append(
            f"<h2>{escape(label)} <span class='tag'>{count}건</span></h2>"
            f"{register_table(db, table_name)}"
        )
    return (
        f"<h1>{escape(section.title)}</h1>"
        f"<p class='sub'>{escape(section.chapter)} · 근거 조항 {escape(section.clause)}</p>"
        "<h2>업무 입력</h2>"
        f'<div class="actions">{buttons}</div>'
        + "".join(blocks)
    )


# --------------------------------------------------------------------- 폼 화면
def action_form(
    action: Action,
    fields: tuple[Field, ...],
    options: dict[str, list[tuple[str, str]]],
    values: dict[str, str],
    *,
    error: str = "",
) -> str:
    parts = [
        f"<h1>{escape(action.label)}</h1>",
        f"<p class='sub'>근거 조항 {escape(action.clause)} ·"
        f" 처리 함수 <code>{escape(action.id)}</code></p>",
    ]
    if action.note:
        parts.append(banner("ok", "이 입력에 적용되는 통제", action.note))
    if error:
        parts.append(error)
    parts.append(f'<form method="post" action="/a/{escape(action.id)}"><div class="card">')
    for fld in fields:
        parts.append(_field_html(fld, options.get(fld.name, []), values))
    parts.append(
        "</div><button type='submit'>저장</button> "
        f"<a class='tag' href='/s/{escape(action.section)}' "
        "style='padding:9px 14px;margin-left:8px'>취소</a></form>"
    )
    return "".join(parts)


def _field_html(
    fld: Field, options: list[tuple[str, str]], values: dict[str, str]
) -> str:
    label = (
        f'<label for="{escape(fld.name)}">{escape(fld.label)}'
        f'{" <span class=req>*</span>" if fld.required else ""}'
        f' <span class="tag">{escape(fld.name)}</span></label>'
    )
    help_html = f'<div class="help">{escape(fld.help)}</div>' if fld.help else ""
    value = values.get(fld.name, "")
    name = escape(fld.name)

    if fld.widget == "bool":
        checked = " checked" if value in ("on", "true", "1") else ""
        control = f'<input type="checkbox" id="{name}" name="{name}"{checked}>'
    elif fld.widget == "textarea":
        control = f'<textarea id="{name}" name="{name}">{escape(value)}</textarea>'
    elif fld.widget == "number":
        control = (
            f'<input type="number" step="any" id="{name}" name="{name}"'
            f' value="{escape(value)}">'
        )
    elif fld.widget == "date":
        control = f'<input type="date" id="{name}" name="{name}" value="{escape(value)}">'
    elif fld.widget in ("choice", "ref"):
        source = (
            [(c, c) for c in fld.choices] if fld.widget == "choice" else options
        )
        opts = ['<option value="">— 선택 —</option>'] if not fld.required else []
        for val, text in source:
            sel = " selected" if str(val) == value else ""
            opts.append(f'<option value="{escape(str(val))}"{sel}>{escape(text)}</option>')
        control = f'<select id="{name}" name="{name}">{"".join(opts)}</select>'
    elif fld.widget == "dict":
        rows = []
        for key in fld.dict_keys:
            sub = f"{fld.name}__{key}"
            rows.append(
                f'<div class="field"><label for="{escape(sub)}">{escape(key)}</label>'
                f'<input type="text" id="{escape(sub)}" name="{escape(sub)}"'
                f' value="{escape(values.get(sub, ""))}"></div>'
            )
        control = (
            f'<fieldset><legend>{escape(fld.label)}</legend>{"".join(rows)}</fieldset>'
        )
        return f'<div class="field">{control}{help_html}</div>'
    elif fld.widget in ("pairs", "list"):
        placeholder = "한 줄에 하나씩" if fld.widget == "list" else "한 줄에 '키=값'"
        control = (
            f'<textarea id="{name}" name="{name}" placeholder="{placeholder}">'
            f"{escape(value)}</textarea>"
        )
    else:
        control = f'<input type="text" id="{name}" name="{name}" value="{escape(value)}">'
    return f'<div class="field">{label}{control}{help_html}</div>'


# ------------------------------------------------------------- 적합성 / 점검
def conformity_page(report: ConformityReport) -> str:
    summary = report.summary()
    gap_rows = [
        {
            "조항": a.clause.id,
            "제목": a.clause.title_ko,
            "의무": a.clause.obligation,
            "증거 누락": ", ".join(a.missing_evidence) or "-",
            "통제 위반": "; ".join(f.detail for f in a.control_findings) or "-",
        }
        for a in report.gaps
    ]
    tiles = "".join(
        f'<div class="tile"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(str(value))}</div></div>'
        for label, value in (
            ("적합률", f"{summary['conformity_rate_pct']}%"),
            ("필수(shall) 적합률", f"{summary['mandatory_conformity_rate_pct']}%"),
            ("적용 조항", summary["clauses_applicable"]),
            ("갭", summary["gaps"]),
        )
    )
    rows = [
        {
            "조항": a.clause.id,
            "제목": a.clause.title_ko,
            "의무": a.clause.obligation,
            "출처": "ISO 9001" if a.clause.source == "iso9001" else "22163",
            "프로세스": ", ".join(a.clause.processes) or "-",
            "통제": ", ".join(a.clause.controls) or "-",
            "증거": f"{len(a.clause.documented_info) - len(a.missing_evidence)}"
            f"/{len(a.clause.documented_info)}",
            "판정": {"conformant": "적합", "gap": "갭", "not_applicable": "비적용"}[a.status],
        }
        for a in report.assessments
    ]
    gap_html = (
        table(gap_rows, ["조항", "제목", "의무", "증거 누락", "통제 위반"],
              wrap={"제목", "증거 누락", "통제 위반"})
        if gap_rows
        else '<div class="empty">갭 없음 — 모든 적용 조항이 구현·통제·증거를 갖추고 있습니다.</div>'
    )
    return (
        "<h1>적합성 평가</h1>"
        f"<p class='sub'>기준일 {escape(report.as_of)} · 적합 = 구현 모듈 존재 +"
        " 통제 위반 없음 + 요구 증거 보유</p>"
        f'<div class="tiles">{tiles}</div>'
        "<h2>갭 목록</h2>" + gap_html +
        "<h2>조항 추적성 매트릭스</h2>" +
        table(rows, ["조항", "제목", "의무", "출처", "프로세스", "통제", "증거", "판정"],
              wrap={"제목"})
    )


def checks_page(findings: list[Finding]) -> str:
    rows = [
        {
            "통제": f.control_id,
            "중요도": f.severity,
            "통제 내용": f.title,
            "근거 조항": ", ".join(f.clauses),
            "위반 상세": f.detail,
        }
        for f in findings
    ]
    body = (
        table(rows, ["통제", "중요도", "통제 내용", "근거 조항", "위반 상세"],
              wrap={"통제 내용", "위반 상세"})
        if rows
        else '<div class="empty">위반 없음.</div>'
    )
    return (
        "<h1>통제 점검</h1>"
        "<p class='sub'>상태 점검형(audit) 통제를 시스템 전체 상태에 대해 검증합니다.</p>"
        f"{body}"
    )


def clause_page(
    clause_id: str,
    detail: dict[str, Any],
    related_actions: tuple[Action, ...],
) -> str:
    controls = "".join(
        f"<tr><td>{escape(c['id'])}</td><td>{escape(c['kind'])}</td>"
        f"<td>{escape(c['severity'])}</td><td class='text'>{escape(c['title'])}</td></tr>"
        for c in detail["controls"]
    )
    evidence = "".join(
        f"<tr><td>{'O' if e['present'] else 'X'}</td>"
        f"<td class='text'>{escape(e['label'])}</td>"
        f"<td>{escape(e['key'])}</td></tr>"
        for e in detail["evidence"]
    )
    action_html = "".join(
        f'<a href="/a/{escape(a.id)}">{escape(a.label)}<small>{escape(a.clause)}</small></a>'
        for a in related_actions
    )
    return (
        f"<h1>{escape(clause_id)} {escape(detail['title_ko'])}</h1>"
        f"<p class='sub'>{escape(detail['title_en'])} · {escape(detail['obligation'])}"
        f" ({escape(detail['source'])})</p>"
        "<div class='card'>"
        f"<div>프로세스: {escape(', '.join(detail['processes']) or '-')}</div>"
        f"<div>구현 모듈: <code>{escape(', '.join(detail['modules']) or '-')}</code></div>"
        "</div>"
        "<h2>강제 통제</h2>"
        + (
            f'<div class="scroll"><table><tr><th>통제</th><th>유형</th><th>중요도</th>'
            f"<th>내용</th></tr>{controls}</table></div>"
            if controls
            else '<div class="empty">지정된 통제 없음 — 증거 기반으로 평가합니다.</div>'
        )
        + "<h2>문서화된 정보(증거)</h2>"
        + (
            f'<div class="scroll"><table><tr><th>보유</th><th>증거</th><th>키</th></tr>'
            f"{evidence}</table></div>"
            if evidence
            else '<div class="empty">요구되는 문서화된 정보 없음.</div>'
        )
        + ("<h2>관련 입력 화면</h2>" + f'<div class="actions">{action_html}</div>'
           if action_html else "")
    )


def not_found(path: str) -> str:
    return (
        "<h1>페이지를 찾을 수 없습니다</h1>"
        f"<p class='sub'><code>{escape(path)}</code></p>"
        "<p><a href='/'>대시보드로 돌아가기</a></p>"
    )


def error_page(title: str, detail: str) -> str:
    return f"<h1>{escape(title)}</h1><p class='sub'>{escape(detail)}</p>"


def optional_str(value: str | None) -> str:
    return "" if value is None else str(value)
