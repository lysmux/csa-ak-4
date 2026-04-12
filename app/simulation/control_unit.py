import logging
from enum import StrEnum, auto

from app.simulation.data_path import DataPath
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.memory import Memory
from app.simulation.trigger import DTrigger

logger = logging.getLogger(__name__)


class Signal(StrEnum):
    # Fetch
    LATCH_PC_ADDR = auto()    # instruction memory address ← PC
    MEM_FETCH = auto()        # read instruction memory
    LATCH_IR = auto()         # IR ← instruction memory output
    PC_INC = auto()           # PC ← PC + 1

    # PC control
    SEL_PC_CR     = auto()    # PC source: instruction operand
    LATCH_PC      = auto()    # unconditional jump
    LATCH_PC_IF_C = auto()    # jump if Carry
    LATCH_PC_IF_Z = auto()    # jump if Zero
    LATCH_PC_IF_N = auto()    # jump if Negative

    # Address mux
    SEL_ADDR_CR = auto()      # data memory address source: instruction operand

    # Data memory
    LATCH_ADDR = auto()
    MEM_READ = auto()
    MEM_WRITE = auto()

    # Data register
    LATCH_DR = auto()

    # Stack mux + push/pop
    SEL_STACK_DR = auto()     # push source: DR
    SEL_STACK_ALU = auto()    # push source: ALU output
    STACK_PUSH = auto()
    STACK_POP = auto()

    # ALU
    ALU_ADD = auto()
    ALU_SUB = auto()
    ALU_INC = auto()
    ALU_DEC = auto()
    LATCH_STATUS = auto()


FETCH_SIGNALS: list[list[Signal]] = [
    [Signal.LATCH_PC_ADDR, Signal.MEM_FETCH],
    [Signal.LATCH_IR, Signal.PC_INC],
]

SIGNALS: dict[Opcode, list[list[Signal]]] = {
    Opcode.LOAD: [
        [Signal.SEL_ADDR_CR, Signal.LATCH_ADDR, Signal.MEM_READ],
        [Signal.LATCH_DR],
        [Signal.SEL_STACK_DR, Signal.STACK_PUSH],
    ],
    Opcode.ADD: [
        [Signal.ALU_ADD, Signal.LATCH_STATUS],
        [Signal.STACK_POP],
        [Signal.STACK_POP],
        [Signal.SEL_STACK_ALU, Signal.STACK_PUSH],
    ],
    Opcode.SUB: [
        [Signal.ALU_SUB, Signal.LATCH_STATUS],
        [Signal.STACK_POP],
        [Signal.STACK_POP],
        [Signal.SEL_STACK_ALU, Signal.STACK_PUSH],
    ],
    Opcode.INC: [
        [Signal.ALU_INC, Signal.LATCH_STATUS],
        [Signal.STACK_POP],
        [Signal.SEL_STACK_ALU, Signal.STACK_PUSH],
    ],
    Opcode.DEC: [
        [Signal.ALU_DEC, Signal.LATCH_STATUS],
        [Signal.STACK_POP],
        [Signal.SEL_STACK_ALU, Signal.STACK_PUSH],
    ],
    Opcode.JMP: [
        [Signal.SEL_PC_CR, Signal.LATCH_PC],
    ],
    Opcode.JC: [
        [Signal.SEL_PC_CR, Signal.LATCH_PC_IF_C],
    ],
    Opcode.JZ: [
        [Signal.SEL_PC_CR, Signal.LATCH_PC_IF_Z],
    ],
    Opcode.JN: [
        [Signal.SEL_PC_CR, Signal.LATCH_PC_IF_N],
    ],
}


class ControlUnit:
    def __init__(self, data_path: DataPath, instruction_memory: Memory) -> None:
        self._data_path = data_path
        self._instruction_memory = instruction_memory
        self._pc = DTrigger()
        self._ir: Instruction = Instruction(Opcode.HALT)
        self._tick = 0

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def current_pc(self) -> int:
        return self._pc.current

    @property
    def current_instruction(self) -> Instruction:
        return self._ir

    def tick(self) -> int:
        self._tick += 1
        return self._tick

    def decode(self) -> list[list[Signal]]:
        """Returns execute signal groups for IR. Raises StopIteration on HALT."""
        if self._ir.opcode == Opcode.HALT:
            raise StopIteration()
        return SIGNALS.get(self._ir.opcode, [])

    def step(self, signals: list[Signal]) -> None:
        """Execute one signal group and advance the tick counter."""
        self._dispatch_signals(signals)
        self.tick()

    def _dispatch_signals(self, signals: list[Signal]) -> None:
        addr: int | None = None
        stack_src: str | None = None
        pc_src: int | None = None

        for signal in signals:
            match signal:
                case Signal.LATCH_PC_ADDR:
                    self._instruction_memory.addr.latch(self._pc.current)
                case Signal.MEM_FETCH:
                    self._instruction_memory.get_signal()
                case Signal.LATCH_IR:
                    self._ir = Instruction.from_binary(self._instruction_memory.out)
                case Signal.PC_INC:
                    self._pc.latch(self.current_pc + 1)
                case Signal.SEL_PC_CR:
                    pc_src = self._ir.operand
                case Signal.LATCH_PC:
                    self._pc.latch(pc_src)
                case Signal.LATCH_PC_IF_C:
                    if self._data_path.status.c:
                        self._pc.latch(pc_src)
                case Signal.LATCH_PC_IF_Z:
                    if self._data_path.status.z:
                        self._pc.latch(pc_src)
                case Signal.LATCH_PC_IF_N:
                    if self._data_path.status.n:
                        self._pc.latch(pc_src)
                case Signal.SEL_ADDR_CR:
                    addr = self._ir.operand
                case Signal.LATCH_ADDR:
                    self._data_path.latch_addr(addr)
                case Signal.MEM_READ:
                    self._data_path.mem_read()
                case Signal.LATCH_DR:
                    self._data_path.latch_dr()
                case Signal.SEL_STACK_DR:
                    stack_src = "dr"
                case Signal.SEL_STACK_ALU:
                    stack_src = "alu"
                case Signal.STACK_PUSH:
                    if stack_src == "dr":
                        self._data_path.stack_push_dr()
                    else:
                        self._data_path.stack_push_alu()
                case Signal.STACK_POP:
                    self._data_path.stack_pop()
                case Signal.ALU_ADD:
                    self._data_path.alu_exec(Opcode.ADD)
                case Signal.ALU_SUB:
                    self._data_path.alu_exec(Opcode.SUB)
                case Signal.ALU_INC:
                    self._data_path.alu_exec(Opcode.INC)
                case Signal.ALU_DEC:
                    self._data_path.alu_exec(Opcode.DEC)
                case Signal.LATCH_STATUS:
                    self._data_path.latch_status()
