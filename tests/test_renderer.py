from __future__ import annotations

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
