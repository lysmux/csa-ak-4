import sys
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, ListView, Label, ListItem, Footer
from textual.containers import Vertical, Horizontal
from textual import work
from rich.text import Text

from app.simulation.simulation import run, Mode, SimState


def _word(val: int) -> str:
    return f"0x{val & 0xFFFF_FFFF:08X}"


class OpcodeView(Widget):
    opcode: reactive[str] = reactive("—")
    operand: reactive[int | None] = reactive(None)
    tick: reactive[int] = reactive(0)
    pc: reactive[int] = reactive(0)

    def render(self) -> Text:
        t = Text()
        t.append("Tick: ", style="dim")
        t.append(str(self.tick), style="bold magenta")
        t.append("   PC: ", style="dim")
        t.append(str(self.pc), style="bold magenta")
        t.append("   Opcode: ", style="dim")
        t.append(self.opcode, style="bold cyan")
        if self.operand is not None:
            t.append(",  Operand: ", style="dim")
            t.append(_word(self.operand), style="bold yellow")
        return t


class RegistersView(Widget):
    tos: reactive[int] = reactive(0)
    nos: reactive[int] = reactive(0)
    ar: reactive[int] = reactive(0)
    dr: reactive[int] = reactive(0)

    def render(self) -> Text:
        t = Text()
        for name, val in [("TOS", self.tos), ("NOS", self.nos), ("AR", self.ar), ("DR", self.dr)]:
            t.append(f"{name}: ", style="dim")
            t.append(f"{_word(val)}\n", style="bold green")
        return t


class SignalsView(Widget):
    signals: reactive[list[str]] = reactive(list)

    def render(self) -> Text:
        t = Text()
        for sig in self.signals:
            t.append(f" {sig} ", style="bold on dark_orange")
            t.append(" ")
        if not self.signals:
            t.append("—", style="dim")
        return t

class StatusView(Widget):
    n: reactive[bool] = reactive(False)
    z: reactive[bool] = reactive(False)
    v: reactive[bool] = reactive(False)
    c: reactive[bool] = reactive(False)

    def render(self) -> Text:
        t = Text()
        for name, val in [("N", self.n), ("Z", self.z), ("V", self.v), ("C", self.c)]:
            t.append(f" {name} ", style="bold on green" if val else "dim on #333333")
            t.append(" ")
        return t


class StackView(Widget):
    stack_data: reactive[list[int]] = reactive(list)

    def __init__(self, title: str = "Stack", **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes="stack-title")
        yield ListView()

    def watch_stack_data(self, data: list[int]) -> None:
        if not self.is_mounted:
            return
        lv = self.query_one(ListView)
        lv.clear()
        for item in data:
            lv.append(ListItem(Label(_word(item))))


class Debugger(App):
    CSS_PATH = "debug.tcss"

    BINDINGS = [
        Binding("down", "step", "Next tick", priority=True),
    ]

    def __init__(self, mode: Mode = Mode.DEFAULT):
        super().__init__()
        self._mode = mode
        self._step_event = threading.Event()
        self._stop_event = threading.Event()

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield OpcodeView(id="opcode")
                yield SignalsView(id="signals")
                yield StatusView(id="status")
                yield RegistersView(id="registers")
            with Vertical(id="right-panel"):
                yield StackView("Data Stack", id="data-stack")
                yield StackView("Return Stack", id="return-stack")
        if self._mode == Mode.TICK:
            yield Footer()

    def on_mount(self) -> None:
        self._run_simulation()

    def on_unmount(self) -> None:
        self._stop_event.set()
        self._step_event.set()

    @work(thread=True)
    def _run_simulation(self) -> None:
        step_event = self._step_event if self._mode == Mode.TICK else None
        run(mode=self._mode, on_tick=self._on_tick, step_event=step_event, stop_event=self._stop_event)

    def _on_tick(self, state: SimState) -> None:
        self.call_from_thread(self._update_ui, state)

    def _update_ui(self, state: SimState) -> None:
        opcode = self.query_one("#opcode", OpcodeView)
        opcode.tick = state.tick
        opcode.pc = state.pc
        opcode.opcode = state.opcode
        opcode.operand = state.operand

        self.query_one("#signals", SignalsView).signals = state.signals

        regs = self.query_one("#registers", RegistersView)
        regs.tos = state.tos
        regs.nos = state.nos
        regs.ar = state.ar
        regs.dr = state.dr

        status = self.query_one("#status", StatusView)
        status.n = state.n
        status.z = state.z
        status.v = state.v
        status.c = state.c

        self.query_one("#data-stack", StackView).stack_data = state.data_stack
        self.query_one("#return-stack", StackView).stack_data = state.call_stack

    def action_step(self) -> None:
        self._step_event.set()
