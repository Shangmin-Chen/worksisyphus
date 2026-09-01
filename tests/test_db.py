"""Tests for the SQLite database layer and append-only audit log."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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

#: A contact block that passes validate_contact: a real-looking name, a deliverable address
#: and a number outside the reserved 555 exchange.
DELIVERABLE_CONTACT = {
    "name": "Simon Chen",
    "email": "simon.chen@fixture.test",
    "phone": "617-266-1810",
    "website": "https://simonchen.dev",
    "github": "https://github.com/fixture-user",
    "linkedin": "https://linkedin.com/in/fixture-user",
}


def _fixture_data_with_deliverable_contact(source: Path | None = None) -> dict[str, Any]:
    """The full test fixture, with its scrubbed contact block swapped for a deliverable one.

    tests/fixtures/profile.json must keep its example.com / 555-555-5555 contact: several
    tests exist precisely to prove that block is rejected, and one of them recreates the
    original incident by planting the fixture where the old fallback looked for it. But
    seed_database now validates the contact of whatever it loads, so the seeding tests -- all
    of which are about audit events, deletions and round-trip fidelity, never about the
    header -- can no longer feed it the fixture verbatim. Swapping only the contact keeps the
    rest of the fixture (its education, experiences, bullets, projects and skills) exactly as
    those tests have always exercised it.
    """
    source = source or Path(__file__).resolve().parent / "fixtures" / "profile.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["contact"] = dict(DELIVERABLE_CONTACT)
    return data


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
    """Structural round-trip: everything written by a seed comes back out of the database.

    The contact block here is deliberately *not* a placeholder. It used to read
    ``candidate@example.com`` / ``555-1234``, which was harmless when seed_database only
    checked that profile.json existed, but seeding now validates what it loaded and would
    reject that block before writing a row. What this test was written to cover is shape --
    education, experiences, bullets, projects, skills surviving the trip -- so swapping in a
    deliverable contact keeps every one of those assertions intact and adds one: that a good
    contact block still seeds. The placeholder path has its own tests below.
    """
    profile_file = tmp_path / "profile.json"
    profile_data = {
        "contact": {
            "name": "Test Candidate",
            "email": "candidate@fixture.test",
            "phone": "617-266-1810",
            "website": "https://candidate.dev",
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
    assert profile.contact.email == "candidate@fixture.test"
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
    # A deliverable contact block: export refuses to write anything less (see the
    # placeholder tests below), so the happy path needs real-shaped details.
    conn.execute(
        "INSERT INTO contact (id, name, email, phone, website, github, linkedin) "
        "VALUES (1, 'Jane Roe', 'jane.roe@fastmail.dev', '617-266-1810', '', '', '')"
    )
    conn.commit()

    export_path = tmp_path / "exported_profile.json"
    data = export_profile_json(conn, output_path=export_path)
    assert data["contact"]["name"] == "Jane Roe"
    assert export_path.is_file()
    loaded = json.loads(export_path.read_text(encoding="utf-8"))
    assert loaded["contact"]["name"] == "Jane Roe"


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
    """Everything profile.json holds must survive a trip through the database unchanged.

    Read back with ``profile_to_dict`` rather than ``export_profile_json``: on CI there is no
    profile.json, so this runs against the scrubbed fixture, and export deliberately refuses
    to write a placeholder contact block. Export's own write path is covered by
    ``test_export_profile_json``; what is under test here is fidelity, not writing.

    Seeding now validates the contact of what it loads, so the fixture's scrubbed block is
    swapped for a deliverable one before seeding -- and only when the real profile is absent.
    On a developer machine this still runs against the genuine profile.json unchanged, which
    is the case worth having: the fixture is small, the real profile is where an unhandled
    field would actually hide.
    """
    from worksisyphus.profile import profile_to_dict

    real_profile_path = Path("profile.json")
    if not real_profile_path.is_file():
        real_profile_path = tmp_path / "fixture_profile.json"
        real_profile_path.write_text(
            json.dumps(_fixture_data_with_deliverable_contact(Path("tests/fixtures/profile.json"))),
            encoding="utf-8",
        )
    real_data = json.loads(real_profile_path.read_text(encoding="utf-8"))

    conn = get_connection(":memory:")
    seed_database(conn, profile_path=real_profile_path, applications_dir=tmp_path / "apps")

    exported_data = profile_to_dict(load_profile_from_db(conn))

    assert exported_data["contact"] == real_data["contact"]
    assert exported_data["education"] == real_data["education"]
    assert exported_data["experiences"] == real_data["experiences"]
    assert exported_data["projects"] == real_data["projects"]
    assert exported_data["skills"] == real_data["skills"]


def test_build_sync_sql_places_drops_inside_the_transaction() -> None:
    """A failed restore must roll the drops back, so they cannot precede BEGIN TRANSACTION."""
    from worksisyphus.db import build_sync_sql

    dump = "PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\nCREATE TABLE contact (id INTEGER);\nCOMMIT;\n"
    sql = build_sync_sql(dump)
    assert sql is not None

    begin_at = sql.index("BEGIN TRANSACTION;")
    first_drop_at = sql.index("DROP TABLE IF EXISTS")
    commit_at = sql.index("COMMIT;")
    assert begin_at < first_drop_at < commit_at
    assert sql.index("CREATE TABLE") > first_drop_at


def test_build_sync_sql_rejects_unusable_dumps() -> None:
    from worksisyphus.db import build_sync_sql

    assert build_sync_sql("") is None
    assert build_sync_sql("   \n  ") is None
    # A dump with no schema means sqlite3 produced nothing worth pushing.
    assert build_sync_sql("BEGIN TRANSACTION;\nCOMMIT;\n") is None
    # A dump with no transaction wrapper cannot be spliced safely.
    assert build_sync_sql("CREATE TABLE contact (id INTEGER);\n") is None


def _seed_fixture(tmp_path: Path) -> tuple[Any, Path]:
    """Return an in-memory connection plus a writable profile file seeded from the test fixture."""
    from worksisyphus.db import get_connection

    profile_file = tmp_path / "profile.json"
    profile_file.write_text(json.dumps(_fixture_data_with_deliverable_contact()), encoding="utf-8")
    return get_connection(":memory:"), profile_file


def test_reseeding_unchanged_data_appends_no_audit_events(tmp_path: Path) -> None:
    """`db sync` reseeds everything; unchanged rows must not bury real edits in no-op events."""
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps_dir = tmp_path / "applications"

    def events() -> int:
        return conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]

    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    after_first = events()
    assert after_first > 0, "the initial seed must record the profile it inserted"

    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    assert events() == after_first
    conn.close()


def test_reseeding_records_a_real_edit_as_an_update(tmp_path: Path) -> None:
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps_dir = tmp_path / "applications"
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    baseline = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]

    data = json.loads(profile_file.read_text(encoding="utf-8"))
    exp_slug = next(iter(data["experiences"]))
    bullet_slug = next(iter(data["experiences"][exp_slug]["bullets"]))
    data["experiences"][exp_slug]["bullets"][bullet_slug] = "Rewritten bullet text."
    profile_file.write_text(json.dumps(data), encoding="utf-8")

    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)

    rows = conn.execute(
        "SELECT entity_type, entity_id, action FROM audit_events ORDER BY id DESC LIMIT ?",
        (conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] - baseline,),
    ).fetchall()
    assert rows == [("experience_bullet", f"{exp_slug}.{bullet_slug}", "UPDATE")]
    conn.close()


def test_reseeding_records_removed_slugs_as_deletions(tmp_path: Path) -> None:
    """A bullet taken out of profile.json must leave a trace, not vanish from history."""
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps_dir = tmp_path / "applications"
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    baseline = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]

    data = json.loads(profile_file.read_text(encoding="utf-8"))
    proj_slug = next(iter(data["projects"]))
    dropped_bullet = next(iter(data["projects"][proj_slug]["bullets"]))
    del data["projects"][proj_slug]["bullets"][dropped_bullet]
    dropped_project = list(data["projects"])[-1]
    del data["projects"][dropped_project]
    profile_file.write_text(json.dumps(data), encoding="utf-8")

    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)

    deletions = conn.execute(
        "SELECT entity_type, entity_id FROM audit_events WHERE action = 'DELETE' AND id > ?",
        (baseline,),
    ).fetchall()
    assert ("project_bullet", f"{proj_slug}.{dropped_bullet}") in deletions
    assert ("project", dropped_project) in deletions
    conn.close()


def test_reseeding_after_a_deletion_is_stable(tmp_path: Path) -> None:
    """Deletions must be reported once, not re-reported on every later sync."""
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps_dir = tmp_path / "applications"
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)

    data = json.loads(profile_file.read_text(encoding="utf-8"))
    del data["projects"][list(data["projects"])[-1]]
    profile_file.write_text(json.dumps(data), encoding="utf-8")
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)

    settled = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    seed_database(conn, profile_path=profile_file, applications_dir=apps_dir)
    assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == settled
    conn.close()


def test_migration_adds_evaluation_column_to_an_existing_database(tmp_path: Path) -> None:
    """CREATE TABLE IF NOT EXISTS leaves old tables alone, so new columns need a migration."""
    from worksisyphus.db import get_connection, init_schema

    db = tmp_path / "legacy.db"
    conn = get_connection(db)
    conn.executescript("""
        CREATE TABLE applications (
            id TEXT PRIMARY KEY, company TEXT NOT NULL, role TEXT DEFAULT '', date TEXT NOT NULL,
            source_url TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'applied',
            jd_text TEXT NOT NULL DEFAULT '', plan_json TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.execute("INSERT INTO applications (id, company, date) VALUES ('2026-01-01_old_swe', 'OldCo', '2026-01-01')")
    conn.commit()

    init_schema(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(applications)")}
    assert "evaluation_json" in columns
    # The pre-existing row survives, defaulted rather than dropped.
    assert conn.execute("SELECT company, evaluation_json FROM applications").fetchone() == ("OldCo", "")

    init_schema(conn)  # idempotent
    assert conn.execute("SELECT count(*) FROM applications").fetchone()[0] == 1
    conn.close()


def test_evaluation_round_trips_through_seed(tmp_path: Path) -> None:
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps = tmp_path / "applications"
    folder = apps / "2026-08-01_acme_swe"
    folder.mkdir(parents=True)
    (folder / "jd.txt").write_text("JD", encoding="utf-8")
    (folder / "plan.json").write_text("{}", encoding="utf-8")
    (folder / "Simon_Chen_Resume.pdf").write_bytes(b"%PDF")
    (folder / "meta.json").write_text(
        json.dumps({"company": "Acme", "status": "applied", "evaluation": {"total_score": 91.5}}), encoding="utf-8"
    )

    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    stored = conn.execute("SELECT evaluation_json FROM applications WHERE id = ?", (folder.name,)).fetchone()[0]
    assert json.loads(stored)["total_score"] == 91.5

    # Reseeding unchanged data must not look like a change.
    before = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == before
    conn.close()


def test_seed_database_refuses_to_fall_back_to_the_test_fixture(tmp_path: Path, monkeypatch) -> None:
    from worksisyphus.db import seed_database

    good_profile = tmp_path / "good_profile.json"
    good_profile.write_text(
        json.dumps(
            {
                "contact": {
                    "name": "Real Person",
                    "email": "real.person@fastmail.dev",
                    "phone": "617-266-1810",
                    "website": "",
                    "github": "",
                    "linkedin": "",
                },
                "education": [],
                "experiences": {},
                "projects": {},
                "skills": {},
            }
        ),
        encoding="utf-8",
    )

    db_file = tmp_path / "worksisyphus.db"
    conn = get_connection(db_file)
    seed_database(conn, profile_path=good_profile, applications_dir=tmp_path / "apps")
    assert load_profile_from_db(conn).contact.email == "real.person@fastmail.dev"

    # Recreate the incident: a working directory with no profile.json but with the fixture
    # sitting exactly where the old fallback looked for it.
    workdir = tmp_path / "workdir"
    (workdir / "tests" / "fixtures").mkdir(parents=True)
    fixture = Path(__file__).resolve().parent / "fixtures" / "profile.json"
    (workdir / "tests" / "fixtures" / "profile.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(workdir)
    assert not Path("profile.json").exists()
    assert Path("tests/fixtures/profile.json").is_file()

    try:
        seed_database(conn)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("seed_database seeded from the fixture instead of failing")

    assert "profile.json" in message
    assert "db export-profile" in message

    # The database is untouched: the real contact block is still the one it holds.
    contact = load_profile_from_db(conn).contact
    assert contact.email == "real.person@fastmail.dev"
    assert "example.com" not in contact.email
    conn.close()


def test_seed_database_leaves_a_fresh_database_empty_when_the_profile_is_missing(tmp_path: Path) -> None:
    from worksisyphus.db import seed_database

    db_file = tmp_path / "fresh.db"
    conn = get_connection(db_file)
    try:
        seed_database(conn, profile_path=tmp_path / "absent.json", applications_dir=tmp_path / "apps")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("seed_database accepted a nonexistent profile path")

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "contact" not in tables, "schema was created before the profile was validated"
    conn.close()


def test_seed_database_refuses_a_profile_missing_a_required_contact_field(tmp_path: Path) -> None:
    from worksisyphus.db import seed_database

    profile_file = tmp_path / "profile.json"
    profile_file.write_text(
        json.dumps(
            {
                "contact": {"name": "Real Person", "email": "real.person@fastmail.dev", "phone": ""},
                "education": [],
                "experiences": {},
                "projects": {},
                "skills": {},
            }
        ),
        encoding="utf-8",
    )

    conn = get_connection(":memory:")
    try:
        seed_database(conn, profile_path=profile_file, applications_dir=tmp_path / "apps")
    except ValueError as exc:
        assert "contact.phone" in str(exc)
    else:
        raise AssertionError("seed_database accepted a profile with no phone number")
    conn.close()


def test_seed_database_leaves_a_fresh_database_empty_when_the_profile_is_invalid(tmp_path: Path) -> None:
    from worksisyphus.db import seed_database

    invalid = tmp_path / "profile.json"
    invalid.write_text(
        json.dumps(
            {
                "contact": {"name": "", "email": "", "phone": ""},
                "education": [],
                "experiences": {},
                "projects": {},
                "skills": {},
            }
        ),
        encoding="utf-8",
    )

    db_file = tmp_path / "fresh.db"
    conn = get_connection(db_file)
    try:
        seed_database(conn, profile_path=invalid, applications_dir=tmp_path / "apps")
    except ValueError:
        pass
    else:
        raise AssertionError("seed_database accepted an invalid profile")

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "contact" not in tables, "schema was created before the profile was validated"
    conn.close()


def _seed_invalid_contact(conn: Any) -> None:
    init_schema(conn)
    conn.execute(
        "INSERT INTO contact (id, name, email, phone, website, github, linkedin) "
        "VALUES (1, 'Simon Chen', '', '', '', '', '')"
    )
    conn.commit()


def test_export_profile_json_refuses_an_invalid_database(tmp_path: Path) -> None:
    conn = get_connection(":memory:")
    _seed_invalid_contact(conn)

    destination = tmp_path / "profile.json"
    try:
        export_profile_json(conn, output_path=destination)
    except ValueError as exc:
        assert "contact.email is empty" in str(exc)
    else:
        raise AssertionError("export_profile_json wrote an invalid contact block")

    assert not destination.exists(), "the destination was written before validation"
    conn.close()


def test_export_profile_json_does_not_overwrite_a_real_profile_with_invalid_data(tmp_path: Path) -> None:
    conn = get_connection(":memory:")
    _seed_invalid_contact(conn)

    destination = tmp_path / "profile.json"
    original = json.dumps({"contact": {"name": "Real Person", "email": "real.person@fastmail.dev"}})
    destination.write_text(original, encoding="utf-8")

    try:
        export_profile_json(conn, output_path=destination)
    except ValueError:
        pass
    else:
        raise AssertionError("export_profile_json overwrote a real profile with invalid data")

    assert destination.read_text(encoding="utf-8") == original
    conn.close()


def test_export_profile_force_does_not_bypass_the_validation_check(tmp_path: Path, monkeypatch) -> None:
    from worksisyphus import cli, db

    db_file = tmp_path / "corrupt.db"
    conn = get_connection(db_file)
    _seed_invalid_contact(conn)
    conn.close()
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_file)

    destination = tmp_path / "profile.json"
    original = json.dumps({"contact": {"name": "Real Person", "email": "real.person@fastmail.dev"}})
    destination.write_text(original, encoding="utf-8")

    assert cli.main(["db", "export-profile", "--output", str(destination), "--force"]) == 1
    assert destination.read_text(encoding="utf-8") == original


def _insert_app_row(conn, app_id: str, company: str = "Acme", status: str = "applied") -> None:
    conn.execute(
        """
        INSERT INTO applications (id, company, role, date, source_url, status, jd_text, plan_json, evaluation_json)
        VALUES (?, ?, '', ?, '', ?, '', '{}', '')
        """,
        (app_id, company, app_id.split("_", 1)[0], status),
    )


def test_db_status_update_matches_the_filesystem_resolver() -> None:
    """The old SQL LIKE treated '_' as a wildcard; resolution must mirror the FS grammar exactly."""
    from worksisyphus.db import update_application_status_in_db

    conn = get_connection(":memory:")
    init_schema(conn)
    _insert_app_row(conn, "2026-08-01_acme_swe")
    _insert_app_row(conn, "2026-08-01_acme_xswe")

    # "swe" stem-matches only acme_swe on disk; LIKE would also have matched acme_xswe.
    app_id, _, new_status = update_application_status_in_db(conn, "swe", "phone_screen")
    assert (app_id, new_status) == ("2026-08-01_acme_swe", "phone_screen")

    # LIKE metacharacters in identifiers are literal text and match nothing.
    with pytest.raises(FileNotFoundError):
        update_application_status_in_db(conn, "%", "phone_screen")
    conn.close()


def test_db_status_update_lists_ambiguous_matches_multi_line() -> None:
    from worksisyphus.db import update_application_status_in_db

    conn = get_connection(":memory:")
    init_schema(conn)
    _insert_app_row(conn, "2026-08-02_google_data-engineer", company="Google", status="rejected")
    _insert_app_row(conn, "2026-08-08_google_data-engineer", company="Google", status="applied")

    with pytest.raises(ValueError, match="ambiguous") as excinfo:
        update_application_status_in_db(conn, "google_data-engineer", "phone_screen")
    message = excinfo.value.args[0]
    assert "  2026-08-02_google_data-engineer" in message
    assert "  2026-08-08_google_data-engineer" in message
    conn.close()


def test_db_listing_orders_retry_ordinals_numerically() -> None:
    conn = get_connection(":memory:")
    init_schema(conn)
    _insert_app_row(conn, "2026-08-24_google_swe", company="Google")
    _insert_app_row(conn, "2026-08-24_google_swe_10", company="Google")
    _insert_app_row(conn, "2026-08-24_google_swe_2", company="Google")
    _insert_app_row(conn, "2026-07-01_google_swe", company="Google")

    order = [app["folder"] for app in list_applications_from_db(conn)]
    assert order == [
        "2026-08-24_google_swe",
        "2026-08-24_google_swe_2",
        "2026-08-24_google_swe_10",
        "2026-07-01_google_swe",
    ]
    conn.close()


def test_seed_deletes_ghost_application_rows_with_audit(tmp_path: Path) -> None:
    """A DB row whose folder vanished must not survive reseed (partial-restore recovery)."""
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps = tmp_path / "applications"
    ghost = apps / "2026-08-01_ghost_swe"
    ghost.mkdir(parents=True)
    (ghost / "meta.json").write_text(json.dumps({"company": "Ghost", "status": "applied"}), encoding="utf-8")
    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    assert conn.execute("SELECT count(*) FROM applications").fetchone()[0] == 1

    import shutil

    shutil.rmtree(ghost)
    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    assert conn.execute("SELECT count(*) FROM applications").fetchone()[0] == 0
    deletions = conn.execute("SELECT entity_type, entity_id FROM audit_events WHERE action = 'DELETE'").fetchall()
    assert ("application", "2026-08-01_ghost_swe") in deletions

    # Reseeding unchanged data reports nothing further.
    before = conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    assert conn.execute("SELECT count(*) FROM audit_events").fetchone()[0] == before
    conn.close()


def test_seed_skips_dot_directories_even_with_meta(tmp_path: Path) -> None:
    """Staging residue that died after meta-write must never become an application row."""
    from worksisyphus.db import seed_database

    conn, profile_file = _seed_fixture(tmp_path)
    apps = tmp_path / "applications"
    residue = apps / ".staging-abc123"
    residue.mkdir(parents=True)
    (residue / "meta.json").write_text(json.dumps({"company": "HalfBuilt", "status": "applied"}), encoding="utf-8")

    seed_database(conn, profile_path=profile_file, applications_dir=apps)
    assert conn.execute("SELECT count(*) FROM applications").fetchone()[0] == 0
    conn.close()
