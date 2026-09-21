"""Ports: Explicit interface boundaries (Protocols) decoupling Core from Adapters."""

from .compiler import CompileError, CompileResult, CompilerPort
from .parser import ATSCheckResult, AtsExtractorPort
from .rubrics import RoleRubricPort
from .storage import StoragePort
from .vcs import GitFreshnessResult, GitGuardPort

__all__ = [
    "ATSCheckResult",
    "AtsExtractorPort",
    "CompileError",
    "CompileResult",
    "CompilerPort",
    "GitFreshnessResult",
    "GitGuardPort",
    "RoleRubricPort",
    "StoragePort",
]
