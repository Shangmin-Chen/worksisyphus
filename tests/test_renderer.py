from __future__ import annotations

import dataclasses
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


def test_full_render_of_real_profile_contains_all_sections(renderable_profile) -> None:
    tex = render_resume(renderable_profile, full_selection(renderable_profile))
    for marker in (
        r"\section{Education}",
        r"\section{Experience}",
        r"\section{Projects}",
        r"\section{Technical Skills}",
        r"\$8K",
        r"$\sim$20$\mu$s",
        renderable_profile.contact.github.replace("https://", ""),
    ):
        assert marker in tex


def test_render_starts_with_source_template_preamble(renderable_profile) -> None:
    template = Path("source_of_truth_resume.tex").read_text(encoding="utf-8")
    preamble = template.partition(r"\begin{document}")[0]

    tex = render_resume(renderable_profile, full_selection(renderable_profile))

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


@pytest.mark.parametrize("field_name", ["name", "email", "phone"])
def test_render_refuses_to_omit_a_required_contact_field(small_profile, field_name) -> None:
    """Regression: an empty phone or email used to render a header silently missing it.

    No gate could catch that -- every one compares the PDF against the profile that rendered
    it -- so the resume looked perfect and could not be answered.
    """
    profile = dataclasses.replace(small_profile, contact=dataclasses.replace(small_profile.contact, **{field_name: ""}))
    with pytest.raises(ValueError, match=f"contact.{field_name} is empty"):
        render_resume(profile, full_selection(profile))


def test_render_allows_missing_optional_links(small_profile) -> None:
    """website/linkedin/github stay optional and are simply omitted from the header."""
    tex = render_resume(small_profile, full_selection(small_profile))
    assert small_profile.contact.phone in tex
    assert f"mailto:{small_profile.contact.email}" in tex
    assert "linkedin" not in tex
