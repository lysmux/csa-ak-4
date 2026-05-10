from app.isa.flags import Flags
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
            io_map: dict[int, Device]
    ) -> None:
        self.memory = memory
        self.stack = stack
        self.io_map = io_map

        self._flags: Flags = Flags(0)
        self._alu = Alu()

        self._dr = 0
        self._ar = 0

        self._tos = 0
        self._nos = 0

    @property
    def flags(self) -> Flags:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flags(value)

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
        self._flags = Flags.nz(value)

    def cmp(self) -> None:
        result = self._alu.perform(Opcode.SUB, self.stack.nos, self.stack.tos)
        self._flags = result.flags

    def pop(self) -> int:
        result = self.stack.pop()
        self._flags = Flags.nz(self.stack.tos)
        return result

    def write(self, address: int, value: int) -> None:
        if device := self.io_map.get(address):
            device.write(value)
        else:
            self.memory.write(address, value)

    def read(self, address: int) -> int:
        if device := self.io_map.get(address):
            return device.read()
        else:
            return self.memory.read(address)