"""Tests for the SQLite database layer and append-only audit log."""

from __future__ import annotations

import json
from pathlib import Path

from worksisyphus.db import (
    export_profile_json,
    get_audit_history,
    get_connection,
    init_schema,
    list_applications_from_db,
    load_profile_from_db,
    log_audit_event,
    save_application_to_db,
    seed_database,
    update_application_status_in_db,
)


def test_init_schema_creates_tables() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    expected = {
        "contact",
        "education",
        "experiences",
        "experience_bullets",
        "projects",
        "project_bullets",
        "skills",
        "audit_events",
        "applications",
    }
    assert expected.issubset(tables)


def test_seed_and_load_profile(tmp_path: Path) -> None:
    profile_file = tmp_path / "profile.json"
    profile_data = {
        "contact": {
            "name": "Test Candidate",
            "email": "candidate@example.com",
            "phone": "555-1234",
            "website": "https://candidate.com",
            "github": "https://github.com/candidate",
            "linkedin": "https://linkedin.com/in/candidate",
        },
        "education": [
            {
                "institution": "Tech University",
                "location": "Boston, MA",
                "degree": "BS in CS",
                "date": "May 2026",
                "coursework": ["Algorithms", "OS"],
            }
        ],
        "experiences": {
            "startup": {
                "role": "SWE Intern",
                "org": "Startup Co",
                "location": "Remote",
                "date": "Summer 2025",
                "bullets": {
                    "feature-x": "Implemented feature X with 99% test coverage.",
                    "pipeline-y": "Built ETL pipeline processing 1M events.",
                },
            }
        },
        "projects": {
            "awesome-proj": {
                "name": "Awesome Project",
                "tech": "Rust, Python",
                "date": "2026",
                "bullets": {
                    "core-engine": "Engineered core engine benchmarked at 100ns.",
                },
            }
        },
        "skills": {
            "languages": ["Python", "Rust"],
            "databases": ["PostgreSQL", "SQLite"],
        },
    }
    profile_file.write_text(json.dumps(profile_data), encoding="utf-8")

    conn = get_connection(":memory:")
    seed_database(conn, profile_path=profile_file, applications_dir=tmp_path / "apps")

    profile = load_profile_from_db(conn)
    assert profile.contact.name == "Test Candidate"
    assert profile.contact.email == "candidate@example.com"
    assert len(profile.education) == 1
    assert profile.education[0].institution == "Tech University"
    assert profile.education[0].coursework == ("Algorithms", "OS")
    assert "startup" in profile.experiences
    assert profile.experiences["startup"].role == "SWE Intern"
    assert profile.experiences["startup"].bullets["feature-x"] == "Implemented feature X with 99% test coverage."
    assert "awesome-proj" in profile.projects
    assert profile.skills["languages"] == ("Python", "Rust")


def test_audit_event_logging() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)

    log_audit_event(
        conn=conn,
        entity_type="experience",
        entity_id="startup",
        action="UPDATE",
        field_name="role",
        old_value="Junior SWE",
        new_value="Lead SWE",
    )

    history = get_audit_history(conn, limit=10)
    assert len(history) == 1
    ev = history[0]
    assert ev["entity_type"] == "experience"
    assert ev["entity_id"] == "startup"
    assert ev["action"] == "UPDATE"
    assert ev["field_name"] == "role"
    assert ev["old_value"] == "Junior SWE"
    assert ev["new_value"] == "Lead SWE"
    assert ev["timestamp"] is not None


def test_application_tracking_in_db() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)

    save_application_to_db(
        conn=conn,
        app_id="2026-08-18_test_corp",
        company="Test Corp",
        role="Software Engineer",
        date_str="2026-08-18",
        source_url="https://example.com/job",
        status="applied",
        jd_text="Job Description text",
        plan_json="{}",
    )

    apps = list_applications_from_db(conn)
    assert len(apps) == 1
    assert apps[0]["folder"] == "2026-08-18_test_corp"
    assert apps[0]["company"] == "Test Corp"
    assert apps[0]["status"] == "applied"

    # Status update
    app_id, old_st, new_st = update_application_status_in_db(conn, "test_corp", "phone_screen")
    assert app_id == "2026-08-18_test_corp"
    assert old_st == "applied"
    assert new_st == "phone_screen"

    apps_updated = list_applications_from_db(conn)
    assert apps_updated[0]["status"] == "phone_screen"

    # Audit events verify status change
    history = get_audit_history(conn, entity_type="application")
    assert len(history) == 2
    assert history[0]["action"] == "STATUS_CHANGE"
    assert history[0]["old_value"] == "applied"
    assert history[0]["new_value"] == "phone_screen"


def test_export_profile_json(tmp_path: Path) -> None:
    conn = get_connection(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO contact (id, name, email, phone, website, github, linkedin) VALUES (1, 'Jane', 'j@e.com', '', '', '', '')"
    )
    conn.commit()

    export_path = tmp_path / "exported_profile.json"
    data = export_profile_json(conn, output_path=export_path)
    assert data["contact"]["name"] == "Jane"
    assert export_path.is_file()
    loaded = json.loads(export_path.read_text(encoding="utf-8"))
    assert loaded["contact"]["name"] == "Jane"


def test_schema_indexes_created() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cur.fetchall()}
    assert "idx_audit_events_entity" in indexes
    assert "idx_audit_events_timestamp" in indexes
    assert "idx_applications_date" in indexes


def test_get_audit_history_filtered() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)
    log_audit_event(conn, "project", "p1", "INSERT")
    log_audit_event(conn, "experience", "e1", "INSERT")
    log_audit_event(conn, "project", "p2", "UPDATE")

    proj_events = get_audit_history(conn, entity_type="project")
    assert len(proj_events) == 2
    assert all(e["entity_type"] == "project" for e in proj_events)

    all_events = get_audit_history(conn)
    assert len(all_events) == 3


def test_real_profile_json_roundtrip_through_db(tmp_path: Path) -> None:
    real_profile_path = Path("profile.json")
    if not real_profile_path.is_file():
        real_profile_path = Path("tests/fixtures/profile.json")
    real_data = json.loads(real_profile_path.read_text(encoding="utf-8"))

    conn = get_connection(":memory:")
    seed_database(conn, profile_path=real_profile_path, applications_dir=tmp_path / "apps")

    export_path = tmp_path / "exported.json"
    exported_data = export_profile_json(conn, output_path=export_path)

    assert exported_data["contact"] == real_data["contact"]
    assert exported_data["education"] == real_data["education"]
    assert exported_data["experiences"] == real_data["experiences"]
    assert exported_data["projects"] == real_data["projects"]
    assert exported_data["skills"] == real_data["skills"]
