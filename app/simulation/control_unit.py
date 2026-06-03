from dataclasses import dataclass
from typing import Never

from app.isa.flag import Flag, ProgramState
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.isa.state import State
from app.simulation.data_path import DataPath
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DStackMux, PCMux, RStackMux
from app.simulation.stack import Stack


@dataclass(frozen=True)
class CUSnapshot:
    state: State
    tick: int
    pc: int
    instruction: Instruction
    flags: Flag

    ar: int

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
        self._step = 0

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
    def current_state(self) -> State:
        return self._state

    @property
    def current_step(self) -> int:
        return self._step

    @property
    def snapshot(self) -> CUSnapshot:
        return CUSnapshot(
            state=self._state,
            tick=self._tick,
            pc=self._pc,
            instruction=self._instr,
            flags=self.data_path.flags,
            ar=self.data_path._ar,
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
                if self._pending_vector is None:
                    msg = "Interrupt vector latch requested without pending vector"
                    raise RuntimeError(msg)
                self._pc = self._vector_table[self._pending_vector]
            case PCMux.R_STACK:
                self._pc = self._return_stack.pop()

    def write_r_stack(self, mux: RStackMux) -> None:
        match mux:
            case RStackMux.PC:
                value = self._pc
            case RStackMux.TOS:
                value = self.data_path.stack.tos
            case RStackMux.FLAGS:
                value = int(self.data_path.flags)
            case RStackMux.ALU:
                value = self.data_path._alu_out
        self._return_stack.push(value)

    def tick(self) -> None:
        self._tick += 1

        match self._state:
            case State.START:
                self._apply_state(self.decode_start_signals())
            case State.FETCH:
                self._apply_state(self.decode_fetch_signals())
            case State.INTERRUPT:
                self.decode_interrupt_signals()
            case State.EXECUTE:
                self.decode_execute_signals()
            case State.DONE:
                self._apply_state(State.START)
            case State.HALT:
                return

    def decode_start_signals(self) -> State:
        if ProgramState.IRQ not in self._program_state:
            for dev in self.data_path.io_map.values():
                vec = dev.tick(self._tick)
                if vec is not None and ProgramState.IE in self._program_state:
                    self._pending_vector = vec
                    self._program_state |= ProgramState.IRQ
                    break

        if ProgramState.IRQ in self._program_state:
            return State.INTERRUPT

        return State.FETCH

    def decode_fetch_signals(self) -> State:
        self._ir = self._instr_memory.read(self._pc)
        self.latch_pc(PCMux.NEXT)
        self._instr = Instruction.from_binary(self._ir)
        self.data_path.set_ir_operand(self._instr.operand)
        return State.EXECUTE

    def decode_interrupt_signals(self) -> None:
        match self._step:
            case 0:
                self.write_r_stack(RStackMux.FLAGS)
                self._advance_step()
            case 1:
                self.write_r_stack(RStackMux.PC)
                self._advance_step()
            case 2:
                self._program_state &= ~ProgramState.IE
                self._advance_step()
            case 3:
                self._program_state &= ~ProgramState.IRQ
                self._advance_step()
            case 4:
                self.latch_pc(PCMux.VECTOR)
                self._pending_vector = None
                self._apply_state(State.START)
            case _:
                self._invalid_step()

    def decode_execute_signals(self) -> None:
        opcode = self._instr.opcode

        if opcode is Opcode.HALT:
            self._apply_state(State.HALT)
            return

        if opcode in _ONE_CYCLE_OPCODES:
            self._execute_one_cycle(opcode)
            self._complete_instruction()
            return

        match opcode:
            case Opcode.CALL:
                self._execute_call()
            case Opcode.PSHR:
                self._execute_pshr()
            case Opcode.POPR:
                self._execute_popr()
            case Opcode.LOAD:
                self._execute_load()
            case Opcode.STORE:
                self._execute_store()
            case Opcode.LOADI:
                self._execute_loadi()
            case Opcode.STOREI:
                self._execute_storei()
            case Opcode.RTI:
                self._execute_rti()
            case _:
                msg = f"Unsupported opcode: {opcode.name}"
                raise NotImplementedError(msg)

    def _execute_one_cycle(self, opcode: Opcode) -> None:
        if self._step != 0:
            self._invalid_step()

        if opcode is Opcode.NOP:
            return

        if opcode in _BRANCH_OPCODES:
            self.execute_branch(self._branch_condition(opcode))
            return

        match opcode:
            case Opcode.PUSH:
                self.data_path.push(DStackMux.IR_OPERAND)
            case Opcode.DUP:
                self.data_path.push(DStackMux.TOS)
            case Opcode.DROP:
                self.data_path.pop_raw()
            case Opcode.SWAP:
                self._swap_data_stack_top()
            case Opcode.OVER:
                self.data_path.push(DStackMux.NOS)
            case Opcode.RET:
                self.latch_pc(PCMux.R_STACK)
            case Opcode.LOOP:
                self._execute_loop()
            case Opcode.EI:
                self._program_state |= ProgramState.IE
            case Opcode.DI:
                self._program_state &= ~ProgramState.IE
            case Opcode.CMP:
                self.data_path.cmp()
            case _ if self.data_path.is_alu_binary_opcode(opcode):
                right = self.data_path.pop_raw()
                left = self.data_path.pop_raw()
                self.data_path.perform_alu(opcode=opcode, left=left, right=right)
                self.data_path.push_raw(DStackMux.ALU)
            case _ if self.data_path.is_alu_unary_opcode(opcode):
                self.data_path.perform_alu(opcode=opcode, left=self.data_path.pop_raw())
                self.data_path.push_raw(DStackMux.ALU)
            case _:
                msg = f"Unsupported one-cycle opcode: {opcode.name}"
                raise NotImplementedError(msg)

    def _execute_call(self) -> None:
        match self._step:
            case 0:
                self.write_r_stack(RStackMux.PC)
                self._advance_step()
            case 1:
                self.latch_pc(PCMux.ADDRESS)
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_pshr(self) -> None:
        match self._step:
            case 0:
                self.write_r_stack(RStackMux.TOS)
                self.data_path.pop()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_popr(self) -> None:
        match self._step:
            case 0:
                self.data_path.set_r_top(self._return_stack.tos)
                self.data_path.push(DStackMux.R_STACK)
                self._return_stack.pop()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_load(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.IR_OPERAND)
                self._advance_step()
            case 1:
                self.data_path.read()
                self.data_path.push_raw(DStackMux.MEMORY)
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_store(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.IR_OPERAND)
                self._advance_step()
            case 1:
                self.data_path.write(self.data_path.stack.tos)
                self.data_path.pop_raw()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_loadi(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.data_path.pop_raw()
                self._advance_step()
            case 1:
                self.data_path.read()
                self.data_path.push(DStackMux.MEMORY)
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_storei(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.data_path.pop_raw()
                self._advance_step()
            case 1:
                self.data_path.write(self.data_path.stack.tos)
                self.data_path.pop_raw()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_rti(self) -> None:
        match self._step:
            case 0:
                self.latch_pc(PCMux.R_STACK)
                self._advance_step()
            case 1:
                self.data_path.flags = self._return_stack.pop()
                self._advance_step()
            case 2:
                self._program_state |= ProgramState.IE
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_loop(self) -> None:
        popped = self._return_stack.pop()
        cnt = self.data_path.perform_alu(Opcode.DEC, popped)
        if cnt != 0:
            self.write_r_stack(RStackMux.ALU)
            self.latch_pc(PCMux.ADDRESS)

    def _swap_data_stack_top(self) -> None:
        stack = self.data_path.stack
        tos_idx = stack.sp - 1
        nos_idx = stack.sp - 2
        stack.stack[tos_idx], stack.stack[nos_idx] = stack.stack[nos_idx], stack.stack[tos_idx]
        self.data_path.flags = Flag.nz(stack.tos)

    def execute_branch(self, condition: bool) -> None:
        if condition:
            self.latch_pc(PCMux.ADDRESS)

    def _branch_condition(self, opcode: Opcode) -> bool:
        flags = self.data_path.flags
        match opcode:
            case Opcode.JMP:
                return True
            case Opcode.JZ:
                return flags.has(Flag.Z)
            case Opcode.JNZ:
                return not flags.has(Flag.Z)
            case Opcode.JPL:
                return not flags.has(Flag.N)
            case Opcode.JMI:
                return flags.has(Flag.N)
            case Opcode.JGE:
                return flags.has(Flag.N) == flags.has(Flag.V)
            case Opcode.JL:
                return flags.has(Flag.N) != flags.has(Flag.V)
            case Opcode.JG:
                return not flags.has(Flag.Z) and flags.has(Flag.N) == flags.has(Flag.V)
            case Opcode.JLE:
                return flags.has(Flag.Z) or flags.has(Flag.N) != flags.has(Flag.V)
            case Opcode.JC:
                return flags.has(Flag.C)
            case Opcode.JNC:
                return not flags.has(Flag.C)
            case Opcode.JV:
                return flags.has(Flag.V)
            case Opcode.JNV:
                return not flags.has(Flag.V)
            case _:
                msg = f"{opcode.name} is not a branch opcode"
                raise ValueError(msg)

    def _apply_state(self, state: State) -> None:
        self._state = state
        self._step = 0

    def _advance_step(self) -> None:
        self._step += 1

    def _complete_instruction(self) -> None:
        self._apply_state(State.DONE)

    def _invalid_step(self) -> Never:
        msg = f"Invalid {self._state.name} step {self._step} for {self._instr.opcode.name}"
        raise RuntimeError(msg)


_BRANCH_OPCODES = {
    Opcode.JMP,
    Opcode.JZ,
    Opcode.JNZ,
    Opcode.JPL,
    Opcode.JMI,
    Opcode.JGE,
    Opcode.JL,
    Opcode.JG,
    Opcode.JLE,
    Opcode.JC,
    Opcode.JNC,
    Opcode.JV,
    Opcode.JNV,
}

_ONE_CYCLE_OPCODES = {
    Opcode.NOP,
    Opcode.PUSH,
    Opcode.DUP,
    Opcode.DROP,
    Opcode.SWAP,
    Opcode.OVER,
    Opcode.RET,
    Opcode.LOOP,
    Opcode.EI,
    Opcode.DI,
    Opcode.ADD,
    Opcode.SUB,
    Opcode.MUL,
    Opcode.DIV,
    Opcode.CMP,
    Opcode.INC,
    Opcode.DEC,
    Opcode.NEG,
    Opcode.AND,
    Opcode.OR,
    Opcode.XOR,
    Opcode.NOT,
    Opcode.SHL,
    Opcode.SHR,
    *_BRANCH_OPCODES,
}
