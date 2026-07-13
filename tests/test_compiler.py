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
