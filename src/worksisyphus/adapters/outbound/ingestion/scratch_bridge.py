"""Scratch bridge for persisting verbatim job descriptions and payload states to disk."""

from __future__ import annotations

import json
from pathlib import Path

from ....core.domain.ingestion import RawJobPayload

DEFAULT_SCRATCH_DIR = Path(".worksisyphus/scratch")


class ScratchBridge:
    """Manages file-based scratch storage to avoid passing giant JD strings through shell buffers."""

    def __init__(self, scratch_dir: Path | str | None = None) -> None:
        self.scratch_dir = Path(scratch_dir) if scratch_dir is not None else DEFAULT_SCRATCH_DIR

    def _ensure_dir(self) -> Path:
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        return self.scratch_dir

    def save_current_jd(self, jd_text: str, filename: str = "current_jd.txt") -> Path:
        """Write verbatim JD text to scratch disk."""
        dest_dir = self._ensure_dir()
        target = dest_dir / filename
        target.write_text(jd_text, encoding="utf-8")
        return target

    def read_current_jd(self, filename: str = "current_jd.txt") -> str:
        """Read verbatim JD text from scratch disk."""
        target = self.scratch_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Scratch JD file not found: {target}")
        return target.read_text(encoding="utf-8")

    def save_raw_payload(self, payload: RawJobPayload, filename: str = "raw_payload.json") -> Path:
        """Persist raw job payload to scratch disk as JSON."""
        dest_dir = self._ensure_dir()
        target = dest_dir / filename
        data = {
            "url": payload.url,
            "raw_content": payload.raw_content,
            "content_type": payload.content_type,
            "source_hint": payload.source_hint,
            "fetched_at": payload.fetched_at,
        }
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return target

    def load_raw_payload(self, filename: str = "raw_payload.json") -> RawJobPayload:
        """Load raw job payload from scratch disk."""
        target = self.scratch_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Scratch payload file not found: {target}")
        data = json.loads(target.read_text(encoding="utf-8"))
        return RawJobPayload(
            url=data["url"],
            raw_content=data["raw_content"],
            content_type=data["content_type"],
            source_hint=data["source_hint"],
            fetched_at=data["fetched_at"],
        )

    def clear(self) -> None:
        """Remove all files in the scratch directory."""
        if self.scratch_dir.exists():
            for p in self.scratch_dir.glob("*"):
                if p.is_file():
                    p.unlink()
