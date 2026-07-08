from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import CanonicalProfile, SelectionPlan, TemplateSpec
from .renderer import RENDERER_VERSION
from .selection import selection_plan_artifact_json


ARTIFACT_KEY_VERSION = "artifact-key-v1"
COMPILER_CONFIG_VERSION = "safe-pdf-backend-v1"


@dataclass(frozen=True)
class TexArtifactRecord:
    key: str
    tex_path: Path
    metadata_path: Path
    has_pdf: bool = False
    pdf_path: Path | None = None
    log_path: Path | None = None


@dataclass(frozen=True)
class ArtifactExportResult:
    key: str
    output_path: Path
    artifact_type: str
    exported: bool
    reason: str = ""


class InvalidPdfArtifactError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_profile_hash(profile: CanonicalProfile) -> str:
    return sha256_text(canonical_json(dataclasses.asdict(profile)))


def template_spec_config_dict(template_spec: TemplateSpec) -> dict[str, Any]:
    return {
        "command_profile": template_spec.command_profile,
        "document_type": template_spec.document_type,
        "id": template_spec.id,
        "max_bullets_per_experience": template_spec.max_bullets_per_experience,
        "max_bullets_per_project": template_spec.max_bullets_per_project,
        "max_education": template_spec.max_education,
        "max_experiences": template_spec.max_experiences,
        "max_projects": template_spec.max_projects,
        "max_skills_per_group": template_spec.max_skills_per_group,
        "page_limit": template_spec.page_limit,
        "preamble": template_spec.preamble,
        "section_order": list(template_spec.section_order),
        "skill_group_order": list(template_spec.skill_group_order),
        "source_template": template_spec.source_template,
        "spacing_profile": template_spec.spacing_profile,
        "version": template_spec.version,
    }


def template_spec_hash(template_spec: TemplateSpec) -> str:
    return sha256_text(canonical_json(template_spec_config_dict(template_spec)))


def artifact_cache_key(
    *,
    selection_plan: SelectionPlan,
    template_spec: TemplateSpec,
    canonical_profile_hash_value: str,
    renderer_version: str = RENDERER_VERSION,
    compiler_config_version: str = COMPILER_CONFIG_VERSION,
) -> str:
    payload = {
        "artifact_key_version": ARTIFACT_KEY_VERSION,
        "canonical_profile_hash": canonical_profile_hash_value,
        "compiler_config_version": compiler_config_version,
        "renderer_version": renderer_version,
        "selection_plan_artifact_json": selection_plan_artifact_json(selection_plan),
        "template_spec_hash": template_spec_hash(template_spec),
        "template_spec_identity": {
            "id": template_spec.id,
            "version": template_spec.version,
            "document_type": template_spec.document_type,
        },
    }
    return sha256_text(canonical_json(payload))


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(path, text.encode(encoding))


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    temp_path: Path | None = None
    try:
        fd, raw_temp_path = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "wb") as temp_file:
            fd = None
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, target)
        _fsync_directory(target.parent)
        return target
    except BaseException:
        if fd is not None:
            os.close(fd)
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        raise


class ArtifactStore:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    def artifact_dir(self, key: str) -> Path:
        return self.cache_dir / "artifacts" / key

    def tex_path(self, key: str) -> Path:
        return self.artifact_dir(key) / "artifact.tex"

    def metadata_path(self, key: str) -> Path:
        return self.artifact_dir(key) / "metadata.json"

    def pdf_path(self, key: str) -> Path:
        return self.artifact_dir(key) / "artifact.pdf"

    def log_path(self, key: str) -> Path:
        return self.artifact_dir(key) / "compile.log"

    def cache_tex(
        self,
        *,
        key: str,
        tex: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> TexArtifactRecord:
        artifact_dir = self.artifact_dir(key)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.tex_path(key)
        metadata_path = self.metadata_path(key)
        pdf_path = self.pdf_path(key)
        log_path = self.log_path(key)
        prior_metadata = self.read_metadata(key)
        has_pdf = pdf_validation_error(pdf_path) is None
        has_log = log_path.is_file()
        pdf_status = prior_metadata.get("pdf_status") if has_pdf else None

        atomic_write_text(tex_path, tex)
        metadata_record = self._base_metadata(
            key=key,
            metadata=metadata,
            has_pdf=has_pdf,
            has_log=has_log,
            pdf_status=str(pdf_status or "not_compiled"),
        )
        if prior_metadata.get("last_compile") is not None:
            metadata_record["last_compile"] = prior_metadata["last_compile"]
        atomic_write_text(metadata_path, canonical_json(metadata_record) + "\n")
        return TexArtifactRecord(
            key=key,
            tex_path=tex_path,
            metadata_path=metadata_path,
            has_pdf=has_pdf,
            pdf_path=pdf_path if has_pdf else None,
            log_path=log_path if has_log else None,
        )

    def read_metadata(self, key: str) -> dict[str, Any]:
        metadata_path = self.metadata_path(key)
        if not metadata_path.is_file():
            return {}
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            value = json.load(metadata_file)
        return value if isinstance(value, dict) else {}

    def has_pdf(self, key: str) -> bool:
        return self.pdf_path(key).is_file()

    def cache_compile_log(
        self,
        *,
        key: str,
        log_text: str,
        compile_metadata: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        artifact_dir = self.artifact_dir(key)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_path(key)
        atomic_write_text(log_path, log_text)

        pdf_path = self.pdf_path(key)
        has_pdf = pdf_validation_error(pdf_path) is None
        timed_out = bool(compile_metadata.get("timed_out"))
        ok = bool(compile_metadata.get("ok"))
        if ok and has_pdf:
            pdf_status = "compiled"
        elif ok:
            pdf_status = "compile_succeeded_no_pdf"
        elif has_pdf:
            pdf_status = "compile_timeout_existing_pdf_preserved" if timed_out else "compile_failed_existing_pdf_preserved"
        else:
            pdf_status = "compile_timeout" if timed_out else "compile_failed"

        metadata_record = self._base_metadata(
            key=key,
            metadata=metadata,
            has_pdf=has_pdf,
            has_log=True,
            pdf_status=pdf_status,
        )
        metadata_record["last_compile"] = dict(compile_metadata)
        atomic_write_text(self.metadata_path(key), canonical_json(metadata_record) + "\n")
        return log_path

    def cache_pdf_from_path(
        self,
        *,
        key: str,
        pdf_path: str | Path,
        metadata: Mapping[str, Any] | None = None,
        compile_metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        source = Path(pdf_path)
        if not source.is_file():
            raise FileNotFoundError(f"Compiled PDF does not exist: {source}")
        pdf_error = pdf_validation_error(source)
        if pdf_error is not None:
            raise InvalidPdfArtifactError(f"Compiled PDF is invalid and was not cached: {pdf_error}")

        artifact_dir = self.artifact_dir(key)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        cached_pdf_path = self.pdf_path(key)
        atomic_write_bytes(cached_pdf_path, source.read_bytes())

        log_path = self.log_path(key)
        metadata_record = self._base_metadata(
            key=key,
            metadata=metadata,
            has_pdf=True,
            has_log=log_path.is_file(),
            pdf_status="compiled",
        )
        if compile_metadata is not None:
            metadata_record["last_compile"] = dict(compile_metadata)
        atomic_write_text(self.metadata_path(key), canonical_json(metadata_record) + "\n")
        return cached_pdf_path

    def _base_metadata(
        self,
        *,
        key: str,
        metadata: Mapping[str, Any] | None,
        has_pdf: bool,
        has_log: bool,
        pdf_status: str,
    ) -> dict[str, Any]:
        prior_metadata = self.read_metadata(key)
        metadata_payload = dict(metadata) if metadata is not None else dict(prior_metadata.get("metadata", {}))
        metadata_record: dict[str, Any] = {
            "artifact_key": key,
            "artifact_type": "tex_pdf",
            "has_pdf": has_pdf,
            "has_log": has_log,
            "has_tex": self.tex_path(key).is_file(),
            "pdf_status": pdf_status,
            "metadata": metadata_payload,
            "renderer_version": RENDERER_VERSION,
        }
        if has_pdf:
            metadata_record["has_pdf"] = True
            metadata_record["pdf_path"] = self.pdf_path(key).name
        if has_log:
            metadata_record["has_log"] = True
            metadata_record["log_path"] = self.log_path(key).name
        return metadata_record

    def has_tex(self, key: str) -> bool:
        return self.tex_path(key).is_file()

    def read_tex(self, key: str) -> str:
        return self.tex_path(key).read_text(encoding="utf-8")

    def export_tex(self, *, key: str, output_path: str | Path) -> ArtifactExportResult:
        tex_path = self.tex_path(key)
        if not tex_path.is_file():
            raise FileNotFoundError(f"No cached TeX artifact for key {key!r}.")
        output = Path(output_path)
        atomic_write_bytes(output, tex_path.read_bytes())
        return ArtifactExportResult(key=key, output_path=output, artifact_type="tex", exported=True)

    def export_pdf(self, *, key: str, output_path: str | Path) -> ArtifactExportResult:
        pdf_path = self.pdf_path(key)
        if not pdf_path.is_file():
            raise FileNotFoundError(f"No cached PDF artifact for key {key!r}.")
        pdf_error = pdf_validation_error(pdf_path)
        if pdf_error is not None:
            raise InvalidPdfArtifactError(f"Cached PDF artifact for key {key!r} is invalid: {pdf_error}")
        output = Path(output_path)
        atomic_write_bytes(output, pdf_path.read_bytes())
        return ArtifactExportResult(key=key, output_path=output, artifact_type="pdf", exported=True)


def pdf_validation_error(path: str | Path) -> str | None:
    target = Path(path)
    if not target.is_file():
        return f"PDF does not exist: {target}"
    if target.stat().st_size == 0:
        return f"PDF is empty: {target}"
    with target.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            return f"PDF header is invalid: {target}"
    return None


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        return
    finally:
        os.close(directory_fd)
