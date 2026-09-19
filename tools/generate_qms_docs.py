#!/usr/bin/env python3
"""표준 레지스트리로부터 QMS 문서화된 정보를 생성한다.

ISO 22163:2023 4.4.3 은 필수·권고 프로세스의 기술서가 4.4.1 a)~e) 를 최소한으로
담도록 요구한다. 프로세스-조항-통제-지표-증거 매핑은 `src/rqms/data` 레지스트리가
단일 진실원천이므로, 프로세스 기술서와 성과지표 정의서는 이 스크립트로 생성하여
레지스트리와 문서가 어긋나지 않게 한다.

사용법
    python tools/generate_qms_docs.py            # qms/ 아래에 생성
    python tools/generate_qms_docs.py --check    # 생성물이 최신인지 검사(CI용)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rqms.conformity import EVIDENCE_SOURCES  # noqa: E402
from rqms.standard import Process, load_registry  # noqa: E402

QMS_DIR = ROOT / "qms"
PROCESS_DIR = QMS_DIR / "20_processes"
INDICATOR_DIR = QMS_DIR / "40_indicators"

BANNER = (
    "> 이 문서는 `tools/generate_qms_docs.py` 가 `src/rqms/data` 레지스트리에서"
    " 생성합니다.\n> 직접 수정하지 말고 레지스트리를 수정한 뒤 재생성하십시오.\n"
)

OBLIGATION_KO = {
    "mandatory": "필수 프로세스 (Annex A.1)",
    "mandatory_conditional": "조건부 필수 프로세스 (Annex A.1)",
    "recommended": "권고 프로세스 (Annex A.2)",
}

ROLE_KO = {
    "quality_director": "품질보증 책임자",
    "operations_director": "운영 총괄",
    "metrology_manager": "계측 관리자",
    "hr_manager": "인사 관리자",
    "pmo_head": "사업관리(PMO) 책임자",
    "configuration_manager": "형상관리 책임자",
    "engineering_director": "기술개발 책임자",
    "procurement_director": "구매 책임자",
    "production_director": "생산 책임자",
    "service_director": "서비스 책임자",
    "rams_manager": "RAMS 관리자",
    "safety_manager": "안전 관리자",
    "sales_director": "영업 책임자",
    "maintenance_manager": "설비 정비 관리자",
}


def process_doc(process: Process) -> str:
    registry = load_registry()
    clauses = registry.clauses_for_process(process.code)
    indicators = registry.indicators_for_process(process.code)
    controls = sorted({c for clause in clauses for c in clause.controls})
    evidence = sorted({e for clause in clauses for e in clause.documented_info})
    children = [p for p in registry.processes if p.parent == process.code]

    lines: list[str] = [
        f"# {process.code} — {process.name_ko}",
        "",
        BANNER,
        "| 항목 | 내용 |",
        "| --- | --- |",
        f"| 문서번호 | RQMS-PRC-{process.code} |",
        f"| 영문명 | {process.name_en} |",
        f"| 근거 조항 | ISO 22163:2023 {process.clause} |",
        f"| 구분 | {OBLIGATION_KO[process.obligation]} |",
        f"| 프로세스 오너 | {ROLE_KO.get(process.owner_role, process.owner_role)}"
        " (5.3.1 b, 5.3.2) |",
        f"| 상위 프로세스 | {process.parent or '없음 (최상위)'} |",
        f"| 하위 프로세스 | {', '.join(p.code for p in children) or '없음'} |",
        f"| 구현 모듈 | `{process.module}` |",
        f"| 프로세스 검토 주기 | {process.review_cycle_months}개월 (9.4) |",
    ]
    if process.applicability_condition:
        lines.append(f"| 적용 조건 | {process.applicability_condition} |")
    lines += ["", "## 1. 목적 및 적용범위", ""]
    lines.append(
        f"본 프로세스는 ISO 22163:2023 {process.clause} 의 요구사항을 충족하기 위해"
        f" {process.name_ko}를 수립·실행·유지한다."
    )
    if process.applicability_condition:
        lines.append("")
        lines.append(f"적용 조건: {process.applicability_condition}")

    lines += [
        "",
        "## 2. 프로세스 정의 (4.4.1 a~e)",
        "",
        "프로세스의 입력·출력, 순서 및 상호작용, 판정기준과 성과지표, 필요자원,"
        " 책임과 권한은 RQMS 데이터베이스의 `process_instance` 레코드에 등록되어 있으며,"
        " 등록 없이는 프로세스를 운영할 수 없다(CTL-038, CTL-039).",
        "",
        "| 4.4.1 항목 | 등록 위치 |",
        "| --- | --- |",
        "| a) 입력·출력 | `process_instance.inputs` / `.outputs` |",
        "| b) 순서 및 상호작용 | `process_instance.sequence_note` |",
        "| c) 판정기준·측정·성과지표 | `process_instance.criteria` 및 아래 5장 성과지표 |",
        "| d) 필요 자원 | `process_instance.resources` |",
        "| e) 책임 및 권한 | `process_instance.owner_id` (프로세스 오너) |",
        "| 4.4.3 f) 리스크기반 통제기준 | `process_instance.risk_criteria` |",
        "",
        "## 3. 관련 요구사항",
        "",
    ]
    if clauses:
        lines += ["| 조항 | 의무 | 출처 | 요구사항 |", "| --- | --- | --- | --- |"]
        for clause in clauses:
            source = "ISO 9001:2015" if clause.source == "iso9001" else "ISO 22163 추가"
            lines.append(
                f"| {clause.id} | {clause.obligation} | {source} | {clause.title_ko} |"
            )
    else:
        lines.append("본 프로세스에 직접 연결된 조항이 레지스트리에 없습니다.")

    lines += ["", "## 4. 강제 통제", ""]
    if controls:
        lines += ["| 통제 | 유형 | 중요도 | 내용 | 근거 조항 |", "| --- | --- | --- | --- | --- |"]
        for control_id in controls:
            control = registry.control(control_id)
            lines.append(
                f"| {control.id} | {control.kind} | {control.severity} |"
                f" {control.title} | {', '.join(control.clauses)} |"
            )
        lines += [
            "",
            "`invariant` 통제는 업무 처리 시점에 시스템이 강제하며, 위반 시 해당 처리가"
            " 거부되고 `control_violation_log` 에 기록된다. `audit` 통제는"
            " `python -m rqms check` 로 상태를 점검한다.",
        ]
    else:
        lines.append("본 프로세스에는 시스템이 강제하는 통제가 지정되지 않았고,"
                     " 문서화된 정보(증거) 보유로 적합성을 입증한다.")

    lines += ["", "## 5. 성과지표 (4.4.1 c, 9.1.1.1)", ""]
    if indicators:
        lines += [
            "| 지표 | 구분 | 산식 | 목표 | 주기 | 보고 대상 | 조치 책임 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for indicator in indicators:
            kind = "KPI" if indicator.is_kpi else "PI"
            lines.append(
                f"| {indicator.code} {indicator.title_ko} | {kind} |"
                f" {indicator.formula} | {indicator.target}{indicator.unit} |"
                f" {indicator.period} |"
                f" {', '.join(ROLE_KO.get(r, r) for r in indicator.reported_to)} |"
                f" {ROLE_KO.get(indicator.action_owner_role, indicator.action_owner_role)} |"
            )
        lines += [
            "",
            "목표 미달 시 KPI 는 시정조치가 필수이며(9.1.3.1), 그 외 PI 는 프로세스 검토에서"
            " 조치 필요성을 판단한다.",
        ]
    else:
        lines.append("(레지스트리 검증 규칙에 따라 모든 프로세스는 1개 이상의 지표를 가진다)")

    lines += ["", "## 6. 문서화된 정보 (7.5)", ""]
    if evidence:
        lines += ["| 증거 | 저장 위치 |", "| --- | --- |"]
        for key in evidence:
            table, where, label = EVIDENCE_SOURCES.get(key, ("-", "", key))
            location = f"`{table}`" + (f" (조건: `{where}`)" if where else "")
            lines.append(f"| {label} | {location} |")
    else:
        lines.append("본 프로세스가 별도로 요구하는 문서화된 정보는 없다.")

    lines += [
        "",
        "## 7. 프로세스 검토 (9.4)",
        "",
        f"본 프로세스는 {process.review_cycle_months}개월 주기로 프로세스 오너가 주재하여"
        " 검토한다. 검토는 9.4 a)~l) 항목을 모두 다루어야 하며, `rqms.services.review."
        "hold_process_review` 가 항목 누락을 거부한다. 검토 출력은 최고경영자에게"
        " 보고되고 경영검토 입력이 된다(9.3.2.1 b).",
        "",
        "## 8. 운영 명령",
        "",
        "```bash",
        f"python -m rqms clause {clauses[0].id if clauses else process.clause}",
        "python -m rqms matrix process",
        "python -m rqms check",
        "```",
        "",
    ]
    return "\n".join(lines)


def indicator_doc() -> str:
    registry = load_registry()
    lines: list[str] = [
        "# RQMS-PI-001 — 성과지표(PI/KPI) 정의서",
        "",
        BANNER,
        "ISO 22163:2023 9.1.1.1.1 은 각 PI 정의가 a) 관련 프로세스, b) 산식,"
        " c) 목표와 기간, d) 측정 제공자, e) 보고 시점과 대상, f) 조치 정의 책임자,"
        " g) 데이터 출처를 명시할 것을 요구한다. Annex C Table C.1 항목도 함께 채운다.",
        "",
        "## 1. 지표 목록",
        "",
        "| 지표 | 명칭 | 구분 | 근거 | 목표 | 방향 | 주기 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    mandate_ko = {
        "required": "9.1.1.1.1 필수",
        "recommended": "9.1.1.1.2 권고",
        "process_pi": "4.4.1 c) 프로세스 지표",
    }
    direction_ko = {"higher_is_better": "높을수록 좋음", "lower_is_better": "낮을수록 좋음"}
    for indicator in registry.indicators:
        lines.append(
            f"| {indicator.code} | {indicator.title_ko} |"
            f" {'KPI' if indicator.is_kpi else 'PI'} |"
            f" {mandate_ko[indicator.mandate]} ({indicator.mandate_clause}) |"
            f" {indicator.target}{indicator.unit} |"
            f" {direction_ko[indicator.target_direction]} | {indicator.period} |"
        )

    lines += ["", "## 2. 지표별 상세 정의", ""]
    for indicator in registry.indicators:
        lines += [
            f"### {indicator.code} {indicator.title_ko}",
            "",
            "| Table C.1 항목 | 내용 |",
            "| --- | --- |",
            f"| PI 명칭 | {indicator.title_ko} ({indicator.title_en}) |",
            f"| 목적/개선 목표 | {indicator.purpose} |",
            f"| 관련 프로세스 | {', '.join(indicator.processes)} |",
            f"| 프로세스/지표 오너 | {ROLE_KO.get(indicator.owner_role, indicator.owner_role)} |",
            f"| 정의 및 산식 | {indicator.formula} (단위: {indicator.unit}) |",
            f"| 데이터 출처 | {indicator.data_source} |",
            f"| 목표값 및 기간 | {indicator.target}{indicator.unit} / {indicator.period} |",
            f"| 측정 제공자 | {ROLE_KO.get(indicator.measured_by_role, indicator.measured_by_role)} |",
            f"| 보고 대상 및 주기 | {', '.join(ROLE_KO.get(r, r) for r in indicator.reported_to)}"
            f" / {indicator.reporting_frequency} |",
            f"| 조치 정의 책임자 | {ROLE_KO.get(indicator.action_owner_role, indicator.action_owner_role)} |",
            f"| 근거 조항 | {indicator.mandate_clause} |",
            "",
        ]

    lines += [
        "## 3. SMART 원칙 적용 (Annex C.3)",
        "",
        "| 원칙 | 적용 방식 |",
        "| --- | --- |",
        "| Specific | 지표별 산식과 적용 범위를 정의서에 명시하고 전 사업장에 표준 적용 |",
        "| Measurable | 산식이 시스템 데이터로 자동 계산되며 목표값과 실적을 병기 |",
        "| Achievable | 과거 실적 기반으로 도전적이나 달성 가능한 목표를 이해관계자와 합의 |",
        "| Relevant | 품질·시간·원가 중 최소 1개 핵심 동인과 연결 |",
        "| Time framed | 측정 기간과 보고 주기를 명시하여 추세를 관찰 |",
        "",
        "## 4. 목표 미달 시 조치",
        "",
        "- KPI 목표 미달: 시정조치 필수 (9.1.3.1). `CTL-020` 이 강제한다.",
        "- 그 외 PI 목표 미달: 프로세스 검토에서 조치 필요성 판단 (9.1.3.1, 9.4 e).",
        "- 목표 초과 달성: 성과 유지를 위해 요인을 분석한다 (9.1.3.1).",
        "",
        "## 5. 운영 명령",
        "",
        "```bash",
        "python -m rqms indicators --period 2026-09",
        "python -m rqms check --control CTL-020 --control CTL-056",
        "```",
        "",
    ]
    return "\n".join(lines)


def process_index() -> str:
    registry = load_registry()
    lines = [
        "# 프로세스 기술서 목록 (Annex A)",
        "",
        BANNER,
        "ISO 22163:2023 4.4.3 a) 에 따른 프로세스 계층구조이다.",
        "",
        "## 필수 프로세스 (Table A.1)",
        "",
        "| 코드 | 프로세스 | 근거 조항 | 오너 | 기술서 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for process in registry.mandatory_processes():
        indent = "└ " if process.level > 1 else ""
        lines.append(
            f"| {process.code} | {indent}{process.name_ko} | {process.clause} |"
            f" {ROLE_KO.get(process.owner_role, process.owner_role)} |"
            f" [{process.code}](RQMS-PRC-{process.code}.md) |"
        )
    lines += [
        "",
        "## 권고 프로세스 (Table A.2)",
        "",
        "| 코드 | 프로세스 | 근거 조항 | 오너 | 기술서 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for process in registry.recommended_processes():
        indent = "└ " if process.level > 1 else ""
        lines.append(
            f"| {process.code} | {indent}{process.name_ko} | {process.clause} |"
            f" {ROLE_KO.get(process.owner_role, process.owner_role)} |"
            f" [{process.code}](RQMS-PRC-{process.code}.md) |"
        )
    lines.append("")
    return "\n".join(lines)


def generate() -> dict[Path, str]:
    registry = load_registry()
    out: dict[Path, str] = {PROCESS_DIR / "README.md": process_index()}
    for process in registry.processes:
        out[PROCESS_DIR / f"RQMS-PRC-{process.code}.md"] = process_doc(process)
    out[INDICATOR_DIR / "RQMS-PI-001_성과지표정의서.md"] = indicator_doc()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="생성물이 최신인지 확인만 한다(CI용)"
    )
    args = parser.parse_args(argv)

    documents = generate()
    stale: list[Path] = []
    for path, content in documents.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if args.check:
        if stale:
            print("생성물이 레지스트리와 일치하지 않습니다:")
            for path in stale:
                print(f"  - {path.relative_to(ROOT)}")
            print("`python tools/generate_qms_docs.py` 를 실행하십시오.")
            return 1
        print(f"생성물 {len(documents)}건 모두 최신입니다.")
        return 0

    print(f"QMS 문서 {len(documents)}건 생성 완료:")
    for path in sorted(documents):
        print(f"  - {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
