#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog, Select, TabbedContent, TabPane, TextArea


def format_template_filename(name: str, template_type: str) -> str:
    """Enforce postpending naming rules: _resume.tex or _cover_letter.tex."""
    name = name.strip()
    if name.endswith(".tex"):
        name = name[:-4]
    name = name.strip()
    
    if template_type == "resume":
        if not name.endswith("_resume"):
            name = f"{name}_resume"
    else:  # cover-letter
        if not name.endswith("_cover_letter"):
            name = f"{name}_cover_letter"
            
    return f"{name}.tex"


class DatabaseScreen(Screen):
    """Screen for browsing the experiences database read-only."""
    BINDINGS = [
        Binding("escape,ctrl+d", "back", "Back to Dashboard", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        
        # Load experiences.json
        exp_path = Path("templates/experiences.json")
        data = {}
        if exp_path.is_file():
            try:
                with open(exp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        education_str = json.dumps(data.get("education", []), indent=2)
        experiences_str = json.dumps(data.get("experiences", []), indent=2)
        projects_str = json.dumps(data.get("projects", []), indent=2)
        skills_str = json.dumps(data.get("skills", {}), indent=2)

        with TabbedContent():
            with TabPane("Education", id="edu-pane"):
                yield TextArea(education_str, read_only=True, language="json")
            with TabPane("Experiences", id="exp-pane"):
                yield TextArea(experiences_str, read_only=True, language="json")
            with TabPane("Projects", id="proj-pane"):
                yield TextArea(projects_str, read_only=True, language="json")
            with TabPane("Skills", id="skills-pane"):
                yield TextArea(skills_str, read_only=True, language="json")
                
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()


class DashboardScreen(Screen):
    """Main dashboard screen."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="dashboard-layout"):
            with Vertical(id="left-panel"):
                yield Label("Job Application Inputs & Imports", classes="panel-title")
                
                yield Label("Paste Job Description:")
                yield TextArea(id="jd-input", show_line_numbers=False)

                # Resume templates
                yield Label("Select Resume Template:")
                res_dir = Path("templates/resumes")
                resume_options = []
                if res_dir.is_dir():
                    resume_options = [(f.name, f.name) for f in sorted(res_dir.glob("*.tex"))]
                if not resume_options:
                    resume_options = [("None", "None")]
                yield Select(
                    resume_options,
                    id="resume-select",
                    value=resume_options[0][0] if resume_options else None,
                    allow_blank=False,
                )

                # Cover letter templates
                yield Label("Select Cover Letter Template:")
                cl_dir = Path("templates/cover_letters")
                cl_options = []
                if cl_dir.is_dir():
                    cl_options = [(f.name, f.name) for f in sorted(cl_dir.glob("*.tex"))]
                if not cl_options:
                    cl_options = [("None", "None")]
                yield Select(
                    cl_options,
                    id="cl-select",
                    value=cl_options[0][0] if cl_options else None,
                    allow_blank=False,
                )

                yield Label("Output Name Prefix:")
                yield Input(id="output-name", value="tailored")

                with Horizontal(classes="action-row"):
                    yield Button("Tailor Both (AI)", variant="primary", id="btn-tailor-both")
                    yield Button("Tailor Resume Only", variant="success", id="btn-tailor-resume")
                    yield Button("Tailor Cover Letter Only", variant="success", id="btn-tailor-cl")

                # Manual Template Importer Section
                yield Label("Import External LaTeX Template", classes="section-divider")
                
                yield Select(
                    [("Import from File Path", "path"), ("Paste LaTeX Code", "paste")],
                    id="import-mode",
                    value="path",
                    allow_blank=False,
                )
                
                # File Path input (default shown)
                yield Input(id="import-path", placeholder="Path to local .tex file")
                
                # Paste LaTeX fields (default hidden)
                yield Input(id="import-name", placeholder="Template Name (e.g. jakes)")
                yield TextArea(id="import-latex-input", show_line_numbers=False)
                
                with Horizontal(classes="import-row"):
                    yield Select(
                        [("Resume", "resume"), ("Cover Letter", "cover-letter")],
                        id="import-type",
                        value="resume",
                        allow_blank=False,
                    )
                    yield Button("Import / Save", variant="success", id="btn-import")

            with Vertical(id="right-panel"):
                yield Label("Select Standard Targets to Compile", classes="panel-title")
                
                # Checkboxes list for compilation selection
                with VerticalScroll(id="template-checkboxes-container"):
                    yield Checkbox("Select All", value=True, id="chk-select-all")
                    # Dynamic checkboxes will be mounted here
                
                yield Button("Compile Selected Standard Templates", variant="warning", id="btn-compile-standard")
                
                yield Label("Activity Logs & Status", classes="panel-title")
                yield RichLog(id="log-view", highlight=True, markup=True)
                
        yield Footer()

    def on_mount(self) -> None:
        self.app.refresh_template_options()
        # Initialize display states for import
        try:
            self.query_one("#import-name").styles.display = "none"
            self.query_one("#import-latex-input").styles.display = "none"
        except Exception:
            pass


class ResumeTUI(App):
    """Textual TUI for Simon Chen Resumes Tool."""
    TITLE = "Simon Chen Resumes Dashboard"
    
    CSS = """
    Screen {
        background: $background;
    }
    
    #dashboard-layout {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr;
        padding: 1;
        grid-gutter: 1;
    }
    
    #left-panel {
        border: tall $primary;
        padding: 1;
        height: 100%;
    }
    
    #right-panel {
        border: tall $secondary;
        padding: 1;
        height: 100%;
    }
    
    .panel-title {
        text-align: center;
        background: $boost;
        padding: 1;
        margin-bottom: 1;
        color: $text;
        text-style: bold;
    }
    
    .section-divider {
        text-align: center;
        text-style: bold;
        background: $boost;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        color: $accent;
    }
    
    #jd-input {
        height: 1fr;
        border: solid $accent;
        margin-bottom: 1;
    }
    
    #import-latex-input {
        height: 6;
        border: solid $accent;
        margin-bottom: 1;
    }
    
    #template-checkboxes-container {
        height: 180;
        border: solid $accent;
        margin-bottom: 1;
        padding: 0 1;
    }
    
    #log-view {
        height: 1fr;
        border: solid $accent;
        background: $background;
    }
    
    Input {
        margin-bottom: 1;
    }
    
    Select {
        margin-bottom: 1;
    }
    
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    
    .action-row {
        height: auto;
        margin-bottom: 1;
    }
    
    .action-row Button {
        column-span: 1;
        width: 1fr;
        margin-right: 1;
    }
    
    .import-row {
        height: auto;
    }
    
    .import-row Select {
        width: 1fr;
        margin-right: 1;
    }
    
    .import-row Button {
        width: auto;
    }
    """

    BINDINGS = [
        Binding("ctrl+t", "tailor_both", "Tailor Both (AI)", show=True),
        Binding("ctrl+c", "compile_standard", "Compile Standard", show=True),
        Binding("ctrl+d", "show_database", "Database Browser", show=True),
        Binding("ctrl+q", "quit", "Exit", show=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())

    def log_message(self, message: str) -> None:
        try:
            log = self.query_one("#log-view", RichLog)
            log.write(message)
        except Exception:
            pass

    def mount_template_checkboxes(self) -> None:
        """Mount compilation checkboxes based on files on disk."""
        try:
            container = self.query_one("#template-checkboxes-container")
        except Exception:
            return

        # Keep only select-all
        for child in list(container.children):
            if child.id != "chk-select-all":
                child.remove()

        # 1. JSON Resume compiler
        container.mount(Checkbox("JSON Resume (Compiled)", value=True))

        # 2. Resumes
        res_dir = Path("templates/resumes")
        if res_dir.is_dir():
            for f in sorted(res_dir.glob("*.tex")):
                container.mount(Checkbox(f"Resume Template: {f.name}", value=True))

        # 3. Cover Letters
        cl_dir = Path("templates/cover_letters")
        if cl_dir.is_dir():
            for f in sorted(cl_dir.glob("*.tex")):
                container.mount(Checkbox(f"Cover Letter Template: {f.name}", value=True))

    def refresh_template_options(self) -> None:
        """Refresh template pickers and compilation checkboxes."""
        # Resume options
        res_dir = Path("templates/resumes")
        resume_options = []
        if res_dir.is_dir():
            resume_options = [(f.name, f.name) for f in sorted(res_dir.glob("*.tex"))]
        
        try:
            resume_select = self.query_one("#resume-select", Select)
            old_val = resume_select.value
            resume_select.set_options(resume_options)
            if old_val in [opt[0] for opt in resume_options]:
                resume_select.value = old_val
            elif resume_options:
                resume_select.value = resume_options[0][0]
        except Exception:
            pass

        # Cover letter options
        cl_dir = Path("templates/cover_letters")
        cl_options = []
        if cl_dir.is_dir():
            cl_options = [(f.name, f.name) for f in sorted(cl_dir.glob("*.tex"))]
            
        try:
            cl_select = self.query_one("#cl-select", Select)
            old_val = cl_select.value
            cl_select.set_options(cl_options)
            if old_val in [opt[0] for opt in cl_options]:
                cl_select.value = old_val
            elif cl_options:
                cl_select.value = cl_options[0][0]
        except Exception:
            pass

        self.mount_template_checkboxes()

    def get_selected_compilations(self) -> list[dict[str, Any]]:
        """Determine which templates are selected for compilation."""
        selected = []
        try:
            container = self.query_one("#template-checkboxes-container")
            for cb in container.query(Checkbox):
                if cb.id == "chk-select-all":
                    continue
                if cb.value:
                    label = str(cb.label)
                    if label == "JSON Resume (Compiled)":
                        selected.append({"type": "json-resume"})
                    elif label.startswith("Resume Template: "):
                        filename = label[len("Resume Template: "):]
                        selected.append({"type": "resume", "path": Path("templates/resumes") / filename})
                    elif label.startswith("Cover Letter Template: "):
                        filename = label[len("Cover Letter Template: "):]
                        selected.append({"type": "cover-letter", "path": Path("templates/cover_letters") / filename})
        except Exception:
            pass
        return selected

    def run_subprocess_cmd(self, cmd: list[str]) -> bool:
        """Run a process and direct its lines to TUI logs."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            if process.stdout:
                for line in process.stdout:
                    self.log_message("  " + line.strip())
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.log_message(f"  [bold red]Exception:[/bold red] {e}")
            return False

    def compile_single_tex(self, path: Path, output_dir_str: str) -> None:
        """Helper to compile a single LaTeX template and move the output PDF."""
        filename = path.stem
        # Compile using pdflatex via latexmk
        cmd1 = ["latexmk", "-pdf", "-interaction=nonstopmode", f"-output-directory={output_dir_str}", str(path)]
        success = self.run_subprocess_cmd(cmd1)
        if success:
            src_pdf = Path(output_dir_str) / f"{filename}.pdf"
            dest_pdf = Path("resumes") / f"{filename}.pdf"
            if src_pdf.is_file():
                try:
                    shutil.move(src_pdf, dest_pdf)
                except Exception as e:
                    self.log_message(f"  [bold red]Failed to move PDF:[/bold red] {e}")
            # Clean up intermediate files
            cmd2 = ["latexmk", "-c", f"-output-directory={output_dir_str}", str(path)]
            self.run_subprocess_cmd(cmd2)
        else:
            self.log_message("  latexmk failed, trying pdflatex fallback...")
            cmd3 = ["pdflatex", "-interaction=nonstopmode", f"-output-directory={output_dir_str}", str(path)]
            success = self.run_subprocess_cmd(cmd3)
            if success:
                src_pdf = Path(output_dir_str) / f"{filename}.pdf"
                dest_pdf = Path("resumes") / f"{filename}.pdf"
                if src_pdf.is_file():
                    try:
                        shutil.move(src_pdf, dest_pdf)
                    except Exception as e:
                        self.log_message(f"  [bold red]Failed to move PDF:[/bold red] {e}")

    def run_cmd_async(self, cmd: list[str]) -> None:
        """Helper to run standard command async (e.g. AI tailoring generator)."""
        def worker() -> None:
            self.log_message(f"[bold blue]Running:[/bold blue] {' '.join(cmd)}")
            self.run_subprocess_cmd(cmd)
            self.log_message("[bold green]Command finished.[/bold green]")
        self.run_worker(worker)

    def trigger_tailor(self, mode: str) -> None:
        """Trigger generate.py to tailor resume/cover letters based on inputs."""
        try:
            jd_input = self.query_one("#jd-input", TextArea)
            resume_select = self.query_one("#resume-select", Select)
            cl_select = self.query_one("#cl-select", Select)
            output_name_input = self.query_one("#output-name", Input)
        except Exception as e:
            self.log_message(f"[bold red]Error accessing input widgets:[/bold red] {e}")
            return

        jd_text = jd_input.text.strip()
        if not jd_text:
            self.log_message("[bold red]Error:[/bold red] Job Description cannot be empty.")
            return

        jd_temp = Path(".jd_temp.txt")
        try:
            with open(jd_temp, "w", encoding="utf-8") as f:
                f.write(jd_text)
        except Exception as e:
            self.log_message(f"[bold red]Failed to write temp JD file:[/bold red] {e}")
            return

        resume_template = Path("templates/resumes") / str(resume_select.value)
        cl_template = Path("templates/cover_letters") / str(cl_select.value)
        output_name = output_name_input.value.strip() or "tailored"

        cmd = ["python", "src/generate.py", "--mode", mode, "--jd", str(jd_temp), "--output-name", output_name]
        
        if mode in ["resume", "both"]:
            cmd += ["--resume-template", str(resume_template)]
        if mode in ["cover-letter", "both"]:
            cmd += ["--cover-letter-template", str(cl_template)]

        self.run_cmd_async(cmd)

    def run_selected_compilations(self) -> None:
        """Asynchronously compiles only the checked templates."""
        selected_items = self.get_selected_compilations()
        if not selected_items:
            self.log_message("[bold red]Error:[/bold red] No targets selected for compilation.")
            return

        def worker() -> None:
            self.log_message(f"[bold blue]Starting compilation for {len(selected_items)} selected target(s)...[/bold blue]")
            Path("resumes").mkdir(parents=True, exist_ok=True)
            
            for item in selected_items:
                t = item["type"]
                if t == "json-resume":
                    self.log_message("[bold yellow]Compiling JSON Resume...[/bold yellow]")
                    cmd = ["python", "src/compile.py", "--resume", "templates/experiences.json", "--output", "resumes/Simon_Chen_Resume_Compiled.tex"]
                    self.run_subprocess_cmd(cmd)
                elif t == "resume":
                    path = item["path"]
                    self.log_message(f"[bold yellow]Compiling Resume: {path.name}...[/bold yellow]")
                    self.compile_single_tex(path, "templates/resumes")
                elif t == "cover-letter":
                    path = item["path"]
                    self.log_message(f"[bold yellow]Compiling Cover Letter: {path.name}...[/bold yellow]")
                    self.compile_single_tex(path, "templates/cover_letters")
            self.log_message("[bold green]Selected compilations complete![/bold green]")
        self.run_worker(worker)

    def import_template(self) -> None:
        """Copy or save a new template using postpending naming rules."""
        try:
            mode_select = self.query_one("#import-mode", Select)
            type_select = self.query_one("#import-type", Select)
            path_input = self.query_one("#import-path", Input)
            name_input = self.query_one("#import-name", Input)
            latex_input = self.query_one("#import-latex-input", TextArea)
        except Exception as e:
            self.log_message(f"[bold red]Error accessing import widgets:[/bold red] {e}")
            return

        import_mode = mode_select.value
        template_type = type_select.value
        dest_dir = Path("templates/resumes") if template_type == "resume" else Path("templates/cover_letters")
        dest_dir.mkdir(parents=True, exist_ok=True)

        if import_mode == "path":
            # 1. Import from local file path
            src_path_str = path_input.value.strip()
            if not src_path_str:
                self.log_message("[bold red]Error:[/bold red] Import path cannot be empty.")
                return

            src_path = Path(src_path_str).expanduser().resolve()
            if not src_path.is_file():
                self.log_message(f"[bold red]Error:[/bold red] File not found at {src_path}")
                return

            if src_path.suffix != ".tex":
                self.log_message("[bold red]Error:[/bold red] Only LaTeX (.tex) template files can be imported.")
                return

            # Format destination filename enforcing the naming rule
            dest_filename = format_template_filename(src_path.stem, template_type)
            dest_path = dest_dir / dest_filename

            try:
                shutil.copy2(src_path, dest_path)
                self.log_message(f"[bold green]Import success:[/bold green] Imported {src_path.name} as {dest_filename} to {dest_dir}")
                path_input.value = ""
                self.refresh_template_options()
            except Exception as e:
                self.log_message(f"[bold red]Import failed:[/bold red] {e}")

        else:
            # 2. Paste raw LaTeX code
            raw_name = name_input.value.strip()
            latex_code = latex_input.text.strip()

            if not raw_name:
                self.log_message("[bold red]Error:[/bold red] Template Name cannot be empty when pasting LaTeX.")
                return
            if not latex_code:
                self.log_message("[bold red]Error:[/bold red] LaTeX code cannot be empty.")
                return

            # Format destination filename enforcing the naming rule
            dest_filename = format_template_filename(raw_name, template_type)
            dest_path = dest_dir / dest_filename

            try:
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(latex_code)
                self.log_message(f"[bold green]Save success:[/bold green] Saved pasted LaTeX as {dest_filename} to {dest_dir}")
                name_input.value = ""
                latex_input.text = ""
                self.refresh_template_options()
            except Exception as e:
                self.log_message(f"[bold red]Save failed:[/bold red] {e}")

    # Action Handlers
    def action_show_database(self) -> None:
        self.push_screen(DatabaseScreen())

    def action_compile_standard(self) -> None:
        self.run_selected_compilations()

    def action_tailor_both(self) -> None:
        self.trigger_tailor("both")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-compile-standard":
            self.action_compile_standard()
        elif button_id == "btn-tailor-both":
            self.action_tailor_both()
        elif button_id == "btn-tailor-resume":
            self.trigger_tailor("resume")
        elif button_id == "btn-tailor-cl":
            self.trigger_tailor("cover-letter")
        elif button_id == "btn-import":
            self.import_template()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-select-all":
            val = event.checkbox.value
            try:
                container = self.query_one("#template-checkboxes-container")
                for cb in container.query(Checkbox):
                    if cb.id != "chk-select-all":
                        cb.value = val
            except Exception:
                pass

    def on_select_changed(self, event: Select.Changed) -> None:
        # Toggle displays when switching between Path import and Paste import modes
        if event.select.id == "import-mode":
            mode = event.select.value
            try:
                path_input = self.query_one("#import-path")
                name_input = self.query_one("#import-name")
                latex_input = self.query_one("#import-latex-input")
                
                if mode == "path":
                    path_input.styles.display = "block"
                    name_input.styles.display = "none"
                    latex_input.styles.display = "none"
                else: # paste
                    path_input.styles.display = "none"
                    name_input.styles.display = "block"
                    latex_input.styles.display = "block"
            except Exception:
                pass


if __name__ == "__main__":
    app = ResumeTUI()
    app.run()
