"""Compiler Port: Abstract boundary protocol for LaTeX to PDF compilation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.domain.rules import TrimCut


_OVERFULL_PARSE_RE = re.compile(r"^([\d.]+)pt too wide(?: at tex line (\d+))?")


class CompileError(RuntimeError):
    """Raised when TeX compilation fails or violates page requirements."""


@dataclass(frozen=True)
class OverfullHbox:
    """Structured representation of a LaTeX overfull hbox diagnostic."""

    width_pt: float | None
    line: int | None = None
    raw: str = ""

    def exceeds_tolerance(self, tolerance_pt: float) -> bool:
        """Fail closed: if width could not be parsed, treat as exceeding tolerance."""
        if self.width_pt is None:
            return True
        return self.width_pt > tolerance_pt

    def __str__(self) -> str:
        if self.width_pt is not None and self.line is not None:
            return f"{self.width_pt:.1f}pt too wide at tex line {self.line}"
        if self.width_pt is not None:
            return f"{self.width_pt:.1f}pt too wide"
        return f"unparseable overfull hbox ({self.raw.strip() or 'unknown'})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, OverfullHbox):
            return (self.width_pt, self.line) == (other.width_pt, other.line)
        return False


@dataclass(frozen=True)
class CompileResult:
    """Immutable outcome of a LaTeX compilation run."""

    pdf_path: Path
    tex_path: Path
    pages: int
    overfull: tuple[OverfullHbox, ...] = ()
    trimmed: tuple[TrimCut, ...] = ()



    def __post_init__(self) -> None:
        if self.overfull:
            normalized: list[OverfullHbox] = []
            for item in self.overfull:
                if isinstance(item, OverfullHbox):
                    normalized.append(item)
                elif isinstance(item, str):
                    m = _OVERFULL_PARSE_RE.match(item)
                    if m:
                        try:
                            w = float(m.group(1))
                            l_num = int(m.group(2)) if m.group(2) is not None else None
                            normalized.append(OverfullHbox(width_pt=w, line=l_num, raw=item))
                            continue
                        except ValueError:
                            pass
                    normalized.append(OverfullHbox(width_pt=None, line=None, raw=item))
                else:
                    normalized.append(OverfullHbox(width_pt=None, line=None, raw=str(item)))
            object.__setattr__(self, "overfull", tuple(normalized))



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
