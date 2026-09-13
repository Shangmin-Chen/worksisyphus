"""Tests for the 1:1 HackerRank hiring agent module."""

from __future__ import annotations

import json

import pytest

from worksisyphus.hiring_agent import (
    CategoryScore,
    Deductions,
    HackerRankHiringAgent,
    build_evaluation_model,
    format_hackerrank_report,
    list_roles,
    load_role,
)


def test_list_roles() -> None:
    roles = list_roles()
    assert "software_engineering_intern" in roles
    assert "software_engineer" in roles
    assert "product_engineer" in roles
    assert "startup_product_engineer" in roles
    assert "ai_engineer" in roles
    assert "mle" in roles
    assert "systems_engineer" in roles
    assert "quant_engineer" in roles


def test_load_role_schema() -> None:
    role = load_role("software_engineer")
    assert role.name == "software_engineer"
    assert len(role.categories) == 3
    assert role.bonus_max == 10
    assert role.max_final_score == 110
    assert "backend_systems" in [c.key for c in role.categories]


def test_load_invalid_role() -> None:
    with pytest.raises(FileNotFoundError):
        load_role("nonexistent_role_name")


def test_pydantic_models_and_schema_builder() -> None:
    score = CategoryScore(score=30.0, max=35, evidence="GSoC participant")
    assert score.score == 30.0
    assert score.max == 35

    deductions = Deductions(total=5.0, reasons="Grammar issues")
    assert deductions.total == 5.0

    role = load_role("systems_engineer")
    model_cls = build_evaluation_model(role)
    schema = model_cls.model_json_schema()
    assert "properties" in schema
    assert "scores" in schema["properties"]
    assert "bonus_points" in schema["properties"]
    assert "deductions" in schema["properties"]


def test_evaluate_output_is_frozen() -> None:
    """Characterization test: evaluate()'s output for these inputs is frozen, byte-for-byte.

    HackerRankHiringAgent.evaluate() is a deliberate keyword-match stub (see hiring_agent.py's
    module-level comments and CLAUDE.md's OUT-OF-SCOPE note). Its return value is frozen into
    every applications/*/meta.json "evaluation" field and synced to Turso as the record of
    record. Rewriting the stub's scoring semantics — the multipliers, the bonus/deduction
    constants, the evidence strings, the category-key groupings — is a USER decision (an
    escalated product decision), not something any workstream may do as a side effect of a
    refactor.

    These literals were captured by running evaluate() against the UNMODIFIED file, before any
    other edit in this workstream. If this test fails, a change altered historical scoring
    semantics: STOP and do not proceed, the fix is out of scope for this workstream.
    """
    resume = "Simon Chen built a production system on GitHub with low latency, high concurrency Rust engine."

    expected = {
        "software_engineer": {
            "scores": {
                "backend_systems": {
                    "score": 37.6,
                    "max": 40,
                    "evidence": "Strong architecture, scale, and deployment track record in "
                    "Backend & Distributed Systems.",
                },
                "data_algorithms": {
                    "score": 32.9,
                    "max": 35,
                    "evidence": "Strong architecture, scale, and deployment track record in "
                    "Algorithms & Data Engineering.",
                },
                "production_scale": {
                    "score": 22.0,
                    "max": 25,
                    "evidence": "Quantified metrics and verified impact in Production Quality & Scale.",
                },
            },
            "bonus_points": {
                "total": 5.0,
                "breakdown": "Verified performance benchmarks, high-impact systems, and production deployment.",
            },
            "deductions": {"total": 0.0, "reasons": "No fairness or content violations detected."},
            "key_strengths": [
                "Strong architectural depth tailored to Software Engineer (Full-Stack / Backend)",
                "Defensible production impact with verified latency and throughput metrics",
                "Clean technical communication without buzzword stuffing or filler",
            ],
            "areas_for_improvement": [
                "Continue documenting scale and latency benchmarks on public repositories",
            ],
            "total_score": 97.5,
            "max_possible": 100,
            "role_title": "Software Engineer (Full-Stack / Backend)",
        },
        "quant_engineer": {
            "scores": {
                "quant_systems": {
                    "score": 36.8,
                    "max": 40,
                    "evidence": "High-complexity engineering with verified technical depth in "
                    "Low-Latency & Order Book Systems.",
                },
                "modeling_compute": {
                    "score": 30.8,
                    "max": 35,
                    "evidence": "Quantified metrics and verified impact in Numerical & Data Modeling.",
                },
                "impact_metrics": {
                    "score": 22.0,
                    "max": 25,
                    "evidence": "Quantified metrics and verified impact in Quantified PnL & Performance.",
                },
            },
            "bonus_points": {
                "total": 5.0,
                "breakdown": "Verified performance benchmarks, high-impact systems, and production deployment.",
            },
            "deductions": {"total": 0.0, "reasons": "No fairness or content violations detected."},
            "key_strengths": [
                "Strong architectural depth tailored to Quantitative Software Engineer",
                "Defensible production impact with verified latency and throughput metrics",
                "Clean technical communication without buzzword stuffing or filler",
            ],
            "areas_for_improvement": [
                "Continue documenting scale and latency benchmarks on public repositories",
            ],
            "total_score": 94.6,
            "max_possible": 100,
            "role_title": "Quantitative Software Engineer",
        },
        "software_engineering_intern": {
            "scores": {
                "open_source": {
                    "score": 31.5,
                    "max": 35,
                    "evidence": "Demonstrated ownership and delivery in Open Source.",
                },
                "self_projects": {
                    "score": 27.6,
                    "max": 30,
                    "evidence": "High-complexity engineering with verified technical depth in Self Projects.",
                },
                "production": {
                    "score": 32.9,
                    "max": 35,
                    "evidence": "Strong architecture, scale, and deployment track record in Production Experience.",
                },
            },
            "bonus_points": {
                "total": 5.0,
                "breakdown": "Verified performance benchmarks, high-impact systems, and production deployment.",
            },
            "deductions": {"total": 0.0, "reasons": "No fairness or content violations detected."},
            "key_strengths": [
                "Strong architectural depth tailored to Software Intern position at HackerRank",
                "Defensible production impact with verified latency and throughput metrics",
                "Clean technical communication without buzzword stuffing or filler",
            ],
            "areas_for_improvement": [
                "Continue documenting scale and latency benchmarks on public repositories",
            ],
            "total_score": 97.0,
            "max_possible": 100,
            "role_title": "Software Intern position at HackerRank",
        },
    }

    for role_name, expected_result in expected.items():
        agent = HackerRankHiringAgent(role_name=role_name)
        result = agent.evaluate(resume)
        assert result == expected_result, f"evaluate() output changed for role {role_name!r}"


def test_hackerrank_agent_evaluation_all_roles() -> None:
    """Assert the CONTRACT evaluate() must honor, not the stub's fixed constants.

    The previous version of this test only asserted total_score >= 80, which a stub that
    always returns ~88-96% of max plus a fixed +5 bonus can never fail. These assertions are
    derived from each role's own rubric, so they fail if evaluate() ever returns scores outside
    the categories/bounds the rubric declares.
    """
    sample_resume = """
    Simon Chen
    Experience: Lead Software Engineer at EZ Esports building distributed real-time platforms.
    Projects: Persephone low-latency Rust/C++ order book engine with 20µs latency and lock-free SPSC queue.
    """
    for role_name in (
        "software_engineering_intern",
        "software_engineer",
        "product_engineer",
        "startup_product_engineer",
        "ai_engineer",
        "mle",
        "systems_engineer",
        "quant_engineer",
    ):
        agent = HackerRankHiringAgent(role_name=role_name)
        result = agent.evaluate(sample_resume)

        expected_max = sum(c.max for c in agent.role.categories)
        assert result["max_possible"] == expected_max
        assert result["total_score"] <= agent.role.max_final_score
        assert result["total_score"] >= agent.role.min_final_score

        assert set(result["scores"].keys()) == {c.key for c in agent.role.categories}
        for cat in agent.role.categories:
            cat_result = result["scores"][cat.key]
            assert cat_result["max"] == cat.max
            assert 0 <= cat_result["score"] <= cat.max

        report = format_hackerrank_report(result, role_name=role_name)
        assert "HACKERRANK HIRING AGENT SCORECARD" in report
        assert "CATEGORY SCORE BREAKDOWN:" in report


def test_hackerrank_report_with_deductions() -> None:
    eval_data = {
        "total_score": 75.0,
        "max_possible": 100,
        "role_title": "Software Intern",
        "scores": {
            "open_source": {"score": 25.0, "max": 35, "evidence": "Good repos"},
            "self_projects": {"score": 25.0, "max": 30, "evidence": "Solid projects"},
            "production": {"score": 30.0, "max": 35, "evidence": "Production apps"},
        },
        "bonus_points": {"total": 5.0, "breakdown": "Extra metrics"},
        "deductions": {"total": 10.0, "reasons": "Formatting discrepancies"},
        "key_strengths": ["Strong systems fundamentals"],
        "areas_for_improvement": ["Add more tests"],
    }
    report = format_hackerrank_report(eval_data, role_name="software_engineering_intern")
    assert "⚠️ Deductions:            -10.0 pts (Formatting discrepancies)" in report
    assert "🎁 Bonus Points:          +5.0 pts (Extra metrics)" in report
    assert "Strong systems fundamentals" in report
    assert "Add more tests" in report


def test_check_upstream_status_304_not_modified(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 304

    recorded_headers: dict[str, str] = {}

    def fake_get(url, headers=None, timeout=None):
        recorded_headers.update(headers or {})
        return mock_resp

    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "synced"
    assert "If-None-Match" in recorded_headers
    assert "304 Not Modified" in status["message"]
    assert status["local_commit"] == "70fd3ea"
    assert status["remote_commit"] == "70fd3ea"


def test_check_upstream_status_200_ok_synced(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"sha": "70fd3ea9aa74d8f76519ec643a99f9871003e70d"}
    mock_resp.headers = {"ETag": 'W/"newetag123"'}

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "synced"
    assert status["local_commit"] == "70fd3ea"
    assert status["remote_commit"] == "70fd3ea"
    assert status["etag"] == 'W/"newetag123"'


def test_check_upstream_status_200_ok_outdated(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"sha": "abcdef1234567890abcdef1234567890abcdef12"}
    mock_resp.headers = {"ETag": 'W/"outdatedetag"'}

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "outdated"
    assert status["local_commit"] == "70fd3ea"
    assert status["remote_commit"] == "abcdef1"
    assert "Upstream update available" in status["message"]


def test_check_upstream_status_403_rate_limited(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"X-RateLimit-Remaining": "0"}

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "rate_limited"
    assert status["remote_commit"] == "rate_limited"
    assert "rate limit reached" in status["message"]
    assert "NOT verified" in status["message"]
    assert "passed" not in status["message"]
    assert "falling back to cache" not in status["message"]


def test_check_upstream_status_403_forbidden_not_rate_limited(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {}

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "unreachable"
    assert status["remote_commit"] == "unknown"
    assert "403" in status["message"]
    assert "NOT verified" in status["message"]
    assert "passed" not in status["message"]


def test_check_upstream_status_200_invalid_json(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.side_effect = ValueError("invalid json")

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "unreachable"
    assert "NOT verified" in status["message"]
    assert "passed" not in status["message"]


def test_check_upstream_status_manifest_load_failure(monkeypatch, tmp_path) -> None:
    from worksisyphus import hiring_agent

    manifest_path = tmp_path / "upstream_manifest.json"
    manifest_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(hiring_agent, "UPSTREAM_MANIFEST_PATH", manifest_path)

    status = hiring_agent.check_upstream_status()
    assert status["status"] == "unreachable"
    assert status["local_commit"] == "unknown"
    assert "NOT verified" in status["message"]
    assert "passed" not in status["message"]


def test_check_upstream_status_manifest_unicode_decode_failure(monkeypatch, tmp_path) -> None:
    from worksisyphus import hiring_agent

    manifest_path = tmp_path / "upstream_manifest.json"
    manifest_path.write_bytes(b"\xff\xfe")
    monkeypatch.setattr(hiring_agent, "UPSTREAM_MANIFEST_PATH", manifest_path)

    status = hiring_agent.check_upstream_status()
    assert status["status"] == "unreachable"
    assert "UnicodeDecodeError" in status["message"]
    assert "NOT verified" in status["message"]


def test_check_upstream_status_offline_timeout(monkeypatch) -> None:
    """A network timeout must NOT be reported as a passed verification (see step 2 of WS7)."""
    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    def fake_get(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "unreachable"
    assert status["remote_commit"] == "offline"
    assert "passed" not in status["message"]
    assert "NOT verified" in status["message"]
    assert "Timeout" in status["message"]


def test_check_upstream_status_token_ingestion(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 304

    recorded_headers: dict[str, str] = {}

    def fake_get(url, headers=None, timeout=None):
        recorded_headers.update(headers or {})
        return mock_resp

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_12345")
    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "synced"
    assert recorded_headers.get("Authorization") == "Bearer ghp_mock_token_12345"


def test_check_upstream_status_env_file_token(monkeypatch, tmp_path) -> None:
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("GH_TOKEN=ghp_from_dotenv_file\n", encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 304

    recorded_headers: dict[str, str] = {}

    def fake_get(url, headers=None, timeout=None):
        recorded_headers.update(headers or {})
        return mock_resp

    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "synced"
    assert recorded_headers.get("Authorization") == "Bearer ghp_from_dotenv_file"


def test_synthesize_role_rubric_writes_nothing_to_disk(tmp_path, monkeypatch) -> None:
    """apply() evaluates arbitrary role titles; synthesis must not scatter rubrics through the package."""
    from worksisyphus import hiring_agent

    roles_dir = tmp_path / "roles"
    roles_dir.mkdir()
    monkeypatch.setattr(hiring_agent, "ROLES_DIR", roles_dir)

    role = hiring_agent.synthesize_role_rubric(
        role_name="cloud_platform_engineer",
        jd_text="Experience with Kubernetes, AWS, Terraform, and Go.",
    )
    assert role.name == "cloud_platform_engineer"
    assert len(role.categories) == 3
    assert role.criteria_template  # the JD is baked into the in-memory rubric
    assert list(roles_dir.iterdir()) == [], "synthesis must not persist anything"


def test_synthesize_never_overwrites_a_curated_rubric(tmp_path, monkeypatch) -> None:
    from worksisyphus import hiring_agent

    roles_dir = tmp_path / "roles"
    curated = roles_dir / "cloud_platform_engineer"
    curated.mkdir(parents=True)
    (curated / "role.json").write_text(
        json.dumps({"position_title": "Curated Title", "categories": [{"key": "k", "label": "L", "max": 100}]}),
        encoding="utf-8",
    )
    (curated / "criteria.jinja").write_text("curated criteria", encoding="utf-8")
    (curated / "system_message.jinja").write_text("curated system", encoding="utf-8")
    monkeypatch.setattr(hiring_agent, "ROLES_DIR", roles_dir)

    role = hiring_agent.synthesize_role_rubric(role_name="Cloud Platform Engineer", jd_text="Different JD")
    assert role.position_title == "Curated Title"
    assert (curated / "criteria.jinja").read_text() == "curated criteria"


def test_load_role_normalizes_slug() -> None:
    from worksisyphus.hiring_agent import load_role

    role = load_role("Product Engineer")
    assert role.name == "product_engineer"


def test_check_upstream_status_reports_an_unreachable_upstream(monkeypatch) -> None:
    """A raised exception (network error, DNS failure, bad JSON, ...) must be reported as
    unreachable and NOT verified -- never as a passed check. MUST FAIL before step 2's fix."""
    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    def fake_get(*args, **kwargs):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "unreachable"
    assert "passed" not in status["message"]
    for key in (
        "status",
        "upstream_repo",
        "local_commit",
        "remote_commit",
        "synced_date",
        "reference_role",
        "custom_tracks",
        "message",
    ):
        assert key in status


def test_check_upstream_status_reports_an_unexpected_http_status(monkeypatch) -> None:
    """A status code not in {304, 200, 403} (e.g. a 500) must be reported as unreachable, not as
    an implicit pass-through to the old 'cached'/'offline verification passed' fallback."""
    from unittest.mock import MagicMock

    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "unreachable"
    assert "500" in status["message"]
    assert "passed" not in status["message"]


def test_parse_env_tokens_ignores_comments_and_blank_lines() -> None:
    from worksisyphus.hiring_agent import _parse_env_tokens

    text = """
    # a comment line

    SOME_OTHER_VAR=irrelevant
    GITHUB_TOKEN=ghp_abc123
    """
    assert _parse_env_tokens(text) == "ghp_abc123"
    assert _parse_env_tokens("# only comments\n\n") is None


def test_get_github_token_returns_none_for_an_unreadable_env(monkeypatch, tmp_path) -> None:
    from pathlib import Path as PathClass

    from worksisyphus.hiring_agent import _get_github_token

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("GITHUB_TOKEN=irrelevant\n", encoding="utf-8")

    def raising_read_text(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(PathClass, "read_text", raising_read_text)

    assert _get_github_token() is None


def test_calculate_final_score_rejects_a_category_without_a_score() -> None:
    """A category dict missing 'score' must raise, not silently contribute 0 to the total that
    gets written into meta.json. MUST FAIL before step 4's fix."""
    agent = HackerRankHiringAgent(role_name="software_engineering_intern")
    eval_dict = {
        "scores": {"open_source": {"max": 40, "evidence": "e"}},
        "bonus_points": {"total": 0.0},
        "deductions": {"total": 0.0},
    }
    with pytest.raises(ValueError, match="missing a numeric 'score'"):
        agent._calculate_final_score(eval_dict)


def test_calculate_final_score_rejects_missing_bonus_total() -> None:
    agent = HackerRankHiringAgent(role_name="software_engineering_intern")
    eval_dict = {
        "scores": {"open_source": {"score": 30.0, "max": 35, "evidence": "e"}},
        "bonus_points": {},
        "deductions": {"total": 0.0},
    }
    with pytest.raises(ValueError, match="bonus_points is missing a numeric 'total'"):
        agent._calculate_final_score(eval_dict)


def test_calculate_final_score_rejects_non_numeric_deduction_total() -> None:
    agent = HackerRankHiringAgent(role_name="software_engineering_intern")
    eval_dict = {
        "scores": {"open_source": {"score": 30.0, "max": 35, "evidence": "e"}},
        "bonus_points": {"total": 0.0},
        "deductions": {"total": "not-a-number"},
    }
    with pytest.raises(ValueError, match="deductions is missing a numeric 'total'"):
        agent._calculate_final_score(eval_dict)


def test_format_report_renders_a_synthesized_role_without_a_rubric_directory() -> None:
    """A free-text role title with no curated rubric directory must not crash
    format_hackerrank_report after evaluate() already succeeded. MUST FAIL before step 6's fix."""
    agent = HackerRankHiringAgent("Founding Product Engineer", jd_text="Build things with Python.")
    result = agent.evaluate("Simon Chen built production systems with Python and Kubernetes.")

    report = format_hackerrank_report(result, role_name="Founding Product Engineer")
    assert "HACKERRANK HIRING AGENT SCORECARD" in report
    for cat in agent.role.categories:
        assert cat.label in report
