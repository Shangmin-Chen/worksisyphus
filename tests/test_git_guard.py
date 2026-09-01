from __future__ import annotations

import json
import subprocess
from pathlib import Path

from worksisyphus.application import apply
from worksisyphus.compiler import CompileResult
from worksisyphus.db import sync_to_turso
from worksisyphus.gates import ATSCheckResult, GateResult
from worksisyphus.git_guard import GitFreshnessResult, check_git_freshness_for_sync


def _make_runner(responses: dict[tuple[str, ...], subprocess.CompletedProcess]):
    def fake_run(cmd, *args, **kwargs):
        tuple_cmd = tuple(cmd)
        if tuple_cmd in responses:
            return responses[tuple_cmd]
        # Partial match prefix fallback
        for key, resp in responses.items():
            if tuple_cmd[: len(key)] == key:
                return resp
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return fake_run


def test_git_freshness_allows_clean_main_branch():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess([], 0, "true\n", ""),
            ("git", "-C", ".", "branch", "--show-current"): subprocess.CompletedProcess([], 0, "main\n", ""),
            ("git", "-C", ".", "fetch", "origin", "main"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", ".", "rev-list", "--count", "HEAD..origin/main"): subprocess.CompletedProcess(
                [], 0, "0\n", ""
            ),
        }
    )
    result = check_git_freshness_for_sync(runner=runner)
    assert result.allowed is True
    assert result.branch == "main"
    assert result.behind_count == 0


def test_git_freshness_rejects_feature_branch_by_default():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess([], 0, "true\n", ""),
            ("git", "-C", ".", "branch", "--show-current"): subprocess.CompletedProcess([], 0, "feat/experiment\n", ""),
        }
    )
    result = check_git_freshness_for_sync(runner=runner)
    assert result.allowed is False
    assert result.branch == "feat/experiment"
    assert "Cloud sync is restricted to 'main'" in result.reason


def test_git_freshness_allows_feature_branch_when_allow_any_branch_set():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess([], 0, "true\n", ""),
            ("git", "-C", ".", "branch", "--show-current"): subprocess.CompletedProcess([], 0, "feat/experiment\n", ""),
            ("git", "-C", ".", "fetch", "origin", "main"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", ".", "rev-list", "--count", "HEAD..origin/main"): subprocess.CompletedProcess(
                [], 0, "0\n", ""
            ),
        }
    )
    result = check_git_freshness_for_sync(allow_any_branch=True, runner=runner)
    assert result.allowed is True
    assert result.branch == "feat/experiment"


def test_git_freshness_rejects_detached_head_by_default():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess([], 0, "true\n", ""),
            ("git", "-C", ".", "branch", "--show-current"): subprocess.CompletedProcess([], 0, "\n", ""),
        }
    )
    result = check_git_freshness_for_sync(runner=runner)
    assert result.allowed is False
    assert result.branch == "(detached HEAD)"
    assert "Detached HEAD state" in result.reason


def test_git_freshness_rejects_when_behind_upstream():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess([], 0, "true\n", ""),
            ("git", "-C", ".", "branch", "--show-current"): subprocess.CompletedProcess([], 0, "main\n", ""),
            ("git", "-C", ".", "fetch", "origin", "main"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", ".", "rev-list", "--count", "HEAD..origin/main"): subprocess.CompletedProcess(
                [], 0, "3\n", ""
            ),
        }
    )
    result = check_git_freshness_for_sync(runner=runner)
    assert result.allowed is False
    assert result.behind_count == 3
    assert "behind origin/main by 3 commit(s)" in result.reason
    assert "git pull" in result.reason


def test_git_freshness_handles_fetch_timeout_and_offline():
    def exploding_fetch(cmd, *args, **kwargs):
        if "fetch" in cmd:
            raise subprocess.TimeoutExpired(cmd, 2.0)
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if "branch" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "main\n", "")
        if "rev-list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "0\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    result = check_git_freshness_for_sync(runner=exploding_fetch)
    assert result.allowed is True
    assert result.branch == "main"


def test_git_freshness_rejects_non_git_directory():
    runner = _make_runner(
        {
            ("git", "-C", ".", "rev-parse", "--is-inside-work-tree"): subprocess.CompletedProcess(
                [], 128, "", "fatal: not a git repository"
            ),
        }
    )
    result = check_git_freshness_for_sync(runner=runner)
    assert result.allowed is False
    assert "Not inside a git work tree" in result.reason


def test_sync_to_turso_skips_when_git_guard_disallows(monkeypatch, tmp_path):

    fake_db = tmp_path / "worksisyphus.db"
    fake_db.write_bytes(b"")

    monkeypatch.setattr(
        "worksisyphus.git_guard.check_git_freshness_for_sync",
        lambda **kw: GitFreshnessResult(allowed=False, reason="behind origin/main by 2 commits"),
    )

    logs: list[str] = []
    synced = sync_to_turso(db_path=fake_db, log=logs.append)
    assert synced is False
    assert any("behind origin/main by 2 commits" in log for log in logs)


def test_sync_to_turso_bypasses_git_guard_when_no_git_check_set(monkeypatch, tmp_path):
    fake_db = tmp_path / "worksisyphus.db"
    fake_db.write_bytes(b"")

    guard_called = False

    def fake_guard(**kw):
        nonlocal guard_called
        guard_called = True
        return GitFreshnessResult(allowed=False, reason="should not be called")

    monkeypatch.setattr("worksisyphus.git_guard.check_git_freshness_for_sync", fake_guard)
    # Turso CLI missing will cause False, but guard is bypassed
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    sync_to_turso(db_path=fake_db, no_git_check=True)
    assert guard_called is False


def test_apply_completes_local_generation_even_if_cloud_sync_is_skipped(small_profile, monkeypatch, tmp_path):
    import worksisyphus.application as app_module
    import worksisyphus.pipeline as pipe_module

    def fake_compile(tex: str, name: str, tex_dir, pdf_dir) -> CompileResult:
        pdf_path = pdf_dir / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=pdf_path, tex_path=tex_dir / f"{name}.tex", pages=1)

    monkeypatch.setattr(pipe_module, "compile_tex", fake_compile)
    monkeypatch.setattr(
        app_module,
        "run_resume_gates",
        lambda *a, **kw: (
            (GateResult("ATS", True, ()),),
            ATSCheckResult(True, (), 1, 100, "Simon Chen text"),
        ),
    )
    monkeypatch.setattr(
        "worksisyphus.git_guard.check_git_freshness_for_sync",
        lambda **kw: GitFreshnessResult(allowed=False, reason="Current branch is 'feat/foo'"),
    )

    logs: list[str] = []
    apps_dir = tmp_path / "applications"
    db_file = tmp_path / "worksisyphus.db"
    from worksisyphus.db import get_connection, init_schema

    conn = get_connection(db_file)
    init_schema(conn)
    conn.close()

    folder, _res, _ats = apply(
        plan_text=json.dumps({"experiences": {"org-a": ["a1"]}}),
        jd_text="Distributed systems",
        company="Acme Corp",
        profile=small_profile,
        applications_dir=apps_dir,
        db_path=db_file,
        sync_cloud=True,
        log=logs.append,
    )

    # Local files exist and are complete
    assert folder.is_dir()
    assert (folder / "Simon_Chen_Resume.pdf").is_file()
    assert (folder / "meta.json").is_file()
    assert (folder / "plan.json").is_file()
    # Warning was logged about skipped cloud sync
    assert any("Turso cloud sync skipped" in log and "feat/foo" in log for log in logs)
