from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore
from .models import RenderModel, TemplateSpec
from .renderer import RENDERER_VERSION, render_tex


COMPILER_BACKEND_VERSION = "safe-compiler-backend-v1"
DEFAULT_COMPILE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    engine: str
    source: str
    tex_path: Path | None
    pdf_path: Path | None
    log_path: Path | None
    stdout: str
    stderr: str
    log_text: str
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    attempted_engines: tuple[str, ...] = ()
    exported_pdf_path: Path | None = None


@dataclass(frozen=True)
class _RenderedTexSource:
    tex: str
    source: str
    template_id: str
    template_version: str
    renderer_version: str


@dataclass(frozen=True)
class _EngineAttempt:
    engine: str
    argv: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str
    tex_log: str


RunCompiler = Callable[..., subprocess.CompletedProcess[str]]
FindExecutable = Callable[[str], str | None]


class CompilerBackend:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        *,
        timeout_seconds: float = DEFAULT_COMPILE_TIMEOUT_SECONDS,
        build_parent: str | Path | None = None,
        engines: Sequence[str] = ("latexmk", "pdflatex"),
        runner: RunCompiler = subprocess.run,
        find_executable: FindExecutable = shutil.which,
    ) -> None:
        self.artifact_store = artifact_store
        self.timeout_seconds = timeout_seconds
        self.build_parent = Path(build_parent) if build_parent is not None else None
        self.engines = tuple(engines)
        self._runner = runner
        self._find_executable = find_executable

    def compile_render_model(
        self,
        *,
        render_model: RenderModel,
        template_spec: TemplateSpec,
        key: str,
        output_pdf_path: str | Path | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CompileResult:
        source = _RenderedTexSource(
            tex=render_tex(render_model, template_spec),
            source="TexRenderer.render(RenderModel, TemplateSpec)",
            template_id=template_spec.id,
            template_version=template_spec.version,
            renderer_version=RENDERER_VERSION,
        )
        return self._compile_rendered_tex_source(
            source=source,
            key=key,
            output_pdf_path=output_pdf_path,
            metadata=metadata,
        )

    def _compile_rendered_tex_source(
        self,
        *,
        source: _RenderedTexSource,
        key: str,
        output_pdf_path: str | Path | None,
        metadata: Mapping[str, Any] | None,
    ) -> CompileResult:
        artifact_metadata = dict(metadata or {})
        artifact_metadata.update(
            {
                "compiler_backend_version": COMPILER_BACKEND_VERSION,
                "renderer_version": source.renderer_version,
                "template_id": source.template_id,
                "template_version": source.template_version,
            }
        )
        tex_record = self.artifact_store.cache_tex(key=key, tex=source.tex, metadata=artifact_metadata)

        warnings: list[str] = []
        errors: list[str] = []
        attempts: list[_EngineAttempt] = []
        log_text = ""

        with tempfile.TemporaryDirectory(
            prefix="worksisyphus-compile-",
            dir=self.build_parent,
        ) as build_dir_text:
            build_dir = Path(build_dir_text)
            build_tex_path = build_dir / "artifact.tex"
            build_pdf_path = build_dir / "artifact.pdf"
            build_tex_path.write_text(source.tex, encoding="utf-8")

            for engine in self.engines:
                executable = self._find_executable(engine)
                if executable is None:
                    warnings.append(f"{engine} is unavailable; skipped.")
                    continue

                attempt = self._run_engine(engine=engine, executable=executable, build_dir=build_dir)
                attempts.append(attempt)
                warnings.extend(_extract_warnings(attempt.tex_log))
                log_text = _combined_log(attempts, warnings=warnings, errors=errors)

                if attempt.timed_out:
                    errors.append(f"{engine} timed out after {self.timeout_seconds:g} seconds.")
                    return self._failure_result(
                        key=key,
                        tex_path=tex_record.tex_path,
                        source=source.source,
                        attempts=attempts,
                        warnings=warnings,
                        errors=errors,
                        timed_out=True,
                        log_text=_combined_log(attempts, warnings=warnings, errors=errors),
                        metadata=artifact_metadata,
                    )

                if attempt.returncode == 0:
                    pdf_error = _pdf_validation_error(build_pdf_path)
                    if pdf_error is None:
                        return self._publish_success(
                            key=key,
                            tex_path=tex_record.tex_path,
                            source=source.source,
                            build_pdf_path=build_pdf_path,
                            attempts=attempts,
                            warnings=warnings,
                            output_pdf_path=output_pdf_path,
                            log_text=log_text,
                            metadata=artifact_metadata,
                        )
                    errors.append(pdf_error)
                else:
                    errors.extend(_extract_errors(attempt.tex_log))
                    if attempt.returncode is None:
                        error_text = (attempt.stderr or attempt.stdout or "unknown subprocess error").strip()
                        errors.append(f"{engine} execution failed: {error_text}")
                    else:
                        errors.append(f"{engine} exited with return code {attempt.returncode}.")

                if engine == "latexmk" and "pdflatex" in self.engines:
                    warnings.append("latexmk failed; trying pdflatex fallback.")

        if not attempts:
            errors.append("No configured TeX engine is available.")
        elif not errors:
            errors.append("No configured TeX engine produced a valid PDF.")

        return self._failure_result(
            key=key,
            tex_path=tex_record.tex_path,
            source=source.source,
            attempts=attempts,
            warnings=warnings,
            errors=errors,
            timed_out=False,
            log_text=_combined_log(attempts, warnings=warnings, errors=errors),
            metadata=artifact_metadata,
        )

    def _run_engine(self, *, engine: str, executable: str, build_dir: Path) -> _EngineAttempt:
        argv = _engine_argv(engine, executable)
        try:
            completed = self._runner(
                list(argv),
                cwd=build_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
            return _EngineAttempt(
                engine=engine,
                argv=argv,
                returncode=completed.returncode,
                timed_out=False,
                stdout=_output_to_text(completed.stdout),
                stderr=_output_to_text(completed.stderr),
                tex_log=_read_text_if_exists(build_dir / "artifact.log"),
            )
        except subprocess.TimeoutExpired as exc:
            return _EngineAttempt(
                engine=engine,
                argv=argv,
                returncode=None,
                timed_out=True,
                stdout=_output_to_text(exc.output),
                stderr=_output_to_text(exc.stderr),
                tex_log=_read_text_if_exists(build_dir / "artifact.log"),
            )
        except OSError as exc:
            return _EngineAttempt(
                engine=engine,
                argv=argv,
                returncode=None,
                timed_out=False,
                stdout="",
                stderr=f"{exc.__class__.__name__}: {exc}",
                tex_log=_read_text_if_exists(build_dir / "artifact.log"),
            )
        except subprocess.SubprocessError as exc:
            return _EngineAttempt(
                engine=engine,
                argv=argv,
                returncode=getattr(exc, "returncode", None),
                timed_out=False,
                stdout=_output_to_text(getattr(exc, "output", None)),
                stderr=_output_to_text(getattr(exc, "stderr", None)) or f"{exc.__class__.__name__}: {exc}",
                tex_log=_read_text_if_exists(build_dir / "artifact.log"),
            )

    def _publish_success(
        self,
        *,
        key: str,
        tex_path: Path,
        source: str,
        build_pdf_path: Path,
        attempts: Sequence[_EngineAttempt],
        warnings: Sequence[str],
        output_pdf_path: str | Path | None,
        log_text: str,
        metadata: Mapping[str, Any],
    ) -> CompileResult:
        final_attempt = attempts[-1]
        compile_metadata = _compile_metadata(
            ok=True,
            attempt=final_attempt,
            warnings=warnings,
            errors=(),
            attempted_engines=tuple(attempt.engine for attempt in attempts),
        )
        pdf_path = self.artifact_store.cache_pdf_from_path(
            key=key,
            pdf_path=build_pdf_path,
            metadata=metadata,
            compile_metadata=compile_metadata,
        )
        log_path = self.artifact_store.cache_compile_log(
            key=key,
            log_text=log_text,
            metadata=metadata,
            compile_metadata=compile_metadata,
        )
        exported_pdf_path: Path | None = None
        if output_pdf_path is not None:
            exported = self.artifact_store.export_pdf(key=key, output_path=output_pdf_path)
            exported_pdf_path = exported.output_path

        return CompileResult(
            ok=True,
            engine=final_attempt.engine,
            source=source,
            tex_path=tex_path,
            pdf_path=pdf_path,
            log_path=log_path,
            stdout=_combine_outputs(attempts, "stdout"),
            stderr=_combine_outputs(attempts, "stderr"),
            log_text=log_text,
            warnings=tuple(warnings),
            errors=(),
            returncode=final_attempt.returncode,
            timed_out=False,
            attempted_engines=tuple(attempt.engine for attempt in attempts),
            exported_pdf_path=exported_pdf_path,
        )

    def _failure_result(
        self,
        *,
        key: str,
        tex_path: Path,
        source: str,
        attempts: Sequence[_EngineAttempt],
        warnings: Sequence[str],
        errors: Sequence[str],
        timed_out: bool,
        log_text: str,
        metadata: Mapping[str, Any],
    ) -> CompileResult:
        final_attempt = attempts[-1] if attempts else None
        compile_metadata = {
            "ok": False,
            "engine": final_attempt.engine if final_attempt is not None else "",
            "returncode": final_attempt.returncode if final_attempt is not None else None,
            "timed_out": timed_out,
            "warnings": list(warnings),
            "errors": list(errors),
            "attempted_engines": [attempt.engine for attempt in attempts],
        }
        log_path = self.artifact_store.cache_compile_log(
            key=key,
            log_text=log_text,
            metadata=metadata,
            compile_metadata=compile_metadata,
        )
        return CompileResult(
            ok=False,
            engine=final_attempt.engine if final_attempt is not None else "",
            source=source,
            tex_path=tex_path,
            pdf_path=None,
            log_path=log_path,
            stdout=_combine_outputs(attempts, "stdout"),
            stderr=_combine_outputs(attempts, "stderr"),
            log_text=log_text,
            warnings=tuple(warnings),
            errors=tuple(errors),
            returncode=final_attempt.returncode if final_attempt is not None else None,
            timed_out=timed_out,
            attempted_engines=tuple(attempt.engine for attempt in attempts),
        )


def _engine_argv(engine: str, executable: str) -> tuple[str, ...]:
    if engine == "latexmk":
        return (
            executable,
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-outdir=.",
            "artifact.tex",
        )
    if engine == "pdflatex":
        return (
            executable,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "artifact.tex",
        )
    raise ValueError(f"Unsupported TeX engine {engine!r}.")


def _compile_metadata(
    *,
    ok: bool,
    attempt: _EngineAttempt,
    warnings: Sequence[str],
    errors: Sequence[str],
    attempted_engines: Sequence[str],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "engine": attempt.engine,
        "returncode": attempt.returncode,
        "timed_out": attempt.timed_out,
        "warnings": list(warnings),
        "errors": list(errors),
        "attempted_engines": list(attempted_engines),
    }


def _combined_log(
    attempts: Sequence[_EngineAttempt],
    *,
    warnings: Sequence[str],
    errors: Sequence[str],
) -> str:
    parts: list[str] = []
    if warnings:
        parts.append("Warnings:\n" + "\n".join(warnings))
    if errors:
        parts.append("Errors:\n" + "\n".join(errors))
    for attempt in attempts:
        parts.append(
            "\n".join(
                [
                    f"Engine: {attempt.engine}",
                    "argv: " + " ".join(attempt.argv),
                    f"returncode: {attempt.returncode}",
                    f"timed_out: {attempt.timed_out}",
                    "stdout:",
                    attempt.stdout,
                    "stderr:",
                    attempt.stderr,
                    "tex log:",
                    attempt.tex_log,
                ]
            )
        )
    return "\n\n".join(parts).rstrip() + "\n"


def _combine_outputs(attempts: Sequence[_EngineAttempt], field: str) -> str:
    chunks: list[str] = []
    for attempt in attempts:
        value = getattr(attempt, field)
        if value:
            chunks.append(value)
    return "\n".join(chunks)


def _read_text_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _output_to_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _extract_warnings(log_text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in log_text.splitlines() if "warning" in line.lower())


def _extract_errors(log_text: str) -> tuple[str, ...]:
    errors: list[str] = []
    for line in log_text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("!") or "fatal error" in lowered or "emergency stop" in lowered:
            errors.append(stripped)
    return tuple(errors)


def _pdf_validation_error(path: Path) -> str | None:
    if not path.is_file():
        return f"TeX engine completed but did not produce {path.name}."
    if path.stat().st_size == 0:
        return f"TeX engine produced an empty PDF at {path.name}."
    with path.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            return f"TeX engine output at {path.name} is not a PDF."
    return None
