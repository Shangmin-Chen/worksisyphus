"""Ports: Explicit interface boundaries (Protocols) decoupling Core from Adapters."""

from .compiler import CompileError, CompileResult, CompilerPort
from .ingestion import RawFetcherPort
from .parser import ATSCheckResult, AtsExtractorPort

__all__ = [
    "ATSCheckResult",
    "AtsExtractorPort",
    "CompileError",
    "CompileResult",
    "CompilerPort",
    "RawFetcherPort",
]
