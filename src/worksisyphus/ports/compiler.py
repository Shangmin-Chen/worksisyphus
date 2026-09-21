"""Compiler Port: Abstract boundary protocol for LaTeX to PDF compilation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.domain.rules import TrimCut


class CompileError(RuntimeError):
    """Raised when TeX compilation fails or violates page requirements."""


@dataclass(frozen=True)
class CompileResult:
    """Immutable outcome of a LaTeX compilation run."""

    pdf_path: Path
    tex_path: Path
    pages: int
    overfull: tuple[str, ...] = ()
    trimmed: tuple[TrimCut, ...] = ()


@runtime_checkable
class CompilerPort(Protocol):
    """Port interface for compiling LaTeX source into a PDF document."""

    def compile_tex(
        self,
        tex: str,
        name: str,
        tex_dir: Path,
        pdf_dir: Path,
    ) -> CompileResult:
        """Compile TeX source string into PDF within designated target directories."""
        ...
