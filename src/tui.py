from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, TabbedContent, TabPane, TextArea


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
                yield Label("Job Application Inputs", classes="panel-title")
                yield Label("Paste Job Description:")
                yield TextArea(id="jd-input", show_line_numbers=False)

                # Find resume templates
                res_dir = Path("templates/resumes")
                resume_options = []
                if res_dir.is_dir():
                    resume_options = [
                        (f.name, f.name) for f in sorted(res_dir.glob("*.tex"))
                    ]
                
                yield Label("Select Resume Template:")
                yield Select(
                    resume_options,
                    id="resume-select",
                    value=resume_options[0][0] if resume_options else None,
                    allow_blank=False,
                )

                # Find cover letter templates
                cl_dir = Path("templates/cover_letters")
                cl_options = []
                if cl_dir.is_dir():
                    cl_options = [
                        (f.name, f.name) for f in sorted(cl_dir.glob("*.tex"))
                    ]

                yield Label("Select Cover Letter Template:")
                yield Select(
                    cl_options,
                    id="cl-select",
                    value=cl_options[0][0] if cl_options else None,
                    allow_blank=False,
                )

                yield Label("Output Name Prefix:")
                yield Input(id="output-name", value="tailored")

                yield Button("Tailor Both (AI)", variant="primary", id="btn-tailor-both")
                yield Button("Tailor Resume Only", variant="success", id="btn-tailor-resume")
                yield Button("Tailor Cover Letter Only", variant="success", id="btn-tailor-cl")

            with Vertical(id="right-panel"):
                yield Label("Activity Logs & Status", classes="panel-title")
                yield RichLog(id="log-view", highlight=True, markup=True)
                yield Button("Compile Standard Templates", variant="warning", id="btn-compile-standard")
        yield Footer()


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
        grid-columns: 1fr 1.2fr;
        grid-rows: 1fr;
        padding: 1;
        gap: 1;
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
    
    #jd-input {
        height: 1fr;
        border: sunken $accent;
        margin-bottom: 1;
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

    def run_cmd_async(self, cmd: list[str]) -> None:
        """Run a command asynchronously in a Textual worker to avoid blocking TUI."""
        def worker() -> None:
            self.log_message(f"[bold blue]Running:[/bold blue] {' '.join(cmd)}")
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
                        self.log_message(line.strip())
                process.wait()
                if process.returncode == 0:
                    self.log_message("[bold green]Success![/bold green] Command completed.")
                else:
                    self.log_message(f"[bold red]Error:[/bold red] Exit code {process.returncode}")
            except Exception as e:
                self.log_message(f"[bold red]Exception:[/bold red] {e}")
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

        # Write Job Description to a temp file to avoid shell argument size limits
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

    # Actions triggered by keybindings or UI buttons
    def action_show_database(self) -> None:
        self.push_screen(DatabaseScreen())

    def action_compile_standard(self) -> None:
        self.run_cmd_async(["/bin/bash", "./compile.sh"])

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


if __name__ == "__main__":
    app = ResumeTUI()
    app.run()
