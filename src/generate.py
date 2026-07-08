#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

from worksisyphus import (
    ArtifactStore,
    CompilerBackend,
    GeminiPlanner,
    InvalidPdfArtifactError,
    PlanCache,
    artifact_cache_key,
    build_render_model,
    canonical_profile_hash,
    get_template_spec,
    load_canonical_profile,
    render_tex,
)


GEMINI_MODEL_ID = "gemini-2.5-flash"
DEFAULT_CACHE_DIR_NAME = ".worksisyphus-cache"


PlannerFactory = Callable[..., GeminiPlanner]
CompilerBackendFactory = Callable[[ArtifactStore], CompilerBackend]


def load_dotenv() -> dict[str, str]:
    env = {}
    path = Path(".env")
    if path.is_file():
        with path.open("r", encoding="utf-8") as env_file:
            for line in env_file:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, value = stripped.split("=", 1)
                    env[key.strip()] = value.strip().strip("'\"")
    return env


def call_gemini(prompt: str, api_key: str, *, model_id: str = GEMINI_MODEL_ID) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API HTTP Error {exc.code}: {error_message}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to communicate with Gemini API: {exc}") from exc

    candidates = response_data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini API returned no candidates: {response_data}")
    return str(candidates[0].get("content", {}).get("parts", [{}])[0].get("text", ""))


def main(
    argv: Sequence[str] | None = None,
    *,
    planner_factory: PlannerFactory = GeminiPlanner,
    compiler_backend_factory: CompilerBackendFactory = CompilerBackend,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    jd_content = _read_raw_input(args.jd)

    if args.mode == "cover-letter":
        return _unsupported_cover_letter()

    env = load_dotenv()
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "Error: Gemini API Key is required for deterministic planning. "
            "Set GEMINI_API_KEY, add it to .env, or pass --api-key."
        )
        return 1

    if args.mode in {"resume", "both"}:
        resume_status = _generate_resume(
            args=args,
            jd_content=jd_content,
            api_key=api_key,
            planner_factory=planner_factory,
            compiler_backend_factory=compiler_backend_factory,
        )
        if resume_status != 0:
            return resume_status

    if args.mode == "both":
        return _unsupported_cover_letter()

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate tailored resumes and cover letters through the deterministic compiler."
    )
    parser.add_argument(
        "--mode",
        choices=["resume", "cover-letter", "both"],
        required=True,
        help="What to generate: 'resume', 'cover-letter', or 'both'",
    )
    parser.add_argument(
        "--jd",
        required=True,
        help="Job Description text or path to a file containing the Job Description",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API Key (overrides GEMINI_API_KEY environment variable or .env file)",
    )
    parser.add_argument(
        "--experiences",
        type=Path,
        default=Path("templates/experiences.json"),
        help="Path to experiences.json master data; default: templates/experiences.json",
    )
    parser.add_argument(
        "--resume-template",
        type=Path,
        default=Path("templates/resumes/jakes_resume_template.tex"),
        help="Path to LaTeX resume template; default: templates/resumes/jakes_resume_template.tex",
    )
    parser.add_argument(
        "--cover-letter-template",
        type=Path,
        default=Path("templates/cover_letters/default_cover_letter.tex"),
        help="Path to LaTeX cover letter template; default: templates/cover_letters/default_cover_letter.tex",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tex_files"),
        help="Output directory for generated artifacts; default: tex_files",
    )
    parser.add_argument(
        "--output-name",
        default="tailored",
        help="Base name for the generated files; default: tailored",
    )
    return parser


def _generate_resume(
    *,
    args: argparse.Namespace,
    jd_content: str,
    api_key: str,
    planner_factory: PlannerFactory,
    compiler_backend_factory: CompilerBackendFactory,
) -> int:
    if not args.experiences.is_file():
        print(f"Error: Experiences JSON file not found at {args.experiences}")
        return 1

    template_spec = get_template_spec("jakes_resume")
    template_error = _resume_template_error(args.resume_template, template_spec.source_template)
    if template_error:
        print(f"Error: {template_error}")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache_root = args.output_dir / DEFAULT_CACHE_DIR_NAME
    plan_cache = PlanCache(cache_root)
    artifact_store = ArtifactStore(cache_root)

    profile = load_canonical_profile(args.experiences)
    profile_hash = canonical_profile_hash(profile)
    planner = planner_factory(
        lambda prompt: call_gemini(prompt, api_key, model_id=GEMINI_MODEL_ID),
        cache=plan_cache,
        model_id=GEMINI_MODEL_ID,
    )

    print("Planning resume selection with Gemini JSON planner...")
    plan_result = planner.plan(
        raw_input=jd_content,
        profile=profile,
        template_spec=template_spec,
        metadata={"mode": "resume", "output_name": args.output_name},
    )
    cache_label = "hit" if plan_result.from_cache else "miss"
    fallback_label = " with deterministic fallback" if plan_result.used_fallback else ""
    print(f"Plan cache {cache_label}; validation status: {plan_result.validation_status}{fallback_label}.")

    render_model = build_render_model(profile=profile, selection_plan=plan_result.plan, template_spec=template_spec)
    artifact_key = artifact_cache_key(
        selection_plan=plan_result.plan,
        template_spec=template_spec,
        canonical_profile_hash_value=profile_hash,
    )
    metadata = {
        "mode": "resume",
        "output_name": args.output_name,
        "plan_cache_key": plan_result.cache_key,
        "plan_validation_status": plan_result.validation_status,
        "template_id": template_spec.id,
        "template_version": template_spec.version,
    }

    tex = render_tex(render_model, template_spec)
    artifact_store.cache_tex(key=artifact_key, tex=tex, metadata=metadata)
    output_tex_path = args.output_dir / f"{args.output_name}_resume.tex"
    artifact_store.export_tex(key=artifact_key, output_path=output_tex_path)
    print(f"Deterministic resume TeX exported: {output_tex_path}")

    output_pdf_path = args.output_dir / f"{args.output_name}_resume.pdf"
    try:
        artifact_store.export_pdf(key=artifact_key, output_path=output_pdf_path)
        print(f"Artifact cache hit; deterministic resume PDF copied: {output_pdf_path}")
        return 0
    except FileNotFoundError:
        print("Artifact cache miss for deterministic resume PDF; compiling.")
    except InvalidPdfArtifactError as exc:
        print(f"Cached deterministic resume PDF is invalid; recompiling. {exc}")

    backend = compiler_backend_factory(artifact_store)
    compile_result = backend.compile_render_model(
        render_model=render_model,
        template_spec=template_spec,
        key=artifact_key,
        output_pdf_path=output_pdf_path,
        metadata=metadata,
    )
    if not compile_result.ok:
        print("Error: deterministic resume TeX was generated, but PDF compilation failed.")
        if compile_result.log_path is not None:
            print(f"Compile log cached: {compile_result.log_path}")
        for error in compile_result.errors:
            print(f"- {error}")
        return 1

    print(f"Deterministic resume PDF exported: {output_pdf_path}")
    return 0


def _read_raw_input(value: str) -> str:
    try:
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return value


def _resume_template_error(candidate: Path, expected_template: str) -> str:
    if not candidate.is_file():
        return f"Resume template file not found at {candidate}"

    expected = Path(expected_template)
    try:
        if candidate.resolve() == expected.resolve():
            return ""
    except OSError:
        pass
    return (
        "deterministic resume generation currently supports only "
        f"{expected_template} through TemplateSpec 'jakes_resume'; got {candidate}"
    )


def _unsupported_cover_letter() -> int:
    print(
        "Error: deterministic cover-letter rendering is not implemented yet. "
        "No Gemini-produced TeX was requested, written, or compiled."
    )
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
