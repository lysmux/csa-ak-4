from dataclasses import dataclass
from typing import Never

from app.isa.flag import Flag, ProgramState
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.isa.state import State
from app.simulation.alu import dword_div, dword_mul
from app.simulation.data_path import DataPath, stack_pop_addr, stack_pop_data, stack_push
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DSPMux, DStackMux, PCMux, RStackMux
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

        self._alu_l_buff = 0
        self._alu_r_buff = 0
        self._loop_cnt = 0

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
        self._r_push(value)

    def _r_push(self, value: int) -> None:
        stack_push(self._return_stack, value)

    def _r_pop_addr(self) -> int:
        return stack_pop_addr(self._return_stack)

    def _r_pop_data(self) -> None:
        stack_pop_data(self._return_stack)

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
            case Opcode.DADD:
                self._execute_dadd()
            case Opcode.DSUB:
                self._execute_dsub()
            case Opcode.DMUL:
                self._execute_dmul()
            case Opcode.DDIV:
                self._execute_ddiv()
            case Opcode.DROP:
                self._execute_drop()
            case Opcode.RET:
                self._execute_ret()
            case Opcode.LOOP:
                self._execute_loop()
            case Opcode.ADDC:
                self._execute_binary(carry=True)
            case _ if self.data_path.is_alu_binary_opcode(opcode):
                self._execute_binary()
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
            case Opcode.SWAP:
                self._swap_data_stack_top()
            case Opcode.OVER:
                self.data_path.push(DStackMux.NOS)
            case Opcode.EI:
                self._program_state |= ProgramState.IE
            case Opcode.DI:
                self._program_state &= ~ProgramState.IE
            case Opcode.CMP:
                self.data_path.cmp()
            case _ if self.data_path.is_alu_unary_opcode(opcode):
                # ALU reads TOS directly and writes the result back in place — no memory.
                self.data_path.stack.tos = self.data_path.perform_alu(
                    opcode=opcode,
                    left=self.data_path.stack.tos,
                )
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
                self.data_path.pop_addr()
                self._advance_step()
            case 1:
                self.data_path.pop_data()
                self.data_path.set_nz_from_tos()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_popr(self) -> None:
        match self._step:
            case 0:
                self.data_path.set_r_top(self._return_stack.tos)
                self.data_path.push(DStackMux.R_STACK)
                self._r_pop_addr()
                self._advance_step()
            case 1:
                self._r_pop_data()
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
                self.data_path.pop_addr()
                self._advance_step()
            case 2:
                self.data_path.pop_data()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_loadi(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.data_path.pop_addr()
                self._advance_step()
            case 1:
                self.data_path.pop_data()
                self._advance_step()
            case 2:
                self.data_path.read()
                self.data_path.push(DStackMux.MEMORY)
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_storei(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.data_path.pop_addr()
                self._advance_step()
            case 1:
                self.data_path.pop_data()
                self._advance_step()
            case 2:
                self.data_path.write(self.data_path.stack.tos)
                self.data_path.pop_addr()
                self._advance_step()
            case 3:
                self.data_path.pop_data()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_drop(self) -> None:
        match self._step:
            case 0:
                self.data_path.pop_addr()
                self._advance_step()
            case 1:
                self.data_path.pop_data()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_ret(self) -> None:
        match self._step:
            case 0:
                self._pc = self._r_pop_addr()
                self._advance_step()
            case 1:
                self._r_pop_data()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_binary(self, *, carry: bool = False) -> None:
        # ALU operands are the TOS/NOS registers; the result replaces NOS-as-new-TOS,
        # then the new NOS is refilled from stack memory (a synchronous read).
        match self._step:
            case 0:
                opcode = Opcode.ADD if carry else self._instr.opcode
                carry_in = int(self.data_path.flags.has(Flag.C)) if carry else 0
                self.data_path.stack.tos = self.data_path.perform_alu(
                    opcode=opcode,
                    left=self.data_path.stack.nos,
                    right=self.data_path.stack.tos,
                    carry_in=carry_in,
                )
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self._advance_step()
            case 1:
                self.data_path.pop_data()
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_rti(self) -> None:
        match self._step:
            case 0:
                self._pc = self._r_pop_addr()
                self._advance_step()
            case 1:
                self._r_pop_data()
                self._advance_step()
            case 2:
                self.data_path.flags = self._r_pop_addr()
                self._advance_step()
            case 3:
                self._r_pop_data()
                self._advance_step()
            case 4:
                self._program_state |= ProgramState.IE
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _surface_a(self) -> bool:
        # Steps 0-3: lift operand B (Bhi:TOS, Blo:NOS) into the ALU buffers, then surface
        # operand A from stack memory with two synchronous fills (address tick + data tick).
        # Returns True while still surfacing; once it returns False, TOS=Ahi and NOS=Alo.
        match self._step:
            case 0:
                self._alu_l_buff = self.data_path.stack.tos  # Bhi
                self._alu_r_buff = self.data_path.stack.nos  # Blo
                self.data_path.pop_addr()
                self._advance_step()
                return True
            case 1:
                self.data_path.pop_data()
                self._advance_step()
                return True
            case 2:
                self.data_path.pop_addr()
                self._advance_step()
                return True
            case 3:
                self.data_path.pop_data()
                self._advance_step()
                return True
            case _:
                return False

    def _write_dword(self, value: int, flags: Flag) -> None:
        self.data_path.stack.tos = (value >> 32) & 0xFFFFFFFF
        self.data_path.stack.nos = value & 0xFFFFFFFF
        self.data_path.flags = flags

    def _execute_dadd(self) -> None:
        if self._surface_a():
            return
        match self._step:
            case 4:
                self.data_path.stack.nos = self.data_path.perform_alu(
                    opcode=Opcode.ADD,
                    left=self.data_path.stack.nos,
                    right=self._alu_r_buff,
                )
                self._advance_step()
            case 5:
                carry_in = int(self.data_path.flags.has(Flag.C))
                rlo = self.data_path.stack.nos
                self.data_path.stack.tos = self.data_path.perform_alu(
                    opcode=Opcode.ADD,
                    left=self.data_path.stack.tos,
                    right=self._alu_l_buff,
                    carry_in=carry_in,
                )
                if rlo != 0:
                    self.data_path.flags = self.data_path.flags & ~Flag.Z
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_dsub(self) -> None:
        if self._surface_a():
            return
        match self._step:
            case 4:
                self.data_path.stack.nos = self.data_path.perform_alu(
                    opcode=Opcode.SUB,
                    left=self.data_path.stack.nos,
                    right=self._alu_r_buff,
                )
                self._advance_step()
            case 5:
                borrow = int(self.data_path.flags.has(Flag.C))
                rlo = self.data_path.stack.nos
                self.data_path.stack.tos = self.data_path.perform_alu(
                    opcode=Opcode.SUB,
                    left=self.data_path.stack.tos,
                    right=self._alu_l_buff,
                    carry_in=-borrow,
                )
                if rlo != 0:
                    self.data_path.flags = self.data_path.flags & ~Flag.Z
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _execute_dmul(self) -> None:
        if self._surface_a():
            return
        a = (self.data_path.stack.tos << 32) | self.data_path.stack.nos
        b = (self._alu_l_buff << 32) | self._alu_r_buff
        value, flags = dword_mul(a, b)
        self._write_dword(value, flags)
        self._complete_instruction()

    def _execute_ddiv(self) -> None:
        if self._surface_a():
            return
        a = (self.data_path.stack.tos << 32) | self.data_path.stack.nos
        b = (self._alu_l_buff << 32) | self._alu_r_buff
        value, flags = dword_div(a, b)
        self._write_dword(value, flags)
        self._complete_instruction()

    def _execute_loop(self) -> None:
        match self._step:
            case 0:
                popped = self._r_pop_addr()
                self._loop_cnt = self.data_path.perform_alu(Opcode.DEC, popped)
                self._advance_step()
            case 1:
                self._r_pop_data()
                self._advance_step()
            case 2:
                if self._loop_cnt != 0:
                    self.write_r_stack(RStackMux.ALU)
                    self.latch_pc(PCMux.ADDRESS)
                self._complete_instruction()
            case _:
                self._invalid_step()

    def _swap_data_stack_top(self) -> None:
        stack = self.data_path.stack
        stack.tos, stack.nos = stack.nos, stack.tos
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
    Opcode.SWAP,
    Opcode.OVER,
    Opcode.EI,
    Opcode.DI,
    Opcode.CMP,
    Opcode.INC,
    Opcode.DEC,
    Opcode.NEG,
    Opcode.NOT,
    Opcode.SHL,
    Opcode.SHR,
    *_BRANCH_OPCODES,
}
