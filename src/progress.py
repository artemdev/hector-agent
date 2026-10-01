import logging
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal
import time

from rich import get_console
from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.padding import Padding
from rich.spinner import Spinner
from rich.table import Table

from src.observability import langfuse

console = get_console()
logger = logging.getLogger(__name__)


IssueStatus = Literal["pending", "resolved", "unchanged", "failed"]
ISSUE_ICONS = {
    "pending": "[yellow]○[/]",
    "resolved": "[green]✓[/]",
    "unchanged": "[dim]–[/]",
    "failed": "[red]✗[/]",
}


@dataclass
class _Step:
    label: str
    started: float = field(default_factory=time.monotonic)
    duration: float | None = None  # None while running
    failed: bool = False  # set when the block raised
    spinner: Spinner = field(default_factory=lambda: Spinner("dots"))
    output: object = None  # the step's result, recorded as the Langfuse observation's output


@dataclass
class IssueProgress:
    """An issue's title with its status icon, and its steps indented underneath."""

    key: str
    title: str
    status: IssueStatus = "pending"
    steps: list[_Step] = field(default_factory=list)
    live: bool = field(default_factory=lambda: console.is_terminal)  # else log lines (server logs)

    def __rich__(self) -> Group:
        steps = Table.grid(padding=(0, 1))

        for s in self.steps:
            if s.duration is None:
                icon, elapsed = s.spinner, time.monotonic() - s.started
            else:
                icon, elapsed = _step_icon(s), s.duration
            steps.add_row(icon, f"{escape(s.label)} [dim]({elapsed:.1f}s)[/]")

        heading = f"{ISSUE_ICONS[self.status]} {escape(self.key)}: {escape(self.title)}"

        return Group(heading, Padding(steps, (0, 0, 0, 4), expand=False))


def _step_icon(s: _Step) -> str:
    return ISSUE_ICONS["failed"] if s.failed else ISSUE_ICONS["resolved"]


_current_issue: ContextVar[IssueProgress] = ContextVar("current_issue")

@contextmanager
def track_issue(key: str, title: str) -> Generator[IssueProgress, None, None]:
    """Show the issue as pending while the block runs, with any `step`s inside nested under it.

    Set `.status` on the yielded progress to "resolved"/"unchanged"/"failed" before the block ends; an
    exception marks it failed. On a terminal this is a live view with spinners; otherwise
    (server logs) each status change is one log line prefixed with `key`.
    """
    progress = IssueProgress(key, title)
    token = _current_issue.set(progress)

    if not progress.live:
        logger.info("%s: %s", key, title)
    try:
        with Live(progress, console=console, refresh_per_second=10) if progress.live else nullcontext():
            try:
                yield progress
            except BaseException:
                progress.status = "failed"
                raise
    finally:
        _current_issue.reset(token)
        if not progress.live:
            logger.info("%s: %s", key, progress.status)


@contextmanager
def step(label: str, *, tool: str | None = None) -> Generator[_Step, None, None]:
    """Show `label` with a spinner under the current `track_issue`, then ✓ (or ✗ on error) with its duration.

    With `tool`, the block is also a Langfuse tool observation of that (stable) name; set
    `.output` on the yielded step to record the step's result there.
    """
    if tool is None:
        with _display_step(label) as current:
            yield current
        return

    with (
        langfuse.start_as_current_observation(name=tool, as_type="tool", input=label) as observation,
        _display_step(label) as current,
    ):
        try:
            yield current
        except BaseException as e:
            observation.update(level="ERROR", status_message=repr(e))
            raise
        observation.update(output=current.output)


@contextmanager
def _display_step(label: str) -> Generator[_Step, None, None]:
    issue = _current_issue.get()  # LookupError outside `track_issue`
    current = _Step(label)
    issue.steps.append(current)

    if not issue.live:
        logger.info("%s: %s...", issue.key, label)
    try:
        yield current
    except BaseException:
        current.failed = True
        raise
    finally:
        current.duration = time.monotonic() - current.started
        if not issue.live:
            icon = "✗" if current.failed else "✓"
            logger.info("%s: %s %s (%.1fs)", issue.key, icon, label, current.duration)

