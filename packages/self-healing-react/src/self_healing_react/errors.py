"""Parse stack traces and compile()/SyntaxError messages into heal hints."""

from __future__ import annotations

import re
import traceback
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ParsedError:
    """Structured diagnosis fed back to the model on heal retries."""

    exception_type: str
    message: str
    traceback_text: str
    lineno: int | None = None
    offset: int | None = None
    hint: str = ""

    def format_heal_message(self, *, tool: str, arguments: dict[str, Any]) -> str:
        lines = [
            f"HEAL_ERROR for tool '{tool}':",
            f"  exception: {self.exception_type}: {self.message}",
        ]
        if self.lineno is not None:
            lines.append(f"  lineno: {self.lineno}")
        if self.offset is not None:
            lines.append(f"  offset: {self.offset}")
        if self.hint:
            lines.append(f"  hint: {self.hint}")
        lines.append("  traceback:")
        for tb_line in self.traceback_text.strip().splitlines()[-12:]:
            lines.append(f"    {tb_line}")
        lines.append(f"  previous_arguments: {arguments}")
        lines.append(
            "Rewrite the tool call arguments to fix the failure. "
            "Do not repeat the same broken payload."
        )
        return "\n".join(lines)


def parse_exception(exc: BaseException) -> ParsedError:
    """
    Turn a live exception into a ParsedError.

    Special-cases ``SyntaxError`` (Python's compile() / compiler API surface) so
    lineno/offset are first-class fields the healer can act on.
    """
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    lineno: int | None = None
    offset: int | None = None
    hint = ""

    if isinstance(exc, SyntaxError):
        lineno = exc.lineno
        offset = exc.offset
        hint = _syntax_hint(exc)
    elif isinstance(exc, ZeroDivisionError):
        hint = "Avoid dividing by zero; rewrite the expression."
    elif isinstance(exc, KeyError):
        hint = f"Missing key {exc.args[0]!r}; use a key that exists in the payload."
    elif isinstance(exc, TypeError):
        hint = "Fix argument types or call signature implied by the TypeError."
    elif isinstance(exc, ValueError):
        hint = "Correct the value that failed validation."
    else:
        hint = "Inspect the traceback and correct the failing tool arguments."

    return ParsedError(
        exception_type=type(exc).__name__,
        message=str(exc),
        traceback_text=tb,
        lineno=lineno,
        offset=offset,
        hint=hint,
    )


def parse_traceback_text(text: str) -> ParsedError:
    """Parse a raw traceback / compiler diagnostic string (no live exception)."""
    exception_type = "Error"
    message = text.strip().splitlines()[-1] if text.strip() else "unknown error"
    match = re.search(r"^([A-Za-z_][\w.]*)\s*:\s*(.*)$", message)
    if match:
        exception_type = match.group(1).split(".")[-1]
        message = match.group(2)

    lineno = None
    offset = None
    line_match = re.search(r"line\s+(\d+)", text, flags=re.IGNORECASE)
    if line_match:
        lineno = int(line_match.group(1))
    offset_match = re.search(r"column\s+(\d+)|offset\s+(\d+)", text, flags=re.IGNORECASE)
    if offset_match:
        offset = int(offset_match.group(1) or offset_match.group(2))

    hint = "Inspect the traceback and correct the failing tool arguments."
    if "SyntaxError" in text:
        hint = "Fix the syntax error at the reported lineno/offset before retrying."
    elif "ZeroDivisionError" in text:
        hint = "Avoid dividing by zero; rewrite the expression."

    return ParsedError(
        exception_type=exception_type,
        message=message,
        traceback_text=text,
        lineno=lineno,
        offset=offset,
        hint=hint,
    )


def _syntax_hint(exc: SyntaxError) -> str:
    msg = (exc.msg or "").lower()
    if "was never closed" in msg or "eof" in msg:
        return "Close unterminated strings, brackets, or parentheses."
    if "invalid syntax" in msg:
        return "Fix invalid syntax near the reported lineno/offset."
    if "unexpected eof" in msg:
        return "Complete the truncated expression or statement."
    return "Repair the syntax error reported by compile() before retrying."
