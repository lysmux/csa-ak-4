import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.isa.consts import MAX_SIGNED, MIN_SIGNED, WORD_MASK
from app.isa.flag import Flag, ProgramState
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.isa.state import State
from app.simulation.alu import _signed
from app.simulation.data_path import DataPath
from app.simulation.memory import Memory
from app.simulation.mux import PCMux, RStackMux
from app.simulation.stack import Stack

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CUSnapshot:
    state: State
    tick: int
    pc: int
    instruction: Instruction
    flags: Flag

    ar: int
    dr: int

    data_memory: list[int]
    instr_memory: list[int]

    data_stack: list[int]
    tos: int
    nos: int

    return_stack: list[int]
    r_tos: int


class ControlUnit:
    def __init__(
        self,
        data_path: DataPath,
        instr_memory: Memory,
        return_stack: Stack,
        vector_table: dict[int, int] | None = None,
    ) -> None:
        self.data_path = data_path
        self._instr_memory = instr_memory
        self._return_stack = return_stack

        self._vector_table: dict[int, int] = vector_table or {}

        self._pc = 0
        self._ir = 0
        self._program_state = ProgramState(0)
        self._pending_vector: int | None = None

        self._instr = Instruction(Opcode.HALT)
        self._state = State.START

        self._tick = 0

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def current_pc(self) -> int:
        return self._pc

    @property
    def current_instr(self) -> Instruction:
        return self._instr

    @property
    def snapshot(self) -> CUSnapshot:
        return CUSnapshot(
            state=self._state,
            tick=self._tick,
            pc=self._pc,
            instruction=self._instr,
            flags=self.data_path.flags,
            ar=self.data_path._ar,
            dr=self.data_path._dr,
            data_memory=self.data_path.memory._memory,
            instr_memory=self._instr_memory._memory,
            data_stack=self.data_path.stack.stack,
            tos=self.data_path.stack.tos,
            nos=self.data_path.stack.nos,
            return_stack=self._return_stack.stack,
            r_tos=self._return_stack.tos,
        )

    def latch_pc(self, mux: PCMux) -> None:
        match mux:
            case PCMux.NEXT:
                self._pc += 1
            case PCMux.ADDRESS:
                self._pc = self._instr.operand
            case PCMux.VECTOR:
                self._pc = self._vector_table[0]
            case PCMux.R_STACK:
                self._pc = self._return_stack.pop()

    def write_r_stack(self, mux: RStackMux) -> None:
        value = 0
        match mux:
            case RStackMux.PC:
                value = self._pc
            case RStackMux.ALU:
                value = 0
        self._return_stack.push(value)

    def tick(self) -> None:
        self._tick += 1

        match self._state:
            case State.START:
                if ProgramState.IRQ not in self._program_state:
                    for dev in self.data_path.io_map.values():
                        vec = dev.tick(self._tick)
                        if vec is not None and ProgramState.IE in self._program_state:
                            self._pending_vector = vec
                            self._program_state |= ProgramState.IRQ
                            break
                if ProgramState.IRQ in self._program_state:
                    self._state = State.INTERRUPT
                    self.execute_interrupt()
                else:
                    self._state = State.FETCH
                    self.fetch()
            case State.EXECUTE:
                self.execute_step()

    def fetch(self) -> None:
        self._ir = self._instr_memory.read(self._pc)
        self.latch_pc(PCMux.NEXT)

        self._instr = Instruction.from_binary(self._ir)
        self._state = State.EXECUTE

    def execute_step(self) -> None:
        if self._instr.opcode is Opcode.HALT:
            self._state = State.HALT
            return

        if self._instr.opcode is Opcode.JMP:
            self.execute_branch(True)
        if self._instr.opcode is Opcode.JZ:
            self.execute_branch(self.data_path.flags.has(Flag.Z))
        if self._instr.opcode is Opcode.JNZ:
            self.execute_branch(not self.data_path.flags.has(Flag.Z))
        if self._instr.opcode is Opcode.JPL:
            self.execute_branch(not self.data_path.flags.has(Flag.N))
        if self._instr.opcode is Opcode.JMI:
            self.execute_branch(self.data_path.flags.has(Flag.N))
        if self._instr.opcode is Opcode.JGE:
            self.execute_branch(self.data_path.flags.has(Flag.N) == self.data_path.flags.has(Flag.V))
        if self._instr.opcode is Opcode.JG:
            n = Flag.N in self.data_path.flags
            v = Flag.V in self.data_path.flags
            self.execute_branch(Flag.Z not in self.data_path.flags and n == v)
        if self._instr.opcode is Opcode.JLE:
            n = Flag.N & self.data_path.flags
            v = Flag.V & self.data_path.flags
            self.execute_branch(bool(Flag.Z & self.data_path.flags) or n != v)
        if self._instr.opcode is Opcode.JL:
            self.execute_branch(self.data_path.flags.has(Flag.N) != self.data_path.flags.has(Flag.V))
        if self._instr.opcode is Opcode.JC:
            self.execute_branch(self.data_path.flags.has(Flag.C))
        if self._instr.opcode is Opcode.JNC:
            self.execute_branch(not self.data_path.flags.has(Flag.C))
        if self._instr.opcode is Opcode.JV:
            self.execute_branch(self.data_path.flags.has(Flag.V))
        if self._instr.opcode is Opcode.JNV:
            self.execute_branch(not self.data_path.flags.has(Flag.V))

        if self._instr.opcode is Opcode.LOAD:
            self.data_path.stack.push(self.data_path.read(self._instr.operand))
        if self._instr.opcode is Opcode.STORE:
            self.data_path.write(self._instr.operand, self.data_path.stack.pop())
        if self._instr.opcode is Opcode.LOADI:
            self.data_path.push(self.data_path.read(self.data_path.pop()))
        if self._instr.opcode is Opcode.STOREI:
            self.data_path.write(self.data_path.pop(), self.data_path.pop())

        if self._instr.opcode is Opcode.PUSH:
            self.data_path.push(self._instr.operand)
        if self._instr.opcode is Opcode.DUP:
            self.data_path.push(self.data_path.stack.tos)
        if self._instr.opcode is Opcode.DROP:
            self.data_path.stack.pop()
        if self._instr.opcode is Opcode.SWAP:
            tos = self.data_path.pop()
            nos = self.data_path.pop()
            self.data_path.push(tos)
            self.data_path.push(nos)
        if self._instr.opcode is Opcode.OVER:
            self.data_path.push(self.data_path.stack.nos)

        if self._instr.opcode is Opcode.CALL:
            self.write_r_stack(RStackMux.PC)
            self.latch_pc(PCMux.ADDRESS)
        if self._instr.opcode is Opcode.RET:
            self.latch_pc(PCMux.R_STACK)
        if self._instr.opcode is Opcode.PSHR:
            self._return_stack.push(self.data_path.pop())
        if self._instr.opcode is Opcode.POPR:
            self.data_path.stack.push(self._return_stack.pop())
        if self._instr.opcode is Opcode.LOOP:
            cnt = self._return_stack.stack.pop()
            cnt -= 1
            self._return_stack.push(cnt)

            if cnt != 0:
                self.latch_pc(PCMux.ADDRESS)

        if self._instr.opcode is Opcode.EI:
            self._program_state |= ProgramState.IE
        if self._instr.opcode is Opcode.DI:
            self._program_state &= ~ProgramState.IE
        if self._instr.opcode is Opcode.RTI:
            self._pc = self._return_stack.pop()
            self.data_path.flags = self._return_stack.pop()
            self._program_state |= ProgramState.IE

        if self._instr.opcode is Opcode.ADDC:
            right = self.data_path.stack.pop()
            left = self.data_path.stack.pop()
            carry = 1 if Flag.C in self.data_path.flags else 0
            raw = left + right + carry
            value = raw & WORD_MASK
            flags = Flag.nz(value)
            if raw > WORD_MASK:
                flags |= Flag.C
            if (
                _signed(left) + _signed(right) + carry > MAX_SIGNED
                or _signed(left) + _signed(right) + carry < MIN_SIGNED
            ):
                flags |= Flag.V
            self.data_path.flags = flags
            self.data_path.stack.push(value)

        if self._instr.opcode is Opcode.CMP:
            self.data_path.cmp()

        if self.data_path.is_alu_binary_opcode(self._instr.opcode):
            right = self.data_path.stack.pop()
            left = self.data_path.stack.pop()
            result = self.data_path.perform_alu(
                opcode=self._instr.opcode,
                left=left,
                right=right,
            )
            self.data_path.stack.push(result)

        if self.data_path.is_alu_unary_opcode(self._instr.opcode):
            result = self.data_path.perform_alu(opcode=self._instr.opcode, left=self.data_path.stack.pop())
            self.data_path.stack.push(result)

        self._state = State.START

    def execute_interrupt(self) -> None:
        self._return_stack.push(int(self.data_path.flags))
        self._return_stack.push(self._pc)
        self._program_state &= ~ProgramState.IE
        self._program_state &= ~ProgramState.IRQ
        self._pc = self._vector_table[self._pending_vector]
        self._pending_vector = None
        self._state = State.START

    def execute_branch(self, condition: bool) -> None:
        if not condition:
            return

        self.latch_pc(PCMux.ADDRESS)

    def run(
        self,
        limit: int | None = None,
        on_tick: "Callable[[ControlUnit], None] | None" = None,
    ) -> None:
        while self._state is not State.HALT:
            if limit is not None and self._tick >= limit:
                logger.warning("Tick limit %d reached, halting", limit)
                return
            self.tick()
            if on_tick is not None:
                on_tick(self)
