"""Textual TUI: paste a job description, get a one-page tailored PDF."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, RichLog, TextArea

from .pipeline import build_canonical, tailor


class WorksisyphusApp(App):
    TITLE = "worksisyphus"
    SUB_TITLE = "paste a job description, get a one-page resume"
    BINDINGS = [("ctrl+q", "quit", "Quit"), ("ctrl+l", "clear_log", "Clear log")]
    CSS = """
    TextArea { height: 1fr; margin: 1; }
    Horizontal { height: auto; margin: 0 1; }
    Button { margin-right: 2; }
    RichLog { height: 12; margin: 1; border: solid $accent; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield TextArea(id="jd")
        with Horizontal():
            yield Button("Generate resume", id="generate", variant="primary")
            yield Button("Rebuild canonical", id="canonical")
        yield RichLog(id="log", wrap=True)
        yield Footer()

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    def _log(self, message: str) -> None:
        self.call_from_thread(self.query_one("#log", RichLog).write, message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for button in self.query(Button):
            button.disabled = True
        if event.button.id == "generate":
            jd_text = self.query_one("#jd", TextArea).text
            self.run_worker(lambda: self._run(lambda: tailor(jd_text, log=self._log)), thread=True)
        else:
            self.run_worker(lambda: self._run(lambda: build_canonical(log=self._log)), thread=True)

    def _run(self, job) -> None:
        try:
            job()
        except Exception as exc:
            self._log(f"[red]error:[/red] {exc}")
        finally:
            for button in self.query(Button):
                self.call_from_thread(setattr, button, "disabled", False)


def main() -> None:
    WorksisyphusApp().run()


if __name__ == "__main__":
    main()
