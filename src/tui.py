#!/usr/bin/env python3
"""Textual TUI for the worksisyphus resume/cover-letter workflow.

Workflows, one per tab:
  1. Generate  — paste a job description, pick templates, and generate through
                 src/generate.py's deterministic planner/renderer/compiler path.
  2. Import    — paste raw LaTeX as non-trusted input for later review.
  3. Compile   — rebuild the canonical resume from templates/experiences.json
                 through src/compile.py's deterministic compiler path.
  4. Database  — read-only browser for templates/experiences.json.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from worksisyphus import atomic_write_text

TEX_DIR = Path("tex_files")
PDF_DIR = Path("resumes")
RAW_IMPORT_DIR = Path("raw_inputs/tex_imports")
RESUME_TEMPLATE_DIR = Path("templates/resumes")
CL_TEMPLATE_DIR = Path("templates/cover_letters")
EXPERIENCES_JSON = Path("templates/experiences.json")
JSON_RESUME_TEX = TEX_DIR / "Simon_Chen_Resume_Compiled.tex"
JSON_RESUME_PDF = PDF_DIR / "Simon_Chen_Resume_Compiled.pdf"
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def format_raw_import_filename(name: str, template_type: str) -> str:
    """Name raw TeX imports so they are clear, local, and non-compileable."""
    name = Path(name.strip()).name
    if name.endswith(".tex"):
        name = name[:-4]
    name = _SAFE_FILENAME_RE.sub("_", name.strip().replace(" ", "_")).strip("._-")
    if not name:
        name = "raw_input"

    if template_type == "resume":
        if not name.endswith("_resume"):
            name = f"{name}_resume"
    else:  # cover-letter
        if not name.endswith("_cover_letter"):
            name = f"{name}_cover_letter"

    return f"{name}.raw.txt"


def template_options(directory: Path) -> list[tuple[str, str]]:
    """List .tex templates in a directory as (pretty label, filename) options."""
    options = []
    if directory.is_dir():
        for f in sorted(directory.glob("*.tex")):
            options.append((f.stem.replace("_", " ").title(), f.name))
    return options


class ResumeTUI(App):
    TITLE = "worksisyphus"
    SUB_TITLE = "resumes & cover letters"

    CSS = """
    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 1 2;
    }

    .hint {
        color: $text-muted;
        margin-bottom: 1;
    }

    .form-row {
        height: auto;
        margin-bottom: 1;
    }

    .form-col {
        width: 1fr;
        height: auto;
        margin-right: 2;
    }

    .form-col:last-of-type {
        margin-right: 0;
    }

    .form-col Label {
        color: $text-muted;
    }

    #jd-input, #add-latex {
        height: 1fr;
        border: round $primary;
        margin-bottom: 1;
    }

    #compile-list {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }

    #compile-list Checkbox {
        border: none;
        background: transparent;
        padding: 0;
        margin: 0;
    }

    #compile-list Checkbox:focus {
        background: $boost;
        text-style: bold;
    }

    #chk-select-all {
        margin-bottom: 1;
        color: $text-muted;
    }

    .empty-hint {
        color: $text-muted;
        padding: 1;
    }

    #btn-generate, #btn-add, #btn-compile {
        width: 100%;
    }

    .form-row Button {
        width: 1fr;
        margin-right: 2;
    }

    .form-row Button:last-of-type {
        margin-right: 0;
    }

    #log-view {
        height: 10;
        border: round $secondary;
        padding: 0 1;
    }

    #db-tabs TextArea {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_log", "Clear Log", show=True),
    ]

    # ------------------------------------------------------------- layout

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="tab-generate"):
            with TabPane("Generate from JD", id="tab-generate"):
                yield Static(
                    "Paste a job description, pick the templates, and generate "
                    "deterministic artifacts from the canonical profile.",
                    classes="hint",
                )
                yield TextArea(id="jd-input", show_line_numbers=False)
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label("Generate")
                        yield Select(
                            [
                                ("Resume + Cover Letter", "both"),
                                ("Resume only", "resume"),
                                ("Cover letter only", "cover-letter"),
                            ],
                            id="gen-mode",
                            value="both",
                            allow_blank=False,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Resume template")
                        yield Select(
                            template_options(RESUME_TEMPLATE_DIR) or [("None found", "")],
                            id="resume-select",
                            allow_blank=False,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Cover letter template")
                        yield Select(
                            template_options(CL_TEMPLATE_DIR) or [("None found", "")],
                            id="cl-select",
                            allow_blank=False,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Output name")
                        yield Input(id="output-name", value="tailored", placeholder="e.g. google_swe")
                yield Button("Generate", variant="primary", id="btn-generate")

            with TabPane("Import Raw TeX", id="tab-add"):
                yield Static(
                    "Paste raw LaTeX source below as non-trusted input. It is not "
                    "saved as a compileable artifact and will not appear in Compile.",
                    classes="hint",
                )
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label("File name")
                        yield Input(id="add-name", placeholder="e.g. google_swe")
                    with Vertical(classes="form-col"):
                        yield Label("Type")
                        yield Select(
                            [("Resume", "resume"), ("Cover letter", "cover-letter")],
                            id="add-type",
                            value="resume",
                            allow_blank=False,
                        )
                yield TextArea(id="add-latex", show_line_numbers=False)
                yield Button("Import raw input", variant="success", id="btn-add")

            with TabPane("Compile", id="tab-compile"):
                yield Static(
                    "Rebuild the canonical resume from experiences.json through "
                    "the deterministic renderer and safe compiler backend.",
                    classes="hint",
                )
                yield VerticalScroll(id="compile-list")
                with Horizontal(classes="form-row"):
                    yield Button(
                        "Rebuild deterministic TeX", id="btn-rebuild-json"
                    )
                    yield Button("Refresh status", id="btn-refresh")
                yield Button("Compile deterministic resume", variant="warning", id="btn-compile")

            with TabPane("Database", id="tab-database"):
                data = {}
                if EXPERIENCES_JSON.is_file():
                    try:
                        data = json.loads(EXPERIENCES_JSON.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                with TabbedContent(id="db-tabs"):
                    for key, title in [
                        ("education", "Education"),
                        ("experiences", "Experiences"),
                        ("projects", "Projects"),
                        ("skills", "Skills"),
                    ]:
                        with TabPane(title):
                            yield TextArea(
                                json.dumps(data.get(key, [] if key != "skills" else {}), indent=2),
                                read_only=True,
                                show_line_numbers=False,
                            )

        yield RichLog(id="log-view", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#jd-input").border_title = "Job Description"
        self.query_one("#add-latex").border_title = "Raw LaTeX Input"
        self.query_one("#compile-list").border_title = "Trusted deterministic outputs"
        self.query_one("#log-view").border_title = "Activity Log"
        self.refresh_compile_list()
        self.log_message("[dim]Ready. Generate from a JD, import raw input, or rebuild deterministically.[/dim]")

    # ------------------------------------------------------------ logging

    def log_message(self, message: str) -> None:
        self.query_one("#log-view", RichLog).write(message)

    def wlog(self, message: str) -> None:
        """Log from a worker thread."""
        self.call_from_thread(self.log_message, message)

    def action_clear_log(self) -> None:
        self.query_one("#log-view", RichLog).clear()

    # ------------------------------------------------------- compile list

    def refresh_compile_list(self) -> None:
        self.run_worker(self._rebuild_compile_list(), exclusive=True, group="compile-list")

    async def _rebuild_compile_list(self) -> None:
        container = self.query_one("#compile-list", VerticalScroll)
        await container.remove_children()

        rows = [
            ("Canonical TeX", JSON_RESUME_TEX),
            ("Canonical PDF", JSON_RESUME_PDF),
        ]
        widgets = [
            Static(
                f"{label}: {path} ({'present' if path.is_file() else 'not built yet'})",
                classes="empty-hint",
            )
            for label, path in rows
        ]
        await container.mount(*widgets)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "gen-mode":
            mode = event.select.value
            self.query_one("#resume-select", Select).disabled = mode == "cover-letter"
            self.query_one("#cl-select", Select).disabled = mode == "resume"

    # ------------------------------------------------------- job running

    def set_busy(self, busy: bool) -> None:
        for bid in ("#btn-generate", "#btn-add", "#btn-compile", "#btn-rebuild-json"):
            self.query_one(bid, Button).disabled = busy

    def run_job(self, job) -> None:
        """Run a blocking job in a thread, managing busy state and refresh."""

        def wrapper() -> None:
            try:
                job()
            finally:
                self.call_from_thread(self.set_busy, False)
                self.call_from_thread(self.refresh_compile_list)

        self.set_busy(True)
        self.run_worker(wrapper, thread=True)

    def run_subprocess_cmd(self, cmd: list[str]) -> bool:
        """Run a process from a worker thread, streaming output to the log."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.wlog("  " + line)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.wlog(f"  [bold red]Exception:[/bold red] {e}")
            return False

    # ------------------------------------------------------------ actions

    def do_generate(self) -> None:
        jd_text = self.query_one("#jd-input", TextArea).text.strip()
        if not jd_text:
            self.log_message("[bold red]Error:[/bold red] job description is empty.")
            return

        mode = str(self.query_one("#gen-mode", Select).value)
        resume_template = self.query_one("#resume-select", Select).value
        cl_template = self.query_one("#cl-select", Select).value
        output_name = self.query_one("#output-name", Input).value.strip() or "tailored"

        cmd = [sys.executable, "src/generate.py", "--mode", mode, "--output-name", output_name]
        if mode in ("resume", "both"):
            if not resume_template or resume_template is Select.BLANK:
                self.log_message("[bold red]Error:[/bold red] no resume template available.")
                return
            cmd += ["--resume-template", str(RESUME_TEMPLATE_DIR / str(resume_template))]
        if mode in ("cover-letter", "both"):
            if not cl_template or cl_template is Select.BLANK:
                self.log_message("[bold red]Error:[/bold red] no cover letter template available.")
                return
            cmd += ["--cover-letter-template", str(CL_TEMPLATE_DIR / str(cl_template))]

        fd, jd_path = tempfile.mkstemp(suffix=".txt", prefix="jd_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(jd_text)
        cmd += ["--jd", jd_path]

        def job() -> None:
            self.wlog(f"[bold blue]Generating ({mode}) as '{output_name}'...[/bold blue]")
            try:
                ok = self.run_subprocess_cmd(cmd)
            finally:
                try:
                    os.unlink(jd_path)
                except OSError:
                    pass
            if ok:
                self.wlog("[bold green]Generation finished through deterministic compiler path.[/bold green]")
            else:
                self.wlog("[bold red]Generation failed — see output above.[/bold red]")

        self.run_job(job)

    def do_add_tex(self) -> None:
        name_input = self.query_one("#add-name", Input)
        latex_input = self.query_one("#add-latex", TextArea)
        template_type = str(self.query_one("#add-type", Select).value)

        raw_name = name_input.value.strip()
        latex_code = latex_input.text.strip()
        if not raw_name:
            self.log_message("[bold red]Error:[/bold red] file name is required.")
            return
        if not latex_code:
            self.log_message("[bold red]Error:[/bold red] LaTeX source is empty.")
            return

        dest = RAW_IMPORT_DIR / format_raw_import_filename(raw_name, template_type)
        try:
            atomic_write_text(dest, latex_code + "\n")
        except Exception as e:
            self.log_message(f"[bold red]Import failed:[/bold red] {e}")
            return

        name_input.value = ""
        latex_input.text = ""
        self.refresh_compile_list()
        self.log_message(
            f"[bold green]Imported raw input[/bold green] {dest} — it is not compileable output."
        )

    def do_compile(self) -> None:
        def job() -> None:
            self.wlog("[bold blue]Compiling deterministic JSON resume...[/bold blue]")
            ok = self.run_subprocess_cmd(
                [
                    sys.executable,
                    "src/compile.py",
                    "--resume",
                    str(EXPERIENCES_JSON),
                    "--output",
                    str(JSON_RESUME_TEX),
                    "--pdf-output",
                    str(JSON_RESUME_PDF),
                ]
            )
            if ok:
                self.wlog(f"[bold green]Compiled deterministic PDF: {JSON_RESUME_PDF}[/bold green]")
            else:
                self.wlog("[bold red]Deterministic compile failed — see output above.[/bold red]")

        self.run_job(job)

    def do_rebuild_json_resume(self) -> None:
        def job() -> None:
            self.wlog("[bold blue]Rebuilding from experiences.json...[/bold blue]")
            ok = self.run_subprocess_cmd(
                [
                    sys.executable,
                    "src/compile.py",
                    "--resume",
                    str(EXPERIENCES_JSON),
                    "--output",
                    str(JSON_RESUME_TEX),
                    "--tex-only",
                ]
            )
            if ok:
                self.wlog(f"[bold green]Rebuilt {JSON_RESUME_TEX}.[/bold green]")
            else:
                self.wlog("[bold red]Rebuild failed — see output above.[/bold red]")

        self.run_job(job)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-generate": self.do_generate,
            "btn-add": self.do_add_tex,
            "btn-compile": self.do_compile,
            "btn-rebuild-json": self.do_rebuild_json_resume,
            "btn-refresh": self.refresh_compile_list,
        }
        handler = handlers.get(event.button.id or "")
        if handler:
            handler()


if __name__ == "__main__":
    ResumeTUI().run()
