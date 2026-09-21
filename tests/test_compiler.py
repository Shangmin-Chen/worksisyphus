from __future__ import annotations

import subprocess
from pathlib import Path

from worksisyphus import compiler


def test_compile_reports_overfull_hboxes(monkeypatch, tmp_path) -> None:
    stdout = """Overfull \\hbox (90.572pt too wide) in paragraph at lines 127--128
[]
Output written on /tmp/x.pdf (1 page, 1234 bytes).
"""

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        output_dir = Path(next(arg for arg in args if arg.startswith("-output-directory=")).split("=", 1)[1])
        (output_dir / "x.pdf").write_bytes(b"%PDF-fake")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    result = compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    assert result.pages == 1
    assert result.overfull == ("90.6pt too wide at tex line 127",)
    assert result.overfull[0].width_pt == 90.6
    assert result.overfull[0].line == 127
    assert result.overfull[0].exceeds_tolerance(2.0) is True


def test_compile_captures_malformed_width_overfull_as_structured(monkeypatch, tmp_path) -> None:
    """A malformed width token must be captured as structured overfull (fail closed), not skipped."""
    stdout = """Overfull \\hbox (1.2.3pt too wide) in paragraph at lines 40--41
[]
Output written on /tmp/x.pdf (1 page, 1234 bytes).
"""

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        output_dir = Path(next(arg for arg in args if arg.startswith("-output-directory=")).split("=", 1)[1])
        (output_dir / "x.pdf").write_bytes(b"%PDF-fake")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    result = compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    assert result.pages == 1
    assert len(result.overfull) == 1
    assert result.overfull[0].width_pt is None
    assert result.overfull[0].line == 40
    assert result.overfull[0].exceeds_tolerance(2.0) is True


def test_compile_raises_compile_error_on_timeout(monkeypatch, tmp_path) -> None:
    import pytest

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(
            cmd=[],
            timeout=120,
            output=b"line 1\nline 2\npartial log before kill",
            stderr=b"! Emergency stop.\n*** (job aborted)",
        )

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    with pytest.raises(compiler.CompileError, match="timed out") as excinfo:
        compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    message = str(excinfo.value)
    assert "partial log before kill" in message
    assert "Emergency stop" in message


def test_format_log_tail_decodes_bytes() -> None:
    tail = compiler._format_log_tail(b"stdout line\n", b"stderr line\n")
    assert "stdout line" in tail
    assert "stderr line" in tail
    assert "--- stderr ---" in tail


def test_decode_log_chunk_replaces_invalid_utf8() -> None:
    decoded = compiler._decode_log_chunk(b"valid\xff\xfe bytes")
    assert "valid" in decoded
    assert "\ufffd" in decoded


def test_compile_survives_invalid_utf8_in_pdflatex_output(monkeypatch, tmp_path) -> None:
    stdout = b"Overfull \\hbox (1.0pt too wide) in paragraph at lines 1--2\n\xff\xfe\nOutput written on /tmp/x.pdf (1 page, 1234 bytes).\n"

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        output_dir = Path(next(arg for arg in args if arg.startswith("-output-directory=")).split("=", 1)[1])
        (output_dir / "x.pdf").write_bytes(b"%PDF-fake")
        return subprocess.CompletedProcess(args, 0, stdout, b"")

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    result = compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    assert result.pages == 1


def test_compile_error_includes_stderr(monkeypatch, tmp_path) -> None:
    import pytest

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        # No PDF is written -- simulate a failed compile.
        return subprocess.CompletedProcess(args, 1, "log tail here", "! LaTeX Error: File `x.sty' not found.")

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    with pytest.raises(compiler.CompileError) as excinfo:
        compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    message = str(excinfo.value)
    assert "log tail here" in message
    assert "x.sty" in message


def test_compile_error_includes_log_on_missing_page_count(monkeypatch, tmp_path) -> None:
    import pytest

    def fake_run(args, **kwargs) -> subprocess.CompletedProcess:
        output_dir = Path(next(arg for arg in args if arg.startswith("-output-directory=")).split("=", 1)[1])
        (output_dir / "x.pdf").write_bytes(b"%PDF-fake")
        return subprocess.CompletedProcess(
            args,
            0,
            "No page count line in this log\nLaTeX finished with no summary",
            "",
        )

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: "/usr/bin/pdflatex")
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)

    with pytest.raises(compiler.CompileError) as excinfo:
        compiler.compile_tex("tex", "x", tmp_path / "tex", tmp_path / "pdf")

    message = str(excinfo.value)
    assert "Could not determine page count" in message
    assert "No page count line in this log" in message


def test_find_pdflatex_missing_raises_compile_error(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(compiler.shutil, "which", lambda _name: None)
    monkeypatch.setattr(compiler.Path, "is_file", lambda self: False)

    with pytest.raises(compiler.CompileError, match="MacTeX"):
        compiler.find_pdflatex()


def test_find_pdflatex_fallback_location(monkeypatch) -> None:
    monkeypatch.setattr(compiler.shutil, "which", lambda _name: None)
    monkeypatch.setattr(compiler.Path, "is_file", lambda self: str(self) == "/Library/TeX/texbin/pdflatex")

    engine = compiler.find_pdflatex()
    assert engine == "/Library/TeX/texbin/pdflatex"
