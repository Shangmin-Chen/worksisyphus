from __future__ import annotations

import hashlib
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
    provenance = json.loads((tmp_path / ".provenance.json").read_text(encoding="utf-8"))
    assert provenance == {
        "plan_hash": hashlib.sha256(_plan_text().encode("utf-8")).hexdigest(),
        "pdf_hash": hashlib.sha256(b"%PDF-fake").hexdigest(),
    }


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


def test_tailor_invalidates_provenance_before_compile(small_profile, monkeypatch, tmp_path) -> None:
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    provenance_path = pdf_dir / ".provenance.json"
    provenance_path.write_text(json.dumps({"plan_hash": "old-plan", "pdf_hash": "old-pdf"}), encoding="utf-8")

    def failed_compile(tex: str, name: str, tex_dir, output_dir) -> CompileResult:
        (output_dir / f"{name}.pdf").write_bytes(b"partially replaced")
        raise RuntimeError("compiler failed")

    monkeypatch.setattr(pipeline, "compile_tex", failed_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    with pytest.raises(RuntimeError, match="compiler failed"):
        tailor(_plan_text(), tex_dir=tmp_path / "tex", pdf_dir=pdf_dir)

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance == {"plan_hash": hashlib.sha256(_plan_text().encode("utf-8")).hexdigest()}


def test_tailor_normalizes_crlf_for_plan_hash(small_profile, monkeypatch, tmp_path) -> None:
    plan_text = _plan_text().replace("{", "{\r\n", 1)

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    monkeypatch.setattr(pipeline, "compile_tex", fake_compile)
    monkeypatch.setattr(pipeline, "load_profile", lambda _path: small_profile)

    tailor(plan_text, tex_dir=tmp_path / "tex", pdf_dir=tmp_path)

    provenance = json.loads((tmp_path / ".provenance.json").read_text(encoding="utf-8"))
    normalized_plan = plan_text.replace("\r\n", "\n")
    assert provenance["plan_hash"] == hashlib.sha256(normalized_plan.encode("utf-8")).hexdigest()
