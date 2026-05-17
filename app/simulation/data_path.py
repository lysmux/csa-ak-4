from app.isa.flag import Flag
from app.isa.opcode import Opcode
from app.simulation.alu import Alu
from app.simulation.io import Device
from app.simulation.memory import Memory
from app.simulation.stack import Stack


class DataPath:
    def __init__(
        self,
        memory: Memory,
        stack: Stack,
        io_map: dict[int, Device],
    ) -> None:
        self.memory = memory
        self.stack = stack
        self.io_map = io_map

        self._flags: Flag = Flag(0)
        self._alu = Alu()

        self._ar = 0

        self._tos = 0
        self._nos = 0

    @property
    def flags(self) -> Flag:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flag(value)

    def latch_ar(self, value: int) -> None:
        self._ar = value

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0) -> int:
        result = self._alu.perform(opcode, left, right)
        self._flags = result.flags
        return result.value

    def is_alu_binary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.BINARY_OPERATIONS.keys()

    def is_alu_unary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.UNARY_OPERATIONS.keys()

    def push(self, value: int) -> None:
        self.stack.push(value)
        self._flags = Flag.nz(value)

    def push_raw(self, value: int) -> None:
        self.stack.push(value)

    def cmp(self) -> None:
        result = self._alu.perform(Opcode.SUB, self.stack.nos, self.stack.tos)
        self._flags = result.flags

    def pop(self) -> int:
        result = self.stack.pop()
        self._flags = Flag.nz(self.stack.tos)
        return result

    def pop_raw(self) -> int:
        return self.stack.pop()

    def write(self, value: int) -> None:
        if device := self.io_map.get(self._ar):
            device.write(value)
        else:
            self.memory.write(self._ar, value)

    def read(self) -> int:
        if device := self.io_map.get(self._ar):
            return device.read()
        return self.memory.read(self._ar)
