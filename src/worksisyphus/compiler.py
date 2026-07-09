"""Compile trusted rendered TeX to PDF with pdflatex and report the page count."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_PAGES_RE = re.compile(r"Output written on .*\((\d+) pages?")


class CompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompileResult:
    pdf_path: Path
    tex_path: Path
    pages: int


def compile_tex(tex: str, name: str, tex_dir: Path, pdf_dir: Path) -> CompileResult:
    """Write <name>.tex to tex_dir, compile it in a temp dir, export <name>.pdf to pdf_dir."""
    engine = shutil.which("pdflatex")
    if engine is None:
        raise CompileError("pdflatex not found on PATH.")

    tex_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    tex_path = tex_dir / f"{name}.tex"
    tex_path.write_text(tex, encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="worksisyphus-") as workdir:
        proc = subprocess.run(
            [engine, "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={workdir}", str(tex_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        built_pdf = Path(workdir) / f"{name}.pdf"
        if proc.returncode != 0 or not built_pdf.is_file():
            tail = "\n".join((proc.stdout or "").splitlines()[-15:])
            raise CompileError(f"pdflatex failed for {tex_path.name}:\n{tail}")
        # pdflatex hard-wraps log lines, which can split the page-count line.
        match = _PAGES_RE.search("".join(proc.stdout.splitlines()))
        if match is None:
            raise CompileError(f"Could not determine page count for {tex_path.name}.")
        pdf_path = pdf_dir / f"{name}.pdf"
        shutil.copyfile(built_pdf, pdf_path)

    return CompileResult(pdf_path=pdf_path, tex_path=tex_path, pages=int(match.group(1)))
