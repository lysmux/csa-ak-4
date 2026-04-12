from dataclasses import dataclass

from app.simulation.alu import ALU
from app.isa.opcode import Opcode
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.simulation.trigger import DTrigger


@dataclass
class StatusRegister:
    n: bool = False
    z: bool = False
    v: bool = False
    c: bool = False


class DataPath:
    def __init__(self, memory: Memory, stack: Stack) -> None:
        self.memory = memory
        self.stack = stack
        self.alu = ALU()
        self.status = StatusRegister()
        self.dr = DTrigger()
        self._alu_out: int = 0

    # --- Memory ---

    def latch_addr(self, source: int) -> None:
        self.memory.addr.latch(source)

    def mem_read(self) -> None:
        self.memory.get_signal()

    def latch_dr(self) -> None:
        self.dr.latch(self.memory.out)

    # --- Stack ---

    def stack_push_dr(self) -> None:
        self.stack.push(self.dr.current)

    def stack_push_alu(self) -> None:
        self.stack.push(self._alu_out)

    def stack_pop(self) -> int:
        return self.stack.pop()

    # --- ALU ---

    def alu_exec(self, opcode: Opcode) -> None:
        self._alu_out = self.alu.perform(opcode, self.stack.tos.current, self.stack.nos.current)

    def latch_status(self) -> None:
        val = self._alu_out
        self.status.n = val < 0
        self.status.z = val == 0
        self.status.v = False
        self.status.c = False
