"""RQMS 운영 CLI.

사용 예
    python -m rqms init --db rqms.db --seed
    python -m rqms conformity --db rqms.db
    python -m rqms check --db rqms.db
    python -m rqms matrix clause --db rqms.db
    python -m rqms report --db rqms.db --out docs/rqms-report.html
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, checks, conformity
from . import report as report_mod
from .db import Database, open_database
from .errors import RqmsError
from .seed import build
from .services import indicators
from .standard import load_registry

DEFAULT_DB = "rqms.db"

#: `rqms register <name>` 으로 조회할 수 있는 등록부
REGISTERS: dict[str, tuple[str, str]] = {
    "document": ("document", "문서 등록부 (7.5.3.3)"),
    "process": ("process_instance", "프로세스 등록부 (4.4.3)"),
    "risk": ("risk_entry", "리스크·기회 등록부 (6.1.3.1)"),
    "competence": ("competence", "역량 기록 (7.2.1.1)"),
    "measuring-resource": ("measuring_resource", "측정자원 등록부 (7.1.5.3)"),
    "tender": ("tender", "입찰 등록부 (8.1.2)"),
    "requirement": ("requirement", "요구사항 등록부 (8.2.5)"),
    "project": ("project", "프로젝트 등록부 (8.1.3)"),
    "config-item": ("config_item", "형상항목 등록부 (8.1.4.1)"),
    "baseline": ("baseline", "형상 기준선 (8.1.4.1)"),
    "change": ("change_request", "변경요청 등록부 (8.1.4.2)"),
    "design": ("design", "설계 등록부 (8.3)"),
    "supplier": ("supplier", "승인 공급자 등록부 (8.4.1.1.4)"),
    "purchase-order": ("purchase_order", "구매발주 등록부 (8.4.3)"),
    "delegation": ("verification_delegation", "검증 위임 등록부 (8.4.2.2)"),
    "production-order": ("production_order", "생산 오더 (8.5.1)"),
    "special-process": ("special_process", "특수공정 등록부 (8.5.1.3)"),
    "equipment": ("production_equipment", "생산설비 등록부 (8.5.1.4)"),
    "item": ("traceable_item", "추적 품목 등록부 (8.5.2)"),
    "nonconformity": ("nonconformity", "부적합 등록부 (8.7.3 b)"),
    "concession": ("concession", "특채 등록부 (8.7.3 d)"),
    "capa": ("capa", "시정조치 등록부 (10.2.3)"),
    "fai": ("fai", "FAI 등록부 (8.9)"),
    "rams": ("rams_objective", "RAMS 목표 등록부 (8.8.2)"),
    "obsolescence": ("obsolescence_risk", "단산 리스크 등록부 (8.10)"),
    "audit": ("internal_audit", "내부심사 등록부 (9.2)"),
    "management-review": ("management_review", "경영검토 기록 (9.3)"),
    "process-review": ("process_review", "프로세스 검토 기록 (9.4)"),
    "complaint": ("complaint", "고객 불만 등록부 (9.1.2.1)"),
    "violation": ("control_violation_log", "통제 위반 로그"),
}


# ------------------------------------------------------------------ 출력 헬퍼
def _emit(data: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("  (해당 없음)")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print("  " + " | ".join(c.ljust(widths[c]) for c in columns))
    print("  " + "-+-".join("-" * widths[c] for c in columns))
    for row in rows:
        print("  " + " | ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


# ------------------------------------------------------------------- 명령 구현
def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.db)
    existed = path.exists()
    db = open_database(path, create=True)
    print(f"데이터베이스 {'갱신' if existed else '생성'}: {path}")
    if args.seed:
        summary = build(db)
        print("시연 데이터 구축 완료:")
        for key, value in summary.items():
            print(f"  - {key}: {value}")
    db.close()
    return 0


def cmd_conformity(args: argparse.Namespace) -> int:
    with _db(args) as db:
        assessment = conformity.assess(db, as_of=args.as_of)
        summary = assessment.summary()
        gaps = conformity.gap_report(db, as_of=args.as_of)
        if args.json:
            _emit({"summary": summary, "gaps": gaps}, as_json=True)
            return 0 if not gaps else 1

        print(f"ISO 22163:2023 적합성 평가 — 기준일 {summary['as_of']}")
        print(f"  조항 총계            : {summary['clauses_total']}")
        print(f"  적용 조항            : {summary['clauses_applicable']}")
        print(f"  비적용 조항          : {summary['clauses_not_applicable']}")
        print(f"  적합                 : {summary['conformant']}")
        print(f"  갭                   : {summary['gaps']}")
        print(f"  적합률               : {summary['conformity_rate_pct']}%")
        print(f"  필수(shall) 적합률   : {summary['mandatory_conformity_rate_pct']}%")
        print(
            f"  통제 위반            : {summary['control_findings']}건"
            f" (중 {summary['major_findings']} / 경 {summary['minor_findings']})"
        )
        if gaps:
            print("\n갭 목록:")
            for gap in gaps:
                print(f"  [{gap['clause']}] {gap['title']} ({gap['obligation']})")
                if gap["missing_evidence"]:
                    print(f"      증거 누락: {', '.join(gap['missing_evidence'])}")
                if gap["missing_modules"]:
                    print(f"      구현 누락: {', '.join(gap['missing_modules'])}")
                for finding in gap["control_findings"]:
                    print(f"      {finding}")
        else:
            print("\n갭 없음 — 모든 적용 조항이 구현·통제·증거를 갖추고 있습니다.")
        return 0 if not gaps else 1


def cmd_check(args: argparse.Namespace) -> int:
    with _db(args) as db:
        findings = checks.run_checks(
            db, as_of=args.as_of, control_ids=args.control or None
        )
        summary = checks.summary(findings)
        if args.json:
            _emit(
                {
                    "summary": summary,
                    "findings": [
                        {
                            "control": f.control_id,
                            "severity": f.severity,
                            "title": f.title,
                            "clauses": list(f.clauses),
                            "detail": f.detail,
                        }
                        for f in findings
                    ],
                },
                as_json=True,
            )
            return 0 if not findings else 1
        print(f"통제 상태 점검 — 위반 {summary['total']}건 "
              f"(중 {summary['major']} / 경 {summary['minor']})")
        for finding in findings:
            print(f"  {finding}")
        if not findings:
            print("  위반 없음.")
        return 0 if not findings else 1


def cmd_matrix(args: argparse.Namespace) -> int:
    with _db(args) as db:
        if args.kind == "clause":
            rows = conformity.traceability_matrix(db)
            if args.json:
                _emit(rows, as_json=True)
                return 0
            print("조항 - 프로세스 - 통제 - 구현 - 증거 추적 매트릭스")
            _table(
                [
                    {
                        "clause": r["clause"],
                        "obl": r["obligation"],
                        "src": r["source"],
                        "processes": ",".join(r["processes"]) or "-",
                        "controls": ",".join(r["controls"]) or "-",
                        "evidence": f"{sum(1 for e in r['evidence'] if e['present'])}"
                        f"/{len(r['evidence'])}",
                        "title": r["title"][:38],
                    }
                    for r in rows
                ],
                ["clause", "obl", "src", "processes", "controls", "evidence", "title"],
            )
        elif args.kind == "control":
            rows = conformity.control_matrix(db, as_of=args.as_of)
            if args.json:
                _emit(rows, as_json=True)
                return 0
            print("통제 - 조항 - 위반 현황")
            _table(
                [
                    {
                        "control": r["control"],
                        "kind": r["kind"],
                        "sev": r["severity"],
                        "viol": r["violations"],
                        "clauses": ",".join(r["clauses"])[:30],
                        "title": r["title"][:44],
                    }
                    for r in rows
                ],
                ["control", "kind", "sev", "viol", "clauses", "title"],
            )
        else:
            rows = conformity.process_matrix(db)
            if args.json:
                _emit(rows, as_json=True)
                return 0
            print("Annex A 프로세스 현황")
            _table(
                [
                    {
                        "code": r["code"],
                        "clause": r["clause"],
                        "obligation": r["obligation"],
                        "owner": r["owner"] or "-",
                        "PI": ",".join(r["indicators"]),
                        "review": r["last_process_review"] or "-",
                        "audit": r["last_internal_audit"] or "-",
                        "name": r["name"][:26],
                    }
                    for r in rows
                ],
                ["code", "clause", "obligation", "owner", "PI", "review", "audit", "name"],
            )
        return 0


def cmd_indicators(args: argparse.Namespace) -> int:
    with _db(args) as db:
        rows = indicators.scorecard(db, period=args.period)
        if args.json:
            _emit(rows, as_json=True)
            return 0
        print(f"성과지표 스코어카드{f' — {args.period}' if args.period else ''}")
        _table(
            [
                {
                    "code": r["code"],
                    "kpi": "KPI" if r["is_kpi"] else "PI",
                    "target": f"{r['target']}{r['unit']}",
                    "value": "-" if r["value"] is None else f"{r['value']}{r['unit']}",
                    "met": {True: "달성", False: "미달", None: "미측정"}[r["met"]],
                    "period": r["period"] or "-",
                    "title": str(r["title"])[:30],
                }
                for r in rows
            ],
            ["code", "kpi", "target", "value", "met", "period", "title"],
        )
        return 0


def cmd_clause(args: argparse.Namespace) -> int:
    registry = load_registry()
    try:
        clause = registry.clause(args.clause_id)
    except KeyError:
        print(f"조항 {args.clause_id} 은 레지스트리에 없습니다.", file=sys.stderr)
        return 2
    with _db(args) as db:
        detail = {
            "id": clause.id,
            "title_ko": clause.title_ko,
            "title_en": clause.title_en,
            "obligation": clause.obligation,
            "source": clause.source,
            "processes": list(clause.processes),
            "controls": [
                {
                    "id": cid,
                    "kind": registry.control(cid).kind,
                    "severity": registry.control(cid).severity,
                    "title": registry.control(cid).title,
                }
                for cid in clause.controls
            ],
            "modules": list(clause.modules),
            "evidence": [
                {
                    "key": key,
                    "label": conformity.EVIDENCE_SOURCES.get(key, ("", "", key))[2],
                    "present": conformity.evidence_present(db, key),
                }
                for key in clause.documented_info
            ],
        }
        if args.json:
            _emit(detail, as_json=True)
            return 0
        print(f"[{clause.id}] {clause.title_ko}")
        print(f"  영문     : {clause.title_en}")
        print(f"  의무     : {clause.obligation} ({clause.source})")
        print(f"  프로세스 : {', '.join(clause.processes) or '-'}")
        print(f"  구현     : {', '.join(clause.modules) or '-'}")
        print("  통제     :")
        for control in detail["controls"]:
            print(f"    - {control['id']} [{control['kind']}/{control['severity']}]"
                  f" {control['title']}")
        if not detail["controls"]:
            print("    - (없음 — 증거 기반으로 평가)")
        print("  증거     :")
        for evidence in detail["evidence"]:
            mark = "O" if evidence["present"] else "X"
            print(f"    [{mark}] {evidence['label']} ({evidence['key']})")
        if not detail["evidence"]:
            print("    - (문서화된 정보 요구 없음)")
        return 0


def cmd_register(args: argparse.Namespace) -> int:
    entry = REGISTERS.get(args.name)
    if entry is None:
        print(f"알 수 없는 등록부: {args.name}", file=sys.stderr)
        print(f"사용 가능: {', '.join(sorted(REGISTERS))}", file=sys.stderr)
        return 2
    table, label = entry
    with _db(args) as db:
        rows = [dict(r) for r in db.query(f"SELECT * FROM {table} LIMIT ?", (args.limit,))]
        if args.json:
            _emit(rows, as_json=True)
            return 0
        print(f"{label} — {len(rows)}건")
        if not rows:
            print("  (비어 있음)")
            return 0
        columns = [c for c in rows[0] if c != "id"][: args.columns]
        _table(
            [{c: _short(r.get(c)) for c in columns} for r in rows],
            columns,
        )
        return 0


def cmd_report(args: argparse.Namespace) -> int:
    with _db(args) as db:
        html = report_mod.render(db, as_of=args.as_of)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"적합성 보고서 생성: {out} ({len(html):,} bytes)")
        return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """운영 웹 화면을 기동한다."""
    from .web.server import serve

    serve(args.db, host=args.host, port=args.port)
    return 0


def cmd_processes(args: argparse.Namespace) -> int:
    with _db(args) as db:
        rows = conformity.process_matrix(db)
        if args.json:
            _emit(rows, as_json=True)
            return 0
        mandatory = [r for r in rows if str(r["obligation"]).startswith("mandatory")]
        recommended = [r for r in rows if r["obligation"] == "recommended"]
        print(f"Annex A.1 필수 프로세스 {len(mandatory)}개 / A.2 권고 프로세스"
              f" {len(recommended)}개")
        for group, title in ((mandatory, "필수(A.1)"), (recommended, "권고(A.2)")):
            print(f"\n{title}")
            for row in group:
                indent = "  " * int(row["level"])
                status = "등록" if row["registered"] else "미등록"
                print(
                    f"  {indent}{row['code']:4} {row['name']} "
                    f"[{row['clause']}] {status} / 오너 {row['owner'] or '-'}"
                )
        return 0


def _short(value: Any, width: int = 24) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def _db(args: argparse.Namespace) -> Database:
    path = Path(args.db)
    if not path.exists():
        raise RqmsError(
            f"데이터베이스 {path} 가 없습니다. 먼저 `python -m rqms init --db {path}` 를"
            " 실행하세요."
        )
    return open_database(path)


# ---------------------------------------------------------------------- 파서
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rqms",
        description="ISO 22163:2023 철도용 품질경영시스템(RQMS) 운영 도구",
    )
    parser.add_argument("--version", action="version", version=f"rqms {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser, *, as_of: bool = True) -> None:
        p.add_argument("--db", default=DEFAULT_DB, help="데이터베이스 경로")
        p.add_argument("--json", action="store_true", help="JSON 출력")
        if as_of:
            p.add_argument("--as-of", dest="as_of", help="평가 기준일 (YYYY-MM-DD)")

    p_init = sub.add_parser("init", help="데이터베이스 생성 및 시연 데이터 구축")
    p_init.add_argument("--db", default=DEFAULT_DB, help="데이터베이스 경로")
    p_init.add_argument("--seed", action="store_true", help="시연용 RQMS 데이터 구축")
    p_init.set_defaults(func=cmd_init)

    p_conf = sub.add_parser("conformity", help="조항별 적합성 평가 및 갭 보고")
    add_common(p_conf)
    p_conf.set_defaults(func=cmd_conformity)

    p_check = sub.add_parser("check", help="통제 상태 점검")
    add_common(p_check)
    p_check.add_argument(
        "--control", action="append", help="점검할 통제 ID (반복 지정 가능)"
    )
    p_check.set_defaults(func=cmd_check)

    p_matrix = sub.add_parser("matrix", help="추적성 매트릭스 출력")
    p_matrix.add_argument("kind", choices=["clause", "control", "process"])
    add_common(p_matrix)
    p_matrix.set_defaults(func=cmd_matrix)

    p_ind = sub.add_parser("indicators", help="성과지표 스코어카드")
    add_common(p_ind, as_of=False)
    p_ind.add_argument("--period", help="측정 기간 (예: 2026-09)")
    p_ind.set_defaults(func=cmd_indicators)

    p_clause = sub.add_parser("clause", help="조항 상세 및 증거 현황")
    p_clause.add_argument("clause_id", help="조항 번호 (예: 8.1.3.1.1)")
    add_common(p_clause, as_of=False)
    p_clause.set_defaults(func=cmd_clause)

    p_reg = sub.add_parser("register", help="등록부 조회")
    p_reg.add_argument("name", help=f"등록부 이름 ({', '.join(sorted(REGISTERS))})")
    p_reg.add_argument("--limit", type=int, default=20)
    p_reg.add_argument("--columns", type=int, default=6)
    add_common(p_reg, as_of=False)
    p_reg.set_defaults(func=cmd_register)

    p_proc = sub.add_parser("processes", help="Annex A 프로세스 계층구조")
    add_common(p_proc, as_of=False)
    p_proc.set_defaults(func=cmd_processes)

    p_report = sub.add_parser("report", help="HTML 적합성 보고서 생성")
    add_common(p_report)
    p_report.add_argument("--out", default="rqms-report.html", help="출력 파일")
    p_report.set_defaults(func=cmd_report)

    p_serve = sub.add_parser("serve", help="운영 웹 화면 기동 (브라우저에서 입력·조회)")
    p_serve.add_argument("--db", default=DEFAULT_DB, help="데이터베이스 경로")
    p_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="바인드 주소 (기본 127.0.0.1 — 인증이 없으므로 외부 노출 금지)",
    )
    p_serve.add_argument("--port", type=int, default=8000, help="포트 (기본 8000)")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RqmsError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        # `| head` 등으로 출력이 끊긴 경우는 정상 종료로 처리한다.
        with contextlib.suppress(Exception):
            sys.stdout.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
