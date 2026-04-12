import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import auto, StrEnum
from threading import Event

from app.simulation.control_unit import ControlUnit, Signal, FETCH_SIGNALS
from app.simulation.data_path import DataPath
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.memory import Memory
from app.simulation.stack import Stack

logger = logging.getLogger(__name__)


class Mode(StrEnum):
    DEFAULT = auto()
    TICK = auto()


@dataclass
class SimState:
    is_running: bool
    tick: int
    pc: int
    opcode: str
    operand: int | None
    signals: list[str]
    tos: int
    nos: int
    ar: int
    dr: int
    n: bool
    z: bool
    v: bool
    c: bool
    data_stack: list[int] = field(default_factory=list)
    call_stack: list[int] = field(default_factory=list)


def _stack_values(stack: Stack) -> list[int]:
    values = []
    if stack.v_tos:
        values.append(stack.tos.current)
    if stack.v_nos:
        values.append(stack.nos.current)
    for i in range(stack.sp, -1, -1):
        values.append(stack.stack[i])
    return values


def _build_state(
    is_running: bool,
    signals: list[Signal],
    control_unit: ControlUnit,
    data_stack: Stack,
    call_stack: Stack,
    data_memory: Memory,
    data_path: DataPath,
) -> SimState:
    instruction = control_unit.current_instruction
    return SimState(
        is_running=is_running,
        tick=control_unit.current_tick,
        pc=control_unit.current_pc,
        opcode=instruction.opcode.name,
        operand=instruction.operand if instruction.operand != 0 else None,
        signals=[s.name for s in signals],
        tos=data_stack.tos.current if data_stack.v_tos else 0,
        nos=data_stack.nos.current if data_stack.v_nos else 0,
        ar=data_memory.addr.current,
        dr=data_path.dr.current,
        data_stack=_stack_values(data_stack),
        call_stack=_stack_values(call_stack),
        n=data_path.status.n,
        z=data_path.status.z,
        v=data_path.status.v,
        c=data_path.status.c,
    )


def run(
    mode: Mode,
    on_tick: Callable[[SimState], None] | None = None,
    step_event: Event | None = None,
    stop_event: Event | None = None,
) -> None:
    data_memory = Memory(capacity=10)
    instruction_memory = Memory(capacity=10)

    data_stack = Stack(capacity=10)
    call_stack = Stack(capacity=10)

    data_memory.fill([0x3])

    instruction_memory.fill([
        Instruction(Opcode.LOAD, 0).to_binary(),  # [0] push mem[0]
        Instruction(Opcode.DEC).to_binary(),  # [2] sub → обновит Z, N, C
        Instruction(Opcode.JZ, 4).to_binary(),  # [3] if Z → jump to 5
        Instruction(Opcode.JMP, 1).to_binary(),  # [4] loop back
        Instruction(Opcode.HALT).to_binary(),  # [5]
    ])

    data_path = DataPath(memory=data_memory, stack=data_stack)
    control_unit = ControlUnit(data_path=data_path, instruction_memory=instruction_memory)

    def emit(signals: list[Signal], is_running: bool = True) -> None:
        if on_tick is not None:
            on_tick(_build_state(is_running, signals, control_unit, data_stack, call_stack, data_memory, data_path))

    def wait_step() -> bool:
        """Returns True if stop was requested."""
        if mode == Mode.TICK and step_event is not None:
            step_event.wait()
            step_event.clear()
            return stop_event is not None and stop_event.is_set()
        return False

    while True:
        # Fetch cycle
        for signals in FETCH_SIGNALS:
            control_unit.step(signals)
            emit(signals)
            if wait_step():
                return

        # Decode
        try:
            exec_signal_groups = control_unit.decode()
        except StopIteration:
            emit([], is_running=False)
            break

        # Execute cycle
        for signals in exec_signal_groups:
            control_unit.step(signals)
            emit(signals)
            if wait_step():
                return
