from __future__ import annotations

import json

import pytest

from worksisyphus import CompileResult, pipeline
from worksisyphus.pipeline import tailor


def _plan_text() -> str:
    return json.dumps(
        {
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
        (pdf_dir / f"{name}.pdf").write_bytes(b"%PDF-fake")
        return CompileResult(
            pdf_path=tmp_path / f"{name}.pdf", tex_path=tmp_path / f"{name}.tex", pages=pages_by_call[len(compiled) - 1]
        )

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    result = tailor(_plan_text(), tex_dir=tmp_path / "tex", pdf_dir=tmp_path)

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
        tailor(_plan_text(), tex_dir=tmp_path / "tex", pdf_dir=tmp_path)


def test_tailor_rejects_empty_plan() -> None:
    with pytest.raises(ValueError, match="empty"):
        tailor("   ")


def test_tailor_rejects_horizontal_overflow(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        return CompileResult(
            pdf_path=tmp_path / f"{name}.pdf",
            tex_path=tmp_path / f"{name}.tex",
            pages=1,
            overfull=("90.6pt too wide at tex line 127",),
        )

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    with pytest.raises(RuntimeError, match=r"Horizontal overflow.*90\.6pt"):
        tailor(_plan_text(), tex_dir=tmp_path / "tex", pdf_dir=tmp_path)


def test_tailor_accepts_one_page_without_horizontal_overflow(small_profile, monkeypatch, tmp_path) -> None:
    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        (pdf_dir / f"{name}.pdf").write_bytes(b"%PDF-fake")
        return CompileResult(
            pdf_path=tmp_path / f"{name}.pdf",
            tex_path=tmp_path / f"{name}.tex",
            pages=1,
        )

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    assert tailor(_plan_text(), tex_dir=tmp_path / "tex", pdf_dir=tmp_path).overfull == ()


def test_tailor_refuses_a_placeholder_contact_without_compiling(placeholder_profile, monkeypatch, tmp_path) -> None:
    """The preview path is covered by the renderer's check, with nothing compiled.

    `tailor` never called validate_contact and never needs to: it cannot render without going
    through render_resume. What matters is that no PDF is produced -- tailor's output carries
    the delivered resume's exact filename, so a plausible preview is a sendable artifact.
    """
    compiled: list[str] = []

    def exploding_compile(tex, name, tex_dir, pdf_dir):
        compiled.append(name)
        raise AssertionError("compilation must not be reached for an invalid contact")

    monkeypatch.setattr(pipeline, "compile_tex", exploding_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: placeholder_profile)

    out_dir = tmp_path / "preview"
    with pytest.raises(ValueError, match="placeholder"):
        tailor(json.dumps({"projects": ["proj1"]}), tex_dir=tmp_path, pdf_dir=out_dir)

    assert compiled == []
    assert list(out_dir.glob("*.pdf")) == []


def test_build_canonical_refuses_a_placeholder_contact(placeholder_profile, monkeypatch) -> None:
    """The canonical 3-page view is covered deliberately.

    It carries the same contact header as a delivered resume; "never send it to an employer"
    is a separate rule about page count, not a reason to let it render an unanswerable header.
    """

    def exploding_compile(tex, name, tex_dir, pdf_dir):
        raise AssertionError("compilation must not be reached for an invalid contact")

    monkeypatch.setattr(pipeline, "compile_tex", exploding_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: placeholder_profile)

    with pytest.raises(ValueError, match="placeholder"):
        pipeline.build_canonical()
