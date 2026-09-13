"""Compile trusted rendered TeX to PDF with pdflatex and report the page count."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_PAGES_RE = re.compile(r"Output written on .*\((\d+) pages?")
_OVERFULL_RE = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\) in .*? at lines? (\d+)")

PDFLATEX_TIMEOUT_SECONDS = 120
_LOG_TAIL_LINES = 15


def _decode_log_chunk(chunk: str | bytes | None) -> str:
    if chunk is None:
        return ""
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", errors="replace")
    return chunk


def _format_log_tail(
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    *,
    lines: int = _LOG_TAIL_LINES,
) -> str:
    """Return the last *lines* of pdflatex stdout/stderr for CompileError diagnostics."""
    tail = "\n".join(_decode_log_chunk(stdout).splitlines()[-lines:])
    err_tail = "\n".join(_decode_log_chunk(stderr).splitlines()[-lines:])
    if not err_tail:
        return tail
    return f"{tail}\n--- stderr ---\n{err_tail}" if tail else err_tail


class CompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompileResult:
    pdf_path: Path
    tex_path: Path
    pages: int
    overfull: tuple[str, ...] = ()


def find_pdflatex() -> str:
    """Locate the pdflatex executable on PATH or in standard MacTeX / TeX Live locations."""
    which_path = shutil.which("pdflatex")
    if which_path is not None:
        return which_path

    known_locations = (
        "/Library/TeX/texbin/pdflatex",
        "/usr/local/texlive/2026/bin/universal-darwin/pdflatex",
        "/usr/local/texlive/2025/bin/universal-darwin/pdflatex",
        "/usr/local/texlive/2024/bin/universal-darwin/pdflatex",
        "/opt/homebrew/bin/pdflatex",
        "/usr/local/bin/pdflatex",
    )
    for loc in known_locations:
        if Path(loc).is_file():
            return loc

    raise CompileError(
        "pdflatex not found. MacTeX (or a compatible LaTeX distribution) is required to compile resumes.\n"
        "Install via Homebrew on macOS:\n"
        "  brew install --cask mactex      # Full MacTeX distribution\n"
        "  brew install --cask basictex    # Lightweight MacTeX distribution\n"
        'If already installed, ensure /Library/TeX/texbin is on your PATH (e.g. run: eval "$(/usr/libexec/path_helper)").'
    )


def compile_tex(tex: str, name: str, tex_dir: Path, pdf_dir: Path) -> CompileResult:
    """Write <name>.tex to tex_dir, compile it in a temp dir, export <name>.pdf to pdf_dir."""
    engine = find_pdflatex()

    tex_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    tex_path = tex_dir / f"{name}.tex"
    tex_path.write_text(tex, encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="worksisyphus-") as workdir:
        try:
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={workdir}", str(tex_path)],
                capture_output=True,
                timeout=PDFLATEX_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            detail = _format_log_tail(exc.stdout, exc.stderr)
            message = (
                f"pdflatex timed out after {PDFLATEX_TIMEOUT_SECONDS}s compiling {tex_path.name}; "
                "the run was killed and no PDF was produced."
            )
            if detail:
                message += f"\n{detail}"
            raise CompileError(message) from exc
        built_pdf = Path(workdir) / f"{name}.pdf"
        if proc.returncode != 0 or not built_pdf.is_file():
            detail = _format_log_tail(proc.stdout, proc.stderr)
            raise CompileError(f"pdflatex failed for {tex_path.name}:\n{detail}")
        # pdflatex hard-wraps log lines, which can split diagnostics.
        stdout = " ".join(_decode_log_chunk(proc.stdout).splitlines())
        match = _PAGES_RE.search(stdout)
        if match is None:
            detail = _format_log_tail(proc.stdout, proc.stderr)
            message = f"Could not determine page count for {tex_path.name}."
            if detail:
                message += f"\n{detail}"
            raise CompileError(message)
        overfull_items: list[str] = []
        for width, line in _OVERFULL_RE.findall(stdout):
            try:
                parsed_width = float(width)
            except ValueError:
                continue
            overfull_items.append(f"{parsed_width:.1f}pt too wide at tex line {line}")
        overfull = tuple(overfull_items)
        pdf_path = pdf_dir / f"{name}.pdf"
        shutil.copyfile(built_pdf, pdf_path)

    return CompileResult(
        pdf_path=pdf_path,
        tex_path=tex_path,
        pages=int(match.group(1)),
        overfull=overfull,
    )
