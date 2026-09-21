"""Backward-compatibility facade for LaTeX compilation."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .adapters.outbound.latex import compiler as _module
from .adapters.outbound.latex.compiler import (
    _OVERFULL_RE,
    PDFLATEX_TIMEOUT_SECONDS,
    PdfLatexCompiler,
    _decode_log_chunk,
    _format_log_tail,
    compile_tex,
    find_pdflatex,
)
from .ports.compiler import CompileError, CompileResult

sys.modules[__name__] = _module

__all__ = [
    "PDFLATEX_TIMEOUT_SECONDS",
    "_OVERFULL_RE",
    "CompileError",
    "CompileResult",
    "Path",
    "PdfLatexCompiler",
    "_decode_log_chunk",
    "_format_log_tail",
    "compile_tex",
    "find_pdflatex",
    "shutil",
    "subprocess",
]
