#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from worksisyphus import (
    ArtifactStore,
    CompilerBackend,
    InvalidPdfArtifactError,
    artifact_cache_key,
    build_render_model,
    canonical_profile_hash,
    deterministic_fallback_selection_plan,
    get_template_spec,
    load_canonical_profile,
    render_tex,
)


DEFAULT_CACHE_DIR_NAME = ".worksisyphus-cache"
DEFAULT_RESUME_JSON = Path("templates/experiences.json")
DEFAULT_TEX_OUTPUT = Path("tex_files/Simon_Chen_Resume_Compiled.tex")
DEFAULT_PDF_OUTPUT = Path("resumes/Simon_Chen_Resume_Compiled.pdf")

CompilerBackendFactory = Callable[[ArtifactStore], CompilerBackend]


def compile_resume(
    resume_json_path: Path,
    output_tex: Path,
    compile_pdf: bool = True,
    *,
    pdf_output: Path | None = None,
    cache_dir: Path | None = None,
    template_id: str = "jakes_resume",
    compiler_backend_factory: CompilerBackendFactory = CompilerBackend,
) -> Path:
    """Render and optionally compile a baseline resume through the trusted pipeline."""
    profile = load_canonical_profile(resume_json_path)
    template_spec = get_template_spec(template_id)
    if template_spec.document_type != "resume":
        raise ValueError(f"Template spec {template_id!r} is not a resume template.")

    selection_plan = deterministic_fallback_selection_plan(profile=profile, template_spec=template_spec)
    render_model = build_render_model(
        profile=profile,
        selection_plan=selection_plan,
        template_spec=template_spec,
    )
    artifact_key = artifact_cache_key(
        selection_plan=selection_plan,
        template_spec=template_spec,
        canonical_profile_hash_value=canonical_profile_hash(profile),
    )

    store = ArtifactStore(cache_dir if cache_dir is not None else output_tex.parent / DEFAULT_CACHE_DIR_NAME)
    metadata = {
        "mode": "baseline_resume_rebuild",
        "source_profile": str(resume_json_path),
        "template_id": template_spec.id,
        "template_version": template_spec.version,
    }

    tex = render_tex(render_model, template_spec)
    store.cache_tex(key=artifact_key, tex=tex, metadata=metadata)
    store.export_tex(key=artifact_key, output_path=output_tex)

    if not compile_pdf:
        return output_tex

    target_pdf = pdf_output if pdf_output is not None else output_tex.with_suffix(".pdf")
    try:
        return store.export_pdf(key=artifact_key, output_path=target_pdf).output_path
    except (FileNotFoundError, InvalidPdfArtifactError):
        pass

    backend = compiler_backend_factory(store)
    result = backend.compile_render_model(
        render_model=render_model,
        template_spec=template_spec,
        key=artifact_key,
        output_pdf_path=target_pdf,
        metadata=metadata,
    )
    if not result.ok:
        details = "; ".join(result.errors) if result.errors else "unknown compiler error"
        log_hint = f" Compile log: {result.log_path}" if result.log_path is not None else ""
        raise RuntimeError(f"Deterministic PDF compilation failed: {details}.{log_hint}")
    return result.exported_pdf_path or result.pdf_path or target_pdf


def main(
    argv: Sequence[str] | None = None,
    *,
    compiler_backend_factory: CompilerBackendFactory = CompilerBackend,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    pdf_output = _resolve_pdf_output(args.output, args.pdf_output)

    try:
        out_path = compile_resume(
            args.resume,
            args.output,
            compile_pdf=not args.tex_only,
            pdf_output=pdf_output,
            cache_dir=args.cache_dir,
            template_id=args.template_id,
            compiler_backend_factory=compiler_backend_factory,
        )
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    if args.tex_only:
        print(f"Deterministic LaTeX source exported: {out_path}")
    else:
        print(f"Deterministic PDF exported: {out_path}")
    return 0


def _resolve_pdf_output(output_tex: Path, requested_pdf_output: Path | None) -> Path:
    if requested_pdf_output is not None:
        return requested_pdf_output
    if output_tex == DEFAULT_TEX_OUTPUT:
        return DEFAULT_PDF_OUTPUT
    return output_tex.with_suffix(".pdf")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild the canonical resume through the deterministic compiler."
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=DEFAULT_RESUME_JSON,
        help=f"Path to canonical experiences JSON; default: {DEFAULT_RESUME_JSON}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TEX_OUTPUT,
        help=f"Output path for deterministic TeX; default: {DEFAULT_TEX_OUTPUT}",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=None,
        help=(
            "Output path for deterministic PDF; default: resumes/Simon_Chen_Resume_Compiled.pdf "
            "when --output is the default, otherwise <output>.pdf"
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help=f"Artifact cache directory; default: <output-dir>/{DEFAULT_CACHE_DIR_NAME}",
    )
    parser.add_argument(
        "--template-id",
        default="jakes_resume",
        help="Built-in TemplateSpec ID to use; default: jakes_resume",
    )
    parser.add_argument(
        "--tex-only",
        action="store_true",
        help="Export deterministic TeX without compiling a PDF.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
