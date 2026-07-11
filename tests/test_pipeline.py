from __future__ import annotations

import json

import pytest

from worksisyphus import CompileResult, pipeline
from worksisyphus.pipeline import tailor


def _plan_text() -> str:
    return json.dumps(
        {
            "name": "acme",
            "experiences": {"org-a": ["a1", "a2", "a3"], "org-b": ["b1", "b2"]},
            "projects": {"proj1": ["p1", "p2", "p3"], "proj2": ["q1"]},
            "skills": {"languages": ["Python", "Rust"]},
        }
    )


def test_tailor_trims_until_one_page(small_profile, monkeypatch, tmp_path) -> None:
    compiled: list[str] = []
    pages_by_call = [2, 2, 1]

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        compiled.append(tex)
        return CompileResult(pdf_path=tmp_path / f"{name}.pdf", tex_path=tmp_path / f"{name}.tex", pages=pages_by_call[len(compiled) - 1])

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    result = tailor(_plan_text())

    assert result.pages == 1
    assert len(compiled) == 3
    assert "Proj" in compiled[0]
    # First trim drops the lowest-ranked project.
    assert r"Proj \& Two" not in compiled[1]


def test_tailor_raises_when_nothing_left_to_trim(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        return CompileResult(pdf_path=tmp_path / "x.pdf", tex_path=tmp_path / "x.tex", pages=2)

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    with pytest.raises(RuntimeError, match="one page"):
        tailor(_plan_text())


def test_tailor_rejects_empty_plan() -> None:
    with pytest.raises(ValueError, match="empty"):
        tailor("   ")
