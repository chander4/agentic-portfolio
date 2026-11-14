"""Error parser extracts compiler/stack-trace diagnostics."""

from __future__ import annotations

from self_healing_react.errors import parse_exception, parse_traceback_text


def test_parse_syntax_error_from_compile() -> None:
    try:
        compile('result = "hello', "<agent-snippet>", "exec")
    except SyntaxError as exc:
        parsed = parse_exception(exc)

    assert parsed.exception_type == "SyntaxError"
    assert parsed.lineno is not None
    assert parsed.offset is not None
    assert "Close unterminated" in parsed.hint or "syntax" in parsed.hint.lower()
    msg = parsed.format_heal_message(
        tool="compile_python",
        arguments={"source": 'result = "hello', "mode": "exec"},
    )
    assert msg.startswith("HEAL_ERROR")
    assert "lineno:" in msg
    assert "traceback:" in msg


def test_parse_zero_division() -> None:
    try:
        _ = 1 / 0
    except ZeroDivisionError as exc:
        parsed = parse_exception(exc)

    assert parsed.exception_type == "ZeroDivisionError"
    assert "zero" in parsed.hint.lower()


def test_parse_traceback_text() -> None:
    text = (
        '  File "<agent-snippet>", line 1\n'
        '    result = "hello\n'
        "             ^\n"
        "SyntaxError: unterminated string literal (detected at line 1)"
    )
    parsed = parse_traceback_text(text)
    assert parsed.exception_type == "SyntaxError"
    assert parsed.lineno == 1
