from __future__ import annotations

from pathlib import Path

import pytest

from worksisyphus import Pick, Selection, full_selection, render_resume


def test_renders_selected_content_verbatim(small_profile) -> None:
    selection = Selection(
        name="x_resume",
        experiences=(Pick("org-a", ("a1", "a3")),),
        projects=(Pick("proj2", ("q1",)),),
        skills={"languages": ("Python",)},
    )
    tex = render_resume(small_profile, selection)

    assert r"\textbf{\Huge \scshape Simon Chen}" in tex
    assert r"\resumeItem{A one}" in tex
    assert r"\resumeItem{A three}" in tex
    assert "A two" not in tex
    assert "OrgB" not in tex
    assert r"\textbf{Proj \& Two}" in tex
    assert r"\textbf{Languages}{: Python}" in tex
    assert tex.strip().endswith(r"\end{document}")


def test_selection_order_controls_render_order(small_profile) -> None:
    selection = Selection(
        name="x_resume",
        experiences=(Pick("org-b", ("b1",)), Pick("org-a", ("a1",))),
        projects=(Pick("proj1", ("p1",)),),
        skills={"languages": ("Rust",)},
    )
    tex = render_resume(small_profile, selection)
    assert tex.index("OrgB") < tex.index("OrgA")


def test_full_render_of_real_profile_contains_all_sections(real_profile) -> None:
    tex = render_resume(real_profile, full_selection(real_profile))
    for marker in (
        r"\section{Education}",
        r"\section{Experience}",
        r"\section{Projects}",
        r"\section{Technical Skills}",
        r"\$8K",
        r"$\sim$20$\mu$s",
        "github.com/shangminchen",
    ):
        assert marker in tex


def test_render_starts_with_source_template_preamble(real_profile) -> None:
    template = Path("source_of_truth_resume.tex").read_text(encoding="utf-8")
    preamble = template.partition(r"\begin{document}")[0]

    tex = render_resume(real_profile, full_selection(real_profile))

    assert tex.startswith(preamble)
    assert "% Author : Jake Gutierrez" in tex
    assert tex.count(r"\begin{document}") == 1


def test_render_requires_template_document_marker(small_profile, tmp_path) -> None:
    template = tmp_path / "invalid.tex"
    template.write_text(r"\documentclass{article}", encoding="utf-8")

    with pytest.raises(ValueError, match=r"no \\begin\{document\} marker"):
        render_resume(
            small_profile,
            Selection(name="x_resume", experiences=(), projects=(), skills={}),
            template_path=template,
        )
