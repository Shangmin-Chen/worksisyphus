from __future__ import annotations

from worksisyphus import full_selection, trim_step


def test_full_selection_includes_everything(small_profile) -> None:
    selection = full_selection(small_profile)
    assert [p.id for p in selection.experiences] == ["org-a", "org-b"]
    assert selection.experiences[0].bullets == ("a1", "a2", "a3")
    assert selection.skills == small_profile.skills


def test_trim_drops_projects_first_then_bullets(small_profile) -> None:
    selection = full_selection(small_profile)

    step1 = trim_step(selection)
    assert step1 is not None
    assert [p.id for p in step1.projects] == ["proj1"]
    assert step1.experiences == selection.experiences

    step2 = trim_step(step1)
    assert step2 is not None
    assert step2.projects[0].bullets == ("p1", "p2")

    # Lowest-ranked experience trims before the top one.
    step3 = trim_step(step2)
    assert step3 is not None
    assert step3.experiences[0].bullets == ("a1", "a2", "a3")
    assert step3.experiences[1].bullets == ("b1", "b2")

    step4 = trim_step(step3)
    assert step4 is not None
    assert step4.experiences[0].bullets == ("a1", "a2")


def test_trim_stops_at_minimums(small_profile) -> None:
    selection = full_selection(small_profile)
    steps = 0
    while (nxt := trim_step(selection)) is not None:
        selection = nxt
        steps += 1
        assert steps < 20, "trim_step must terminate"
    assert len(selection.projects) == 1
    assert all(len(p.bullets) >= 1 for p in selection.projects)
    assert all(len(e.bullets) == 2 for e in selection.experiences)
