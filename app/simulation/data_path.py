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

    @property
    def memory(self) -> Memory:
        return self._memory

    @property
    def flags(self) -> Flags:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flags(value)

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

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0) -> int:
        result = self._alu.perform(opcode, left, right)
        self._flags = result.flags

        return result.value
