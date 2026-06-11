from app.isa.flag import Flag
from app.isa.opcode import Opcode
from app.simulation.alu import Alu
from app.simulation.io import Device
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DSPMux, NosMux, TosMux
from app.simulation.stack import DataStack


class DataPath:
    def __init__(
        self,
        memory: Memory,
        stack: DataStack,
        io_map: dict[int, Device],
    ) -> None:
        self.memory = memory
        self.stack = stack
        self.io_map = io_map

        self._flags: Flag = Flag(0)
        self._alu = Alu()

        self._ar = 0

        self._operand = 0
        self._r_top_in = 0
        self.alu_out = 0
        self._mem_out = 0

    @property
    def flags(self) -> Flag:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flag(value)

    @property
    def ar(self) -> int:
        return self._ar

    def set_operand(self, value: int) -> None:
        self._operand = value

    def set_r_top(self, value: int) -> None:
        self._r_top_in = value

    def latch_ar(self, mux: ARMux) -> None:
        match mux:
            case ARMux.OPERAND:
                self._ar = self._operand
            case ARMux.TOS:
                self._ar = self.stack.tos

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0, carry_in: int = 0) -> int:
        result = self._alu.perform(opcode, left, right, carry_in)
        self._flags = result.flags
        self.alu_out = result.value
        return result.value

    def is_alu_binary_opcode(self, opcode: Opcode) -> bool:
        return self._alu.is_binary(opcode)

    def is_alu_unary_opcode(self, opcode: Opcode) -> bool:
        return self._alu.is_unary(opcode)

    def _tos_source(self, mux: TosMux) -> int:
        match mux:
            case TosMux.OPERAND:
                return self._operand
            case TosMux.NOS:
                return self.stack.nos
            case TosMux.ALU:
                return self.alu_out
            case TosMux.MEMORY:
                return self._mem_out
            case TosMux.R_STACK:
                return self._r_top_in

    def latch_tos(self, mux: TosMux) -> None:
        self.stack.tos = self._tos_source(mux)

    def latch_nos(self, mux: NosMux) -> None:
        match mux:
            case NosMux.TOS:
                value = self.stack.tos
            case NosMux.D_STACK:
                value = self.stack.read()
            case NosMux.ALU:
                value = self.alu_out
        self.stack.nos = value

    def push(self, mux: TosMux) -> None:
        value = self._tos_source(mux)
        self.stack.write_nos()
        self.stack.latch_sp(DSPMux.INC)
        self.stack.nos = self.stack.tos
        self.stack.tos = value
        self.set_nz_from_tos()

    def pop(self) -> None:
        self.latch_tos(TosMux.NOS)
        self.latch_nos(NosMux.D_STACK)

    def dup(self) -> None:
        self.stack.write_nos()
        self.stack.latch_sp(DSPMux.INC)
        self.stack.nos = self.stack.tos

    def cmp(self) -> None:
        result = self._alu.perform(Opcode.SUB, self.stack.nos, self.stack.tos)
        self._flags = result.flags

    def set_nz_from_tos(self) -> None:
        self._flags = Flag.nz(self.stack.tos)

    def write(self, value: int) -> None:
        if device := self.io_map.get(self._ar):
            device.write(value)
        else:
            self.memory.write(self._ar, value)

    def read(self) -> int:
        if device := self.io_map.get(self._ar):
            value = device.read()
        else:
            value = self.memory.read(self._ar)
        self._mem_out = value
        return value
