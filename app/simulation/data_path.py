from app.isa.flag import Flag
from app.isa.opcode import Opcode
from app.simulation.alu import Alu
from app.simulation.io import Device
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DStackMux
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

        self._ir_operand_in = 0
        self._r_top_in = 0
        self._alu_out = 0
        self._mem_out = 0

    @property
    def flags(self) -> Flag:
        return self._flags

    @flags.setter
    def flags(self, value: int) -> None:
        self._flags = Flag(value)

    def set_ir_operand(self, value: int) -> None:
        self._ir_operand_in = value

    def set_r_top(self, value: int) -> None:
        self._r_top_in = value

    def latch_ar(self, mux: ARMux) -> None:
        match mux:
            case ARMux.IR_OPERAND:
                self._ar = self._ir_operand_in
            case ARMux.TOS:
                self._ar = self.stack.tos

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0) -> int:
        result = self._alu.perform(opcode, left, right)
        self._flags = result.flags
        self._alu_out = result.value
        return result.value

    def is_alu_binary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.BINARY_OPERATIONS.keys()

    def is_alu_unary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.UNARY_OPERATIONS.keys()

    def push(self, mux: DStackMux) -> None:
        value = self._select_d_stack_source(mux)
        self.stack.push(value)
        self._flags = Flag.nz(value)

    def push_raw(self, mux: DStackMux) -> None:
        self.stack.push(self._select_d_stack_source(mux))

    def _select_d_stack_source(self, mux: DStackMux) -> int:
        match mux:
            case DStackMux.IR_OPERAND:
                return self._ir_operand_in
            case DStackMux.TOS:
                return self.stack.tos
            case DStackMux.NOS:
                return self.stack.nos
            case DStackMux.ALU:
                return self._alu_out
            case DStackMux.MEMORY:
                return self._mem_out
            case DStackMux.R_STACK:
                return self._r_top_in

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
            value = device.read()
        else:
            value = self.memory.read(self._ar)
        self._mem_out = value
        return value
