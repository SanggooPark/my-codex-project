"""HTML 적합성 보고서 생성.

경영검토(9.3)와 내부심사(9.2)에서 사용할 수 있는 단일 파일 보고서를 만든다.
외부 의존성 없이 표준 라이브러리만 사용하며, 명암 모드를 모두 지원한다.
"""

from __future__ import annotations

from html import escape

from .conformity import EVIDENCE_SOURCES, assess, control_matrix, process_matrix
from .db import Database, today
from .services import indicators
from .standard import load_registry

#: 장(chapter) 제목
CHAPTERS = {
    "4": "조직 상황",
    "5": "리더십",
    "6": "기획",
    "7": "지원",
    "8": "운용",
    "9": "성과평가",
    "10": "개선",
}

_STYLE = """
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --seq-100: #cde2fb;
  --seq-450: #2a78d6;
  --good: #0ca30c;
  --warning: #fab219;
  --critical: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink: #ffffff;
    --ink-2: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --border: rgba(255,255,255,0.10);
    --seq-100: #184f95;
    --seq-450: #3987e5;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d;
  --surface: #1a1a19;
  --ink: #ffffff;
  --ink-2: #c3c2b7;
  --grid: #2c2c2a;
  --axis: #383835;
  --border: rgba(255,255,255,0.10);
  --seq-100: #184f95;
  --seq-450: #3987e5;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.55;
}
.wrap { max-width: 1120px; margin: 0 auto; padding: 32px 16px 72px; }
header h1 { font-size: 1.6rem; margin: 0 0 4px; }
header p { color: var(--ink-2); margin: 0 0 24px; }
section { margin-top: 36px; }
h2 { font-size: 1.15rem; margin: 0 0 4px; }
h2 + .hint { color: var(--muted); font-size: 0.85rem; margin: 0 0 14px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
}
.tile .label { color: var(--ink-2); font-size: 0.82rem; }
.tile .value { font-size: 1.9rem; font-weight: 650; margin-top: 2px; }
.tile .note { color: var(--muted); font-size: 0.78rem; }
.bars { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
.bar-row { display: grid; grid-template-columns: 116px 1fr 76px; align-items: center; gap: 12px; padding: 5px 0; }
.bar-row .name { color: var(--ink-2); font-size: 0.85rem; }
.bar-track { background: var(--grid); border-radius: 4px; height: 10px; position: relative; }
.bar-fill { background: var(--seq-450); border-radius: 4px; height: 10px; }
.bar-row .val { font-size: 0.85rem; font-variant-numeric: tabular-nums; text-align: right; color: var(--ink-2); }
table { min-width: 100%; width: max-content; border-collapse: collapse;
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  font-size: 0.86rem; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--grid);
  vertical-align: middle; white-space: nowrap; }
td.text { white-space: normal; max-width: 420px; }
th { color: var(--ink-2); font-weight: 600; background: var(--page); }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 0.82rem; }
.status .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.status.ok .dot { background: var(--good); }
.status.warn .dot { background: var(--warning); }
.status.bad .dot { background: var(--critical); }
.status.ok { color: var(--good); }
.status.bad { color: var(--critical); }
.tag { display: inline-block; border: 1px solid var(--axis); border-radius: 999px;
  padding: 0 7px; font-size: 0.74rem; color: var(--ink-2); }
.mono { font-variant-numeric: tabular-nums; }
footer { margin-top: 48px; color: var(--muted); font-size: 0.8rem; }
.scroll { overflow-x: auto; }
@media (max-width: 640px) {
  .bar-row { grid-template-columns: 92px 1fr 64px; }
  .tile .value { font-size: 1.55rem; }
}
"""


def render(db: Database, *, as_of: str | None = None) -> str:
    """단일 파일 HTML 보고서를 생성한다."""
    registry = load_registry()
    report = assess(db, as_of=as_of)
    summary = report.summary()
    controls = control_matrix(db, as_of=as_of)
    processes = process_matrix(db)
    scorecard = indicators.scorecard(db)

    parts: list[str] = []
    parts.append(
        f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RQMS 적합성 보고서</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>ISO 22163:2023 철도용 품질경영시스템 적합성 보고서</h1>
  <p>기준일 {escape(str(summary["as_of"]))} · 조항 {summary["clauses_total"]}개 ·
     Annex A 프로세스 {len(registry.processes)}개 · 통제 {len(registry.controls)}개</p>
</header>
"""
    )

    # ------------------------------------------------------------- 요약 타일
    gap_state = _state(summary["gaps"] == 0)
    finding_state = _state(summary["control_findings"] == 0)
    kpi_rows = [r for r in scorecard if r["is_kpi"]]
    kpi_met = sum(1 for r in kpi_rows if r["met"])
    parts.append(
        f"""<section>
  <h2>요약</h2>
  <p class="hint">적합 = 구현 모듈 존재 + 강제 통제 위반 없음 + 요구 증거 보유</p>
  <div class="tiles">
    <div class="tile">
      <div class="label">적용 조항 적합률</div>
      <div class="value">{summary["conformity_rate_pct"]}%</div>
      <div class="note">적용 {summary["clauses_applicable"]}개 중
        적합 {summary["conformant"]}개</div>
    </div>
    <div class="tile">
      <div class="label">필수(shall) 적합률</div>
      <div class="value">{summary["mandatory_conformity_rate_pct"]}%</div>
      <div class="note">shall 및 조건부 shall 조항 기준</div>
    </div>
    <div class="tile">
      <div class="label">조항 갭</div>
      <div class="value">{summary["gaps"]}</div>
      <div class="note">{_status_html(gap_state, "갭 없음" if summary["gaps"] == 0 else "시정조치 필요")}</div>
    </div>
    <div class="tile">
      <div class="label">통제 위반</div>
      <div class="value">{summary["control_findings"]}</div>
      <div class="note">{_status_html(finding_state, f"중 {summary['major_findings']} / 경 {summary['minor_findings']}")}</div>
    </div>
    <div class="tile">
      <div class="label">KPI 목표 달성</div>
      <div class="value">{kpi_met}/{len(kpi_rows)}</div>
      <div class="note">5.3.1 a) 최고경영자 지정 KPI</div>
    </div>
  </div>
</section>
"""
    )

    # ------------------------------------------------------- 장별 적합률 (막대)
    chapter_rows = []
    for chapter, name in CHAPTERS.items():
        items = [
            a
            for a in report.applicable
            if a.clause.id.split(".")[0] == chapter
        ]
        if not items:
            continue
        ok = sum(1 for a in items if a.status == "conformant")
        chapter_rows.append((f"{chapter}. {name}", ok, len(items)))

    bars = "\n".join(
        f"""    <div class="bar-row">
      <div class="name">{escape(label)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{round(ok / total * 100, 1)}%"></div></div>
      <div class="val">{ok}/{total}</div>
    </div>"""
        for label, ok, total in chapter_rows
    )
    parts.append(
        f"""<section>
  <h2>장별 적합 조항</h2>
  <p class="hint">각 행의 숫자는 적합 조항 수 / 적용 조항 수</p>
  <div class="bars">
{bars}
  </div>
</section>
"""
    )

    # ------------------------------------------------------------------ 갭 목록
    if report.gaps:
        gap_rows = "\n".join(
            f"""    <tr>
      <td class="mono">{escape(a.clause.id)}</td>
      <td class="text">{escape(a.clause.title_ko)}</td>
      <td><span class="tag">{escape(a.clause.obligation)}</span></td>
      <td class="text">{escape(", ".join(EVIDENCE_SOURCES.get(k, ("", "", k))[2] for k in a.missing_evidence)) or "-"}</td>
      <td class="text">{escape("; ".join(f.detail for f in a.control_findings)) or "-"}</td>
    </tr>"""
            for a in report.gaps
        )
        parts.append(
            f"""<section>
  <h2>갭 목록 — 시정조치 대상</h2>
  <p class="hint">10.2 에 따라 시정조치를 등록하고 효과성을 검토해야 합니다</p>
  <div class="scroll"><table>
    <tr><th>조항</th><th>제목</th><th>의무</th><th>증거 누락</th><th>통제 위반</th></tr>
{gap_rows}
  </table></div>
</section>
"""
        )

    # ------------------------------------------------------- Annex A 프로세스
    process_rows = "\n".join(
        f"""    <tr>
      <td class="mono">{escape(str(p["code"]))}</td>
      <td class="text">{escape(str(p["name"]))}</td>
      <td class="mono">{escape(str(p["clause"]))}</td>
      <td><span class="tag">{escape(_obligation_label(str(p["obligation"])))}</span></td>
      <td>{escape(str(p["owner"] or "-"))}</td>
      <td>{escape(", ".join(p["indicators"]))}</td>
      <td class="mono">{escape(str(p["last_process_review"] or "-"))}</td>
      <td class="mono">{escape(str(p["last_internal_audit"] or "-"))}</td>
      <td>{_status_html(_state(bool(p["registered"])), "등록" if p["registered"] else "미등록")}</td>
    </tr>"""
        for p in processes
    )
    parts.append(
        f"""<section>
  <h2>Annex A 프로세스 현황</h2>
  <p class="hint">필수(A.1) {len(registry.mandatory_processes())}개 ·
     권고(A.2) {len(registry.recommended_processes())}개 —
     프로세스 검토는 9.4, 내부심사는 9.2.3.2 주기를 따릅니다</p>
  <div class="scroll"><table>
    <tr><th>코드</th><th>프로세스</th><th>근거 조항</th><th>구분</th><th>오너</th>
        <th>성과지표</th><th>최근 프로세스검토</th><th>최근 내부심사</th><th>등록</th></tr>
{process_rows}
  </table></div>
</section>
"""
    )

    # -------------------------------------------------------------- PI 스코어카드
    pi_rows = "\n".join(
        f"""    <tr>
      <td class="mono">{escape(str(r["code"]))}</td>
      <td class="text">{escape(str(r["title"]))}</td>
      <td><span class="tag">{"KPI" if r["is_kpi"] else "PI"}</span></td>
      <td class="num">{r["target"]}{escape(str(r["unit"]))}</td>
      <td class="num">{"-" if r["value"] is None else f'{r["value"]}{escape(str(r["unit"]))}'}</td>
      <td>{_status_html(_met_state(r["met"]), _met_label(r["met"]))}</td>
      <td class="mono">{escape(str(r["period"] or "-"))}</td>
      <td>{escape(", ".join(r["processes"]))}</td>
    </tr>"""
        for r in scorecard
    )
    parts.append(
        f"""<section>
  <h2>성과지표 스코어카드</h2>
  <p class="hint">9.1.1.1.1 — 목표 미달 KPI 는 9.1.3.1 에 따라 시정조치가 필수입니다</p>
  <div class="scroll"><table>
    <tr><th>코드</th><th>지표</th><th>구분</th><th class="num">목표</th>
        <th class="num">실적</th><th>판정</th><th>기간</th><th>관련 프로세스</th></tr>
{pi_rows}
  </table></div>
</section>
"""
    )

    # ------------------------------------------------------------- 통제 매트릭스
    control_rows = "\n".join(
        f"""    <tr>
      <td class="mono">{escape(str(c["control"]))}</td>
      <td><span class="tag">{escape(str(c["kind"]))}</span></td>
      <td><span class="tag">{escape(str(c["severity"]))}</span></td>
      <td class="text">{escape(str(c["title"]))}</td>
      <td class="mono">{escape(", ".join(c["clauses"]))}</td>
      <td>{_status_html(_state(c["violations"] == 0), "0" if c["violations"] == 0 else f'{c["violations"]}건')}</td>
    </tr>"""
        for c in controls
    )
    parts.append(
        f"""<section>
  <h2>통제 매트릭스</h2>
  <p class="hint">invariant 통제는 업무 처리 시점에 강제되고, audit 통제는 상태 점검으로 검증됩니다</p>
  <div class="scroll"><table>
    <tr><th>통제</th><th>유형</th><th>중요도</th><th>내용</th><th>근거 조항</th><th>위반</th></tr>
{control_rows}
  </table></div>
</section>
"""
    )

    # ------------------------------------------------------------ 조항 추적성
    clause_rows = "\n".join(
        f"""    <tr>
      <td class="mono">{escape(a.clause.id)}</td>
      <td class="text">{escape(a.clause.title_ko)}</td>
      <td><span class="tag">{escape(a.clause.obligation)}</span></td>
      <td><span class="tag">{escape("ISO 9001" if a.clause.source == "iso9001" else "22163")}</span></td>
      <td>{escape(", ".join(a.clause.processes)) or "-"}</td>
      <td class="mono">{escape(", ".join(a.clause.controls)) or "-"}</td>
      <td class="num">{len(a.clause.documented_info) - len(a.missing_evidence)}/{len(a.clause.documented_info)}</td>
      <td>{_status_html(_state(a.status == "conformant"), _clause_label(a.status))}</td>
    </tr>"""
        for a in report.assessments
    )
    parts.append(
        f"""<section>
  <h2>조항 추적성 매트릭스</h2>
  <p class="hint">조항 → 프로세스 → 통제 → 증거. 증거 열은 보유 증거 수 / 요구 증거 수</p>
  <div class="scroll"><table>
    <tr><th>조항</th><th>제목</th><th>의무</th><th>출처</th><th>프로세스</th>
        <th>통제</th><th class="num">증거</th><th>판정</th></tr>
{clause_rows}
  </table></div>
</section>
"""
    )

    parts.append(
        f"""<footer>
  생성: rqms {escape(today())} · 근거: ISO 22163:2023 (ISO 9001:2015 요구사항 포함) ·
  본 보고서는 조직의 RQMS 데이터베이스 상태에서 자동 생성되었습니다.
</footer>
</div>
</body>
</html>
"""
    )
    return "".join(parts)


def _state(ok: bool) -> str:
    return "ok" if ok else "bad"


def _met_state(met: object) -> str:
    if met is None:
        return "warn"
    return "ok" if met else "bad"


def _met_label(met: object) -> str:
    if met is None:
        return "미측정"
    return "달성" if met else "미달"


def _clause_label(status: str) -> str:
    return {"conformant": "적합", "gap": "갭", "not_applicable": "비적용"}[status]


def _obligation_label(obligation: str) -> str:
    return {
        "mandatory": "필수",
        "mandatory_conditional": "조건부 필수",
        "recommended": "권고",
    }.get(obligation, obligation)


def _status_html(state: str, label: str) -> str:
    """상태는 색만으로 표현하지 않고 점 + 라벨을 함께 제공한다."""
    return f'<span class="status {state}"><span class="dot"></span>{escape(label)}</span>'
