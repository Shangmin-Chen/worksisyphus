from __future__ import annotations

from worksisyphus import full_selection, trim_step


def test_full_selection_includes_everything(small_profile) -> None:
    selection = full_selection(small_profile)
    assert [p.id for p in selection.experiences] == ["org-a", "org-b"]
    assert selection.experiences[0].bullets == ("a1", "a2", "a3")
    assert selection.skills == small_profile.skills


def test_trim_drops_projects_first_then_bullets(small_profile) -> None:
    selection = full_selection(small_profile)

    # 1. Extra lowest-ranked project is dropped first
    step1 = trim_step(selection)
    assert step1 is not None
    next1, cut1 = step1
    assert cut1.kind == "project" and cut1.slug == "proj2"
    assert [p.id for p in next1.projects] == ["proj1"]
    assert next1.experiences == selection.experiences

    # 2. Lowest-ranked experience trims before the top one, and before the top project
    step2 = trim_step(next1)
    assert step2 is not None
    next2, cut2 = step2
    assert cut2.kind == "experience-bullet" and cut2.slug == "org-b" and cut2.bullet == "b3"
    assert "org-b" in cut2.log_line()
    assert next2.experiences[0].bullets == ("a1", "a2", "a3")
    assert next2.experiences[1].bullets == ("b1", "b2")
    assert next2.projects[0].bullets == ("p1", "p2", "p3")

    # 3. Next experience trims before gutting the top project
    step3 = trim_step(next2)
    assert step3 is not None
    next3, cut3 = step3
    assert cut3.kind == "experience-bullet" and cut3.slug == "org-a" and cut3.bullet == "a3"
    assert next3.experiences[0].bullets == ("a1", "a2")
    assert next3.projects[0].bullets == ("p1", "p2", "p3")

    # 4. Only after all experiences reach MIN_BULLETS does the top project's bullets trim
    step4 = trim_step(next3)
    assert step4 is not None
    next4, cut4 = step4
    assert cut4.kind == "project-bullet" and cut4.slug == "proj1" and cut4.bullet == "p3"
    assert next4.projects[0].bullets == ("p1", "p2")


def test_trim_does_not_gut_top_project_before_lower_ranked_experiences(small_profile) -> None:
    """One high-ranked project with > MIN_BULLETS and two experiences;
    overflow trim must not reduce the top project before lower-ranked experience bullets."""
    selection = full_selection(small_profile)
    # Drop down to 1 project
    selection, _ = trim_step(selection)  # type: ignore[misc]
    assert len(selection.projects) == 1
    assert len(selection.projects[0].bullets) > 2

    # Trimming should reduce org-b, not the top project
    next_sel, cut = trim_step(selection)  # type: ignore[misc]
    assert cut.kind == "experience-bullet"
    assert cut.slug == "org-b"
    assert len(next_sel.projects[0].bullets) == len(selection.projects[0].bullets)


def test_trim_stops_at_minimums(small_profile) -> None:
    selection = full_selection(small_profile)
    steps = 0
    while (nxt := trim_step(selection)) is not None:
        selection, _cut = nxt
        steps += 1
        assert steps < 20, "trim_step must terminate"
    assert len(selection.projects) == 1
    assert all(len(p.bullets) >= 1 for p in selection.projects)
    assert all(len(e.bullets) == 2 for e in selection.experiences)
