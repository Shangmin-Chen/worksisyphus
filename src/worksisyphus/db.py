"""SQLite and Turso LibSQL database layer for worksisyphus.

Provides:
- SQLite connection management with Turso sync support.
- Schema creation & initialization.
- Append-only audit/changelog tracking with ISO timestamps.
- Profile loading, seeding, and export.
- Application archiving, listing, and status updates.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .profile import Contact, Education, Experience, Profile, Project

DEFAULT_DB_PATH = Path("worksisyphus.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    github TEXT DEFAULT '',
    linkedin TEXT DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution TEXT NOT NULL,
    location TEXT NOT NULL,
    degree TEXT NOT NULL,
    date TEXT NOT NULL,
    coursework TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS experiences (
    slug TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    org TEXT NOT NULL,
    location TEXT NOT NULL,
    date TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS experience_bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_slug TEXT NOT NULL REFERENCES experiences(slug) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (experience_slug, slug)
);

CREATE TABLE IF NOT EXISTS projects (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tech TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS project_bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug TEXT NOT NULL REFERENCES projects(slug) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (project_slug, slug)
);

CREATE TABLE IF NOT EXISTS skills (
    group_name TEXT NOT NULL,
    item TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (group_name, item)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    role TEXT DEFAULT '',
    date TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'applied',
    jd_text TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events (entity_type, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications (date DESC);
"""


def get_connection(
    db_path: Path | str | None = None,
) -> sqlite3.Connection:
    """Return a local SQLite database connection with WAL mode and foreign keys."""
    if db_path == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        target_path = Path(db_path or DEFAULT_DB_PATH)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target_path))
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not already exist."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def log_audit_event(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    action: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
    commit: bool = True,
) -> None:
    """Append a timestamped event into the audit_events table."""
    ts = timestamp or datetime.now(UTC).isoformat()
    meta_str = json.dumps(metadata) if metadata else None
    conn.execute(
        """
        INSERT INTO audit_events (timestamp, entity_type, entity_id, action, field_name, old_value, new_value, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, entity_type, entity_id, action, field_name, old_value, new_value, meta_str),
    )
    if commit:
        conn.commit()


def seed_database(
    conn: sqlite3.Connection,
    profile_path: Path = Path("profile.json"),
    applications_dir: Path = Path("applications"),
) -> None:
    """Populate database from profile.json and applications/."""
    init_schema(conn)

    if not profile_path.is_file() and profile_path == Path("profile.json"):
        if Path("profile.example.json").is_file():
            profile_path = Path("profile.example.json")
        elif (Path("tests") / "fixtures" / "profile.json").is_file():
            profile_path = Path("tests") / "fixtures" / "profile.json"

    # 1. Contact
    if profile_path.is_file():
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        contact = data.get("contact", {})
        conn.execute(
            """
            INSERT OR REPLACE INTO contact (id, name, email, phone, website, github, linkedin)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact.get("name", ""),
                contact.get("email", ""),
                contact.get("phone", ""),
                contact.get("website", ""),
                contact.get("github", ""),
                contact.get("linkedin", ""),
            ),
        )
        log_audit_event(conn, "contact", "1", "INSERT", metadata={"name": contact.get("name", "")}, commit=False)

        # 2. Education
        conn.execute("DELETE FROM education")
        for i, edu in enumerate(data.get("education", [])):
            conn.execute(
                """
                INSERT INTO education (institution, location, degree, date, coursework, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edu.get("institution", ""),
                    edu.get("location", ""),
                    edu.get("degree", ""),
                    edu.get("date", ""),
                    json.dumps(edu.get("coursework", [])),
                    i,
                ),
            )
            log_audit_event(conn, "education", edu.get("institution", ""), "INSERT", metadata=edu, commit=False)

        # 3. Experiences & bullets
        conn.execute("DELETE FROM experience_bullets")
        conn.execute("DELETE FROM experiences")
        for i, (slug, exp) in enumerate(data.get("experiences", {}).items()):
            conn.execute(
                """
                INSERT INTO experiences (slug, role, org, location, date, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (slug, exp.get("role", ""), exp.get("org", ""), exp.get("location", ""), exp.get("date", ""), i),
            )
            log_audit_event(conn, "experience", slug, "INSERT", metadata=exp, commit=False)
            for j, (b_slug, b_text) in enumerate(exp.get("bullets", {}).items()):
                conn.execute(
                    """
                    INSERT INTO experience_bullets (experience_slug, slug, text, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (slug, b_slug, b_text, j),
                )
                log_audit_event(conn, "experience_bullet", f"{slug}.{b_slug}", "INSERT", new_value=b_text, commit=False)

        # 4. Projects & bullets
        conn.execute("DELETE FROM project_bullets")
        conn.execute("DELETE FROM projects")
        for i, (slug, proj) in enumerate(data.get("projects", {}).items()):
            conn.execute(
                """
                INSERT INTO projects (slug, name, tech, date, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                (slug, proj.get("name", ""), proj.get("tech", ""), proj.get("date", ""), i),
            )
            log_audit_event(conn, "project", slug, "INSERT", metadata=proj, commit=False)
            for j, (b_slug, b_text) in enumerate(proj.get("bullets", {}).items()):
                conn.execute(
                    """
                    INSERT INTO project_bullets (project_slug, slug, text, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (slug, b_slug, b_text, j),
                )
                log_audit_event(conn, "project_bullet", f"{slug}.{b_slug}", "INSERT", new_value=b_text, commit=False)

        # 5. Skills
        conn.execute("DELETE FROM skills")
        for group, items in data.get("skills", {}).items():
            for i, item in enumerate(items):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO skills (group_name, item, sort_order)
                    VALUES (?, ?, ?)
                    """,
                    (group, item, i),
                )
        log_audit_event(
            conn, "skills", "skills", "INSERT", metadata={"groups": list(data.get("skills", {}).keys())}, commit=False
        )

    # 6. Applications
    if applications_dir.is_dir():
        conn.execute("DELETE FROM applications")
        for d in sorted(applications_dir.iterdir()):
            if not d.is_dir():
                continue
            meta_file = d / "meta.json"
            jd_file = d / "jd.txt"
            plan_file = d / "plan.json"
            if not meta_file.is_file():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            jd_text = jd_file.read_text(encoding="utf-8") if jd_file.is_file() else ""
            plan_json = plan_file.read_text(encoding="utf-8") if plan_file.is_file() else "{}"
            conn.execute(
                """
                INSERT OR REPLACE INTO applications (id, company, role, date, source_url, status, jd_text, plan_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    d.name,
                    meta.get("company", ""),
                    meta.get("role", ""),
                    meta.get("date", ""),
                    meta.get("source_url", ""),
                    meta.get("status", "applied"),
                    jd_text,
                    plan_json,
                ),
            )
            log_audit_event(conn, "application", d.name, "ARCHIVE", metadata=meta, commit=False)

    conn.commit()


def load_profile_from_db(conn: sqlite3.Connection) -> Profile:
    """Query database and construct a Profile instance."""
    # Contact
    cur = conn.execute("SELECT name, email, phone, website, github, linkedin FROM contact WHERE id = 1")
    row = cur.fetchone()
    contact = Contact(*(row or ("", "", "", "", "", "")))

    # Education
    education_list: list[Education] = []
    cur = conn.execute("SELECT institution, location, degree, date, coursework FROM education ORDER BY sort_order, id")
    for inst, loc, deg, dt, cw_json in cur.fetchall():
        cw = tuple(json.loads(cw_json)) if cw_json else ()
        education_list.append(Education(institution=inst, location=loc, degree=deg, date=dt, coursework=cw))

    # Experiences
    experiences_dict: dict[str, Experience] = {}
    cur = conn.execute("SELECT slug, role, org, location, date FROM experiences ORDER BY sort_order, slug")
    for slug, role, org, loc, dt in cur.fetchall():
        b_cur = conn.execute(
            "SELECT slug, text FROM experience_bullets WHERE experience_slug = ? ORDER BY sort_order, id",
            (slug,),
        )
        bullets = {b_slug: text for b_slug, text in b_cur.fetchall()}
        experiences_dict[slug] = Experience(id=slug, role=role, org=org, location=loc, date=dt, bullets=bullets)

    # Projects
    projects_dict: dict[str, Project] = {}
    cur = conn.execute("SELECT slug, name, tech, date FROM projects ORDER BY sort_order, slug")
    for slug, name, tech, dt in cur.fetchall():
        b_cur = conn.execute(
            "SELECT slug, text FROM project_bullets WHERE project_slug = ? ORDER BY sort_order, id",
            (slug,),
        )
        bullets = {b_slug: text for b_slug, text in b_cur.fetchall()}
        projects_dict[slug] = Project(id=slug, name=name, tech=tech, date=dt, bullets=bullets)

    # Skills
    skills_dict: dict[str, tuple[str, ...]] = {}
    cur = conn.execute("SELECT group_name, item FROM skills ORDER BY group_name, sort_order, item")
    for group, item in cur.fetchall():
        skills_dict.setdefault(group, ())
        skills_dict[group] = skills_dict[group] + (item,)

    return Profile(
        contact=contact,
        education=tuple(education_list),
        experiences=experiences_dict,
        projects=projects_dict,
        skills=skills_dict,
    )


def export_profile_json(conn: sqlite3.Connection, output_path: Path = Path("profile.json")) -> dict[str, Any]:
    """Materialize database profile state into profile.json format."""
    profile = load_profile_from_db(conn)
    data = {
        "contact": {
            "name": profile.contact.name,
            "email": profile.contact.email,
            "phone": profile.contact.phone,
            "website": profile.contact.website,
            "github": profile.contact.github,
            "linkedin": profile.contact.linkedin,
        },
        "education": [
            {
                "institution": edu.institution,
                "location": edu.location,
                "degree": edu.degree,
                "date": edu.date,
                "coursework": list(edu.coursework),
            }
            for edu in profile.education
        ],
        "experiences": {
            slug: {
                "role": exp.role,
                "org": exp.org,
                "location": exp.location,
                "date": exp.date,
                "bullets": dict(exp.bullets),
            }
            for slug, exp in profile.experiences.items()
        },
        "projects": {
            slug: {
                "name": proj.name,
                "tech": proj.tech,
                "date": proj.date,
                "bullets": dict(proj.bullets),
            }
            for slug, proj in profile.projects.items()
        },
        "skills": {group: list(items) for group, items in profile.skills.items()},
    }
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def save_application_to_db(
    conn: sqlite3.Connection,
    app_id: str,
    company: str,
    role: str,
    date_str: str,
    source_url: str,
    status: str,
    jd_text: str,
    plan_json: str,
) -> None:
    """Store application in the applications table with audit logging."""
    conn.execute(
        """
        INSERT OR REPLACE INTO applications (id, company, role, date, source_url, status, jd_text, plan_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (app_id, company, role, date_str, source_url, status, jd_text, plan_json),
    )
    log_audit_event(
        conn,
        "application",
        app_id,
        "APPLY",
        metadata={"company": company, "role": role, "date": date_str, "status": status},
        commit=True,
    )


archive_application_to_db = save_application_to_db


def list_applications_from_db(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """Return all applications from DB ordered by date descending."""
    cur = conn.execute(
        "SELECT id, company, role, date, source_url, status FROM applications ORDER BY date DESC, id DESC"
    )
    results: list[dict[str, str]] = []
    for app_id, company, role, dt, url, status in cur.fetchall():
        results.append(
            {
                "folder": app_id,
                "company": company,
                "role": role,
                "date": dt,
                "source_url": url,
                "status": status,
            }
        )
    return results


def update_application_status_in_db(
    conn: sqlite3.Connection, app_identifier: str, new_status: str
) -> tuple[str, str, str]:
    """Update status in DB and record an append-only audit event."""
    cur = conn.execute(
        "SELECT id, status FROM applications WHERE id = ? OR id LIKE ?", (app_identifier, f"%_{app_identifier}")
    )
    rows = cur.fetchall()
    if not rows:
        raise FileNotFoundError(f"No application found matching {app_identifier!r}.")
    if len(rows) > 1:
        names = ", ".join(r[0] for r in rows)
        raise ValueError(f"Application identifier {app_identifier!r} is ambiguous; matches: {names}")
    app_id, old_status = rows[0]
    conn.execute(
        "UPDATE applications SET status = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')) WHERE id = ?",
        (new_status, app_id),
    )
    log_audit_event(
        conn,
        "application",
        app_id,
        "STATUS_CHANGE",
        field_name="status",
        old_value=old_status,
        new_value=new_status,
        commit=True,
    )
    return app_id, old_status, new_status


def get_audit_history(
    conn: sqlite3.Connection, limit: int = 50, entity_type: str | None = None
) -> list[dict[str, Any]]:
    """Query append-only audit log."""
    if entity_type:
        cur = conn.execute(
            """
            SELECT id, timestamp, entity_type, entity_id, action, field_name, old_value, new_value, metadata
            FROM audit_events WHERE entity_type = ? ORDER BY id DESC LIMIT ?
            """,
            (entity_type, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT id, timestamp, entity_type, entity_id, action, field_name, old_value, new_value, metadata
            FROM audit_events ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
    events: list[dict[str, Any]] = []
    for row in cur.fetchall():
        events.append(
            {
                "id": row[0],
                "timestamp": row[1],
                "entity_type": row[2],
                "entity_id": row[3],
                "action": row[4],
                "field_name": row[5],
                "old_value": row[6],
                "new_value": row[7],
                "metadata": json.loads(row[8]) if row[8] else None,
            }
        )
    return events


def sync_to_turso(db_path: Path = DEFAULT_DB_PATH, turso_db_name: str = "worksisyphus") -> bool:
    """Push local SQLite database state to Turso cloud via Turso CLI."""
    home_turso = Path.home() / ".turso" / "turso"
    turso_bin = shutil.which("turso") or (str(home_turso) if home_turso.is_file() else None)
    if not turso_bin or not db_path.is_file():
        return False
    try:
        drop_all = """
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS project_bullets;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS experience_bullets;
DROP TABLE IF EXISTS experiences;
DROP TABLE IF EXISTS education;
DROP TABLE IF EXISTS contact;
"""
        subprocess.run(
            [turso_bin, "db", "shell", turso_db_name],
            input=drop_all,
            capture_output=True,
            text=True,
            timeout=30,
        )
        dump_proc = subprocess.run(
            ["sqlite3", str(db_path), ".dump"],
            capture_output=True,
            text=True,
            check=True,
        )
        proc = subprocess.run(
            [turso_bin, "db", "shell", turso_db_name],
            input=dump_proc.stdout,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False
