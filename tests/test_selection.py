from __future__ import annotations

from worksisyphus import full_selection, trim_step


def test_full_selection_includes_everything(small_profile) -> None:
    selection = full_selection(small_profile)
    assert [p.index for p in selection.experiences] == [0, 1]
    assert selection.experiences[0].bullets == (0, 1, 2)
    assert selection.skills == small_profile.skills


def test_trim_drops_projects_first_then_bullets(small_profile) -> None:
    selection = full_selection(small_profile)

    step1 = trim_step(selection)
    assert [p.index for p in step1.projects] == [0]
    assert step1.experiences == selection.experiences

    step2 = trim_step(step1)
    assert step2.projects[0].bullets == (0, 1)

    # Lowest-ranked experience trims before the top one.
    step3 = trim_step(step2)
    assert step3.experiences[0].bullets == (0, 1, 2)
    assert step3.experiences[1].bullets == (0, 1)

    step4 = trim_step(step3)
    assert step4.experiences[0].bullets == (0, 1)


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
