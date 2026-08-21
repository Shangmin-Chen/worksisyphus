"""Tests for the 1:1 HackerRank hiring agent module."""

from __future__ import annotations

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


def test_hackerrank_agent_evaluation_all_roles() -> None:
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
        assert result["total_score"] >= 80
        assert "scores" in result
        assert len(result["scores"]) == 3
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

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_resp)

    status = check_upstream_status()
    assert status["status"] == "rate_limited"
    assert status["remote_commit"] == "rate_limited"
    assert "rate limit reached" in status["message"]


def test_check_upstream_status_offline_timeout(monkeypatch) -> None:
    import requests

    from worksisyphus.hiring_agent import check_upstream_status

    def fake_get(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "get", fake_get)

    status = check_upstream_status()
    assert status["status"] == "cached"
    assert status["remote_commit"] == "offline"
    assert "offline verification passed" in status["message"]


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


def test_synthesize_role_rubric_and_cleanup(tmp_path, monkeypatch) -> None:
    from worksisyphus import hiring_agent

    monkeypatch.setattr(hiring_agent, "ROLES_DIR", tmp_path / "roles")
    (tmp_path / "roles").mkdir()

    role = hiring_agent.synthesize_role_rubric(
        role_name="cloud_platform_engineer",
        jd_text="Experience with Kubernetes, AWS, Terraform, and Go.",
    )
    assert role.name == "cloud_platform_engineer"
    assert len(role.categories) == 3
    assert (tmp_path / "roles" / "cloud_platform_engineer" / "role.json").is_file()
    assert (tmp_path / "roles" / "cloud_platform_engineer" / "criteria.jinja").is_file()

    # Verify that calling synthesize on an existing role does not overwrite it
    (tmp_path / "roles" / "cloud_platform_engineer" / "role.json").write_text('{"categories": []}', encoding="utf-8")
    existing_role = hiring_agent.synthesize_role_rubric(
        role_name="cloud_platform_engineer",
        jd_text="Different JD",
    )
    assert existing_role.name == "cloud_platform_engineer"


def test_load_role_normalizes_slug() -> None:
    from worksisyphus.hiring_agent import load_role

    role = load_role("Product Engineer")
    assert role.name == "product_engineer"
