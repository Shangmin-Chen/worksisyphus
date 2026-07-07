#!/usr/bin/env python3
"""Textual TUI for the worksisyphus resume/cover-letter workflow.

Workflows, one per tab:
  1. Generate  — paste a job description, pick templates, generate tailored
                 .tex files into tex_files/ via src/generate.py (Gemini AI).
  2. Add TeX   — paste raw LaTeX source and save it straight into tex_files/.
  3. Compile   — check any of the .tex files in tex_files/ and compile them
                 to PDFs in resumes/.
  4. Database  — read-only browser for templates/experiences.json.

tex_files/ is the single directory holding every generated or added .tex
file; resumes/ holds only compiled PDFs; templates/ holds only the two base
templates (jakes_resume_template, default_cover_letter).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
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

TEX_DIR = Path("tex_files")
PDF_DIR = Path("resumes")
RESUME_TEMPLATE_DIR = Path("templates/resumes")
CL_TEMPLATE_DIR = Path("templates/cover_letters")
EXPERIENCES_JSON = Path("templates/experiences.json")
JSON_RESUME_TEX = TEX_DIR / "Simon_Chen_Resume_Compiled.tex"


def format_template_filename(name: str, template_type: str) -> str:
    """Enforce postpending naming rules: _resume.tex or _cover_letter.tex."""
    name = name.strip()
    if name.endswith(".tex"):
        name = name[:-4]
    name = name.strip().replace(" ", "_")

    if template_type == "resume":
        if not name.endswith("_resume"):
            name = f"{name}_resume"
    else:  # cover-letter
        if not name.endswith("_cover_letter"):
            name = f"{name}_cover_letter"

    return f"{name}.tex"


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
                    "tailored .tex files into tex_files/. Compile them from the "
                    "Compile tab afterwards.",
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

            with TabPane("Add TeX File", id="tab-add"):
                yield Static(
                    "Paste raw LaTeX source below and save it into tex_files/. "
                    "The file is named with the usual _resume / _cover_letter suffix.",
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
                yield Button("Save to tex_files/", variant="success", id="btn-add")

            with TabPane("Compile", id="tab-compile"):
                yield Static(
                    "Every generated or added .tex file lives in tex_files/. "
                    "Check the ones you want and compile — PDFs land in resumes/.",
                    classes="hint",
                )
                yield VerticalScroll(id="compile-list")
                with Horizontal(classes="form-row"):
                    yield Button(
                        "Rebuild JSON resume (experiences.json)", id="btn-rebuild-json"
                    )
                    yield Button("Refresh list", id="btn-refresh")
                yield Button("Compile selected", variant="warning", id="btn-compile")

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
        self.query_one("#add-latex").border_title = "LaTeX Source"
        self.query_one("#compile-list").border_title = "tex_files/"
        self.query_one("#log-view").border_title = "Activity Log"
        self.refresh_compile_list()
        self.log_message("[dim]Ready. Generate from a JD or add a .tex file, then compile.[/dim]")

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
        checked = {
            cb.name: cb.value for cb in container.query(Checkbox) if cb.name
        }
        await container.remove_children()

        TEX_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(TEX_DIR.glob("*.tex"))
        if not files:
            await container.mount(
                Static(
                    "No .tex files yet — generate one from a JD or add one first.",
                    classes="empty-hint",
                )
            )
            return

        values = [checked.get(f.name, True) for f in files]
        widgets = [Checkbox("Select all", id="chk-select-all")]
        widgets += [
            Checkbox(f.name, name=f.name, classes="file-check") for f in files
        ]
        # Set initial values silently: Checkbox posts Changed even from its
        # constructor, and a Changed from "Select all" would clobber the
        # restored per-file states.
        for widget, value in zip(widgets, [all(values)] + values):
            with widget.prevent(Checkbox.Changed):
                widget.value = value
        await container.mount(*widgets)

    def selected_tex_files(self) -> list[Path]:
        return [
            TEX_DIR / cb.name
            for cb in self.query(".file-check")
            if cb.value and cb.name
        ]

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-select-all":
            for cb in self.query(".file-check"):
                cb.value = event.checkbox.value
        elif event.checkbox.has_class("file-check"):
            select_all = self.query_one("#chk-select-all", Checkbox)
            with select_all.prevent(Checkbox.Changed):
                select_all.value = all(cb.value for cb in self.query(".file-check"))

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

    def compile_single_tex(self, path: Path) -> bool:
        """Compile one .tex file (worker thread); move the PDF to resumes/."""
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = str(TEX_DIR)

        def collect_pdf() -> bool:
            src_pdf = TEX_DIR / f"{path.stem}.pdf"
            if not src_pdf.is_file():
                self.wlog(f"  [bold red]No PDF produced for {path.name}[/bold red]")
                return False
            try:
                shutil.move(src_pdf, PDF_DIR / src_pdf.name)
                return True
            except Exception as e:
                self.wlog(f"  [bold red]Failed to move PDF:[/bold red] {e}")
                return False

        if self.run_subprocess_cmd(
            ["latexmk", "-pdf", "-interaction=nonstopmode", f"-output-directory={out_dir}", str(path)]
        ):
            ok = collect_pdf()
            self.run_subprocess_cmd(["latexmk", "-c", f"-output-directory={out_dir}", str(path)])
            return ok

        self.wlog("  latexmk failed, trying pdflatex fallback...")
        if self.run_subprocess_cmd(
            ["pdflatex", "-interaction=nonstopmode", f"-output-directory={out_dir}", str(path)]
        ):
            return collect_pdf()
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
                self.wlog("[bold green]Generation finished — files are in tex_files/.[/bold green]")
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

        TEX_DIR.mkdir(parents=True, exist_ok=True)
        dest = TEX_DIR / format_template_filename(raw_name, template_type)
        try:
            dest.write_text(latex_code + "\n", encoding="utf-8")
        except Exception as e:
            self.log_message(f"[bold red]Save failed:[/bold red] {e}")
            return

        name_input.value = ""
        latex_input.text = ""
        self.refresh_compile_list()
        self.log_message(
            f"[bold green]Saved[/bold green] {dest} — it is now available in the Compile tab."
        )

    def do_compile(self) -> None:
        targets = self.selected_tex_files()
        if not targets:
            self.log_message("[bold red]Error:[/bold red] no files selected to compile.")
            return

        def job() -> None:
            self.wlog(f"[bold blue]Compiling {len(targets)} file(s)...[/bold blue]")
            failures = 0
            for path in targets:
                self.wlog(f"[bold yellow]→ {path.name}[/bold yellow]")
                if not self.compile_single_tex(path):
                    failures += 1
            if failures:
                self.wlog(f"[bold red]Done with {failures} failure(s).[/bold red]")
            else:
                self.wlog("[bold green]All PDFs compiled into resumes/.[/bold green]")

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
