"""RQMS 예외 정의."""

from __future__ import annotations


class RqmsError(Exception):
    """RQMS 기본 예외."""


class NotFound(RqmsError):
    """요청한 레코드를 찾을 수 없음."""


class ControlViolation(RqmsError):
    """통제(control) 위반.

    ISO 22163 요구사항을 강제하는 지점에서 발생한다. 위반 시 해당 업무 트랜잭션은
    거부되며, 통제 ID와 근거 조항이 함께 보고된다.
    """

    def __init__(self, control_id: str, message: str, clauses: tuple[str, ...] = ()):
        self.control_id = control_id
        self.clauses = tuple(clauses)
        clause_txt = f" [조항 {', '.join(self.clauses)}]" if self.clauses else ""
        super().__init__(f"{control_id}{clause_txt}: {message}")
