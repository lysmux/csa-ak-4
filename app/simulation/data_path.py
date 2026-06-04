from app.isa.flag import Flag
from app.isa.opcode import Opcode
from app.simulation.alu import Alu
from app.simulation.io import Device
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DSPMux, DStackMux
from app.simulation.stack import Stack


def stack_push(stack: Stack, value: int) -> None:
    if stack.sp >= 2:
        stack.write_mem(stack.sp - 2, stack.nos)
    stack.nos = stack.tos if stack.sp >= 1 else 0
    stack.tos = value
    stack.latch_sp(DSPMux.INC)


def stack_pop_addr(stack: Stack) -> int:
    """Synchronous read, address phase: drop the top cell and present the fill address.

    Returns the popped value (the old TOS). NOS still holds stale data until the
    data phase latches the refilled value.
    """
    value = stack.tos
    stack.latch_sp(DSPMux.DEC)
    stack.tos = stack.nos if stack.sp >= 1 else 0
    return value


def stack_pop_data(stack: Stack) -> None:
    """Synchronous read, data phase: latch the refilled NOS from stack memory."""
    stack.nos = stack.read_mem(stack.sp - 2) if stack.sp >= 2 else 0


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

    def perform_alu(self, opcode: Opcode, left: int, right: int = 0, carry_in: int = 0) -> int:
        result = self._alu.perform(opcode, left, right, carry_in)
        self._flags = result.flags
        self._alu_out = result.value
        return result.value

    def is_alu_binary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.BINARY_OPERATIONS.keys()

    def is_alu_unary_opcode(self, opcode: Opcode) -> bool:
        return opcode in self._alu.UNARY_OPERATIONS.keys()

    def push(self, mux: DStackMux) -> None:
        value = self._select_d_stack_source(mux)
        stack_push(self.stack, value)
        self._flags = Flag.nz(value)

    def push_raw(self, mux: DStackMux) -> None:
        stack_push(self.stack, self._select_d_stack_source(mux))

    def pop_addr(self) -> int:
        return stack_pop_addr(self.stack)

    def pop_data(self) -> None:
        stack_pop_data(self.stack)

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
