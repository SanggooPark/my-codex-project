# CLAUDE.md

ISO 22163:2023 철도용 품질경영시스템(RQMS). 외부 의존성 없이 표준 라이브러리만
사용하며, 요구사항 레지스트리·업무 로직·QMS 문서를 하나의 저장소에서 관리한다.

응답과 코드 주석·오류 메시지는 **한국어**로 작성한다.

## 실행

`PYTHONPATH=src` 가 없으면 `ModuleNotFoundError: rqms` 가 난다. 매 터미널마다 필요하다.

```bash
export PYTHONPATH=src

python -m rqms init --db rqms.db --seed     # DB 생성 + 시연 조직(한빛레일) 구축
python -m rqms serve --db rqms.db           # 운영 화면 http://127.0.0.1:8000
python -m rqms conformity --db rqms.db      # 조항별 적합성 평가 (갭 있으면 종료코드 1)
python -m rqms check --db rqms.db           # audit 통제 상태 점검
```

- `init --seed` 는 **이미 시드된 DB 에 다시 실행하면 거부된다**(사번 중복). 재구축은 `--reset`.
- `serve` 는 종료할 때까지 터미널을 점유한다. 다른 명령은 새 탭에서 실행한다.
- `serve` 는 인증이 없다. `--host` 로 외부에 노출하지 않는다.

## 커밋 전 검증 (3개 모두 통과해야 함)

```bash
PYTHONPATH=src python -m unittest discover -s tests
python tools/generate_qms_docs.py --check
ruff check .
```

CI 는 Python **3.9 / 3.11 / 3.13** 에서 동일하게 돌린다. 3.9 를 깨뜨리기 쉬우므로
문법에 확신이 없으면 최소 버전으로도 실행해 본다.

## 절대 깨뜨리면 안 되는 규칙

**1. 외부 의존성 금지.** `dependencies = []` 를 유지한다. 설치 없이 바로 돌아가는 것이
이 프로젝트의 전제다. `ruff` 는 린트 전용이며 런타임 의존성이 아니다.

**2. 레지스트리가 단일 진실 공급원.** 조항·프로세스·지표·통제는 `src/rqms/data/` 의
JSON 에만 정의한다. `qms/20_processes/`, `qms/40_indicators/` 의 문서는
`tools/generate_qms_docs.py` 가 **생성**하므로 직접 편집하지 않는다. 내용을 바꾸려면
레지스트리나 생성기를 고치고 다시 생성한다. 손으로 고치면 CI 의 `--check` 가 잡는다.

**3. 모든 쓰기는 `rqms.services.*` 를 통과한다.** CLI 도 웹 화면도 서비스 함수를 호출할
뿐이며, 화면 전용 저장 경로를 만들지 않는다. 통제를 우회하는 입력 경로가 생기면
"적합률 100%" 라는 숫자가 무의미해진다.

**4. 통제는 `enforce()` 로 강제한다.** 서비스 계층에서 조건 위반 시 `ControlViolation`
을 던진다(`src/rqms/services/_base.py`). 통제를 새로 만들면 `data/controls.json` 에
등록하고 조항과 연결해야 한다 — 연결되지 않은 통제는 `validate_registry()` 가 거부한다.

**5. Python 3.9 호환.** `from __future__ import annotations` 덕분에 **애노테이션**에는
`X | None` 을 써도 되지만, **런타임에 평가되는 위치**(타입 별칭, `TypeVar` 인자,
`cast()` 등)에는 `Optional[X]` 를 써야 한다. 실제로 `checks.py` 의 `CheckFn` 별칭이
이 문제로 3.9 에서 `TypeError` 를 냈다.

```python
CheckFn = Callable[[Database, Optional[str]], list[str]]   # 별칭은 런타임 평가 → Optional
def run(db: Database, as_of: str | None) -> None: ...      # 애노테이션은 PEP 604 가능
```

## 구조

```
src/rqms/
├── data/              레지스트리 — 조항 170 · 프로세스 29 · 지표 21 · 통제 60 · 테이블 74
├── services/          업무 로직 27개 모듈 + _base.py(enforce)
├── web/               운영 화면 — actions(폼 165개) · views(HTML) · server(라우팅)
├── standard.py        레지스트리 로더 + 정합성 검증
├── db.py              SQLite 저장계층, 기록 무결성 봉인(7.5.3.2)
├── checks.py          상태 점검 43개 (audit 통제 29개 전부 + invariant 14개 이중 확인)
├── conformity.py      조항-통제-증거 추적 및 갭 분석 (증거원 115종)
└── cli.py             python -m rqms

qms/                   QMS 문서체계 (일부는 생성물 — 규칙 2 참조)
tools/                 문서 생성기
tests/                 test_registry / test_controls / test_system / test_web
```

**웹 폼은 자동 생성된다.** `web/actions.py` 가 서비스 함수의 시그니처를 `inspect` 로
읽어 필드를 만든다. 서비스 함수에 인자를 추가하면 화면에도 자동으로 나타나므로,
폼을 손으로 맞출 필요가 없다. 한글 라벨·선택지·참조 테이블만 `overrides` 로 보강한다.
새 식별자를 만드는 액션(`nc_no`, `po_no` 등)은 `creates=` 로 지정해야 기존 기록을
고르는 드롭다운이 아니라 자유 입력으로 렌더링된다.

## 테스트 관점

수치(갭 0, 적합률 100%)가 의미를 가지려면 **빈 시스템에서는 갭이 나와야** 한다.
`test_system.py::EmptySystemTest` 가 이를 고정한다. 통제를 추가하면
`test_controls.py` 에 "위반이 실제로 거부되는지"를 함께 넣는다. 통과만 확인하는
테스트는 통제가 사라져도 초록색으로 남는다.

## 작업 방식

- 개발 브랜치: `claude/lucid-wozniak-4xo0f9` ([PR #1](https://github.com/SanggooPark/my-codex-project/pull/1)). 다른 브랜치에 푸시하지 않는다.
- PR 은 요청받았을 때만 만든다.
- 한글 텍스트를 소스에서 스크립트로 일괄 수정할 때 주의: `ast` 의 `col_offset` 은
  문자 수가 아니라 **UTF-8 바이트 오프셋**이다. 문자 기준으로 자르면 코드가 깨진다.
