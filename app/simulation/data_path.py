from app.isa.flags import Flags
from app.isa.opcode import Opcode
from app.simulation.alu import Alu
from app.simulation.memory import Memory
from app.simulation.register import Register
from app.simulation.stack import Stack


class DataPath:
    def __init__(self, memory: Memory, stack: Stack) -> None:
        self._memory = memory
        self._stack = stack

        self._flags: Flags = Flags(0)
        self._alu = Alu()

        self._dr = Register()
        self._a = Register()

    # ── Flags ────────────────────────────────────────────────────────────────

    @property
    def flags(self) -> Flags:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flags(value)

    # ── Memory ───────────────────────────────────────────────────────────────

    @property
    def memory(self) -> Memory:
        return self._memory

    def dmem_read(self) -> None:
        self._memory.get_signal()

    def dmem_write(self) -> None:
        self._memory.set_in(self._dr.current)
        self._memory.write_signal()

    # ── Data Register ────────────────────────────────────────────────────────

    def dr_latch_mem(self) -> None:
        self._dr.latch(self._memory.out)

    def dr_latch_tos(self) -> None:
        self._dr.latch(self._stack.tos.current)

    def push_dr(self) -> None:
        self.push(self._dr.current)

    # ── Stack ────────────────────────────────────────────────────────────────

    @property
    def tos(self) -> int:
        return self._stack.tos.current

    @property
    def nos(self) -> int:
        return self._stack.nos.current

    def push(self, value: int) -> None:
        self._stack.push(value)
        self._flags = Flags.nz(value)

    def pop(self) -> int:
        result = self._stack.pop()
        self._flags = Flags.nz(self.tos)
        return result

    def dup(self) -> None:
        self.push(self._stack.tos.current)

    def swap(self) -> None:
        top = self._stack.pop()
        nos = self._stack.pop()
        self._stack.push(top)
        self._stack.push(nos)
        self._flags = Flags.nz(nos)

    def over(self) -> None:
        self.push(self._stack.nos.current)

    # ── Register A ───────────────────────────────────────────────────────────

    @property
    def a(self) -> int:
        return self._a.current

    def a_latch_tos(self) -> None:
        value = self._stack.pop()
        self._a.latch(value)
        self._flags = Flags.nz(value)

    def push_a(self) -> None:
        self._stack.push(self._a.current)

    def a_inc(self) -> None:
        self._a.latch(self._a.current + 1)

    def a_dec(self) -> None:
        self._a.latch(self._a.current - 1)

    # ── ALU ──────────────────────────────────────────────────────────────────

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0) -> int:
        result = self._alu.perform(opcode, left, right)
        self._flags = result.flags
        return result.value

    def alu_binary(self, opcode: Opcode) -> None:
        right = self._stack.pop()
        left  = self._stack.pop()
        result = self._alu.perform(opcode, left, right)
        self._flags = result.flags
        self._stack.push(result.value)

    def alu_unary(self, opcode: Opcode) -> None:
        val = self._stack.pop()
        result = self._alu.perform(opcode, val)
        self._flags = result.flags
        self._stack.push(result.value)

    def alu_cmp(self) -> None:
        result = self._alu.perform(Opcode.CMP, self._stack.nos.current, self._stack.tos.current)
        self._flags = result.flags
