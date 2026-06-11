from dataclasses import dataclass
from typing import Never

from app.isa.consts import INSTR_BYTES
from app.isa.flag import Flag
from app.isa.instruction import Instruction
from app.isa.opcode import BRANCH_OPCODES, ONE_CYCLE_OPCODES, Opcode
from app.isa.state import State
from app.simulation.data_path import DataPath
from app.simulation.memory import Memory
from app.simulation.mux import ARMux, DSPMux, NosMux, PCMux, RSPMux, RStackMux, TosMux
from app.simulation.stack import ReturnStack


@dataclass(frozen=True)
class CUSnapshot:
    state: State
    tick: int

    pc: int
    instruction: Instruction

    flags: Flag
    ar: int

    data_stack: list[int]
    tos: int
    nos: int

    return_stack: list[int]
    r_tos: int

    data_memory: bytearray
    instr_memory: bytearray


class ControlUnit:
    def __init__(
        self,
        data_path: DataPath,
        instr_memory: Memory,
        return_stack: ReturnStack,
        vector_table: dict[int, int] | None = None,
    ) -> None:
        self.data_path = data_path
        self.instr_memory = instr_memory
        self.return_stack = return_stack

        self._vector_table: dict[int, int] = vector_table or {}

        self._state = State.FETCH
        self._step = 0
        self._tick = 0

        self._pc = 0
        self._ir = 0
        self._instr = Instruction(Opcode.HALT)

        self._alu_l_buff = 0
        self._alu_r_buff = 0
        self._loop_cnt = 0

        self._pending_vector: int | None = None
        self._irq = False
        self._ie = False

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def current_state(self) -> State:
        return self._state

    @property
    def snapshot(self) -> CUSnapshot:
        return CUSnapshot(
            state=self._state,
            tick=self._tick,
            pc=self._pc,
            instruction=self._instr,
            flags=self.data_path.flags,
            ar=self.data_path.ar,
            data_stack=list(self.data_path.stack.stack),
            tos=self.data_path.stack.tos,
            nos=self.data_path.stack.nos,
            return_stack=list(self.return_stack.stack),
            r_tos=self.return_stack.read(),
            data_memory=bytearray(self.data_path.memory.memory),
            instr_memory=bytearray(self.instr_memory.memory),
        )

    def tick(self) -> None:
        self._tick += 1

        self._irq = False
        self._pending_vector = None
        for dev in self.data_path.io_map.values():
            vec = dev.tick(self._tick)
            if vec is not None:
                self._pending_vector = vec
                self._irq = True
                break

        match self._state:
            case State.FETCH:
                self.decode_fetch_signals()
            case State.INTERRUPT:
                self.decode_interrupt_signals()
            case State.EXECUTE:
                self.decode_execute_signals()
            case State.CHECK_IRQ:
                self.decode_check_irq_signals()
            case State.HALT:
                return

    def decode_check_irq_signals(self) -> None:
        if self._irq:
            self.apply_state(State.INTERRUPT)
        else:
            self.apply_state(State.FETCH)

    def decode_fetch_signals(self) -> None:
        self._ir = self.instr_memory.read(self._pc)
        self._instr = Instruction.from_binary(self._ir)
        self.data_path.set_operand(self._instr.operand)
        self.latch_pc(PCMux.NEXT)
        self.apply_state(State.EXECUTE)

    def decode_interrupt_signals(self) -> None:
        match self._step:
            case 0:
                self._ie = False
                self.write_r_stack(RStackMux.FLAGS)
                self.advance_step()
            case 1:
                self.write_r_stack(RStackMux.PC)
                self.advance_step()
            case 2:
                self.latch_pc(PCMux.VECTOR)
                self.apply_state(State.FETCH)
            case _:
                self._invalid_step()

    def decode_execute_signals(self) -> None:
        opcode = self._instr.opcode

        if opcode is Opcode.HALT:
            self.apply_state(State.HALT)
            return

        if opcode in ONE_CYCLE_OPCODES:
            self._execute_one_cycle(opcode)
            self.complete_instruction()
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
        if opcode is Opcode.NOP:
            return

        if opcode in BRANCH_OPCODES:
            self.execute_branch(self.branch_condition(opcode))
            return

        match opcode:
            case Opcode.PUSH:
                self.data_path.push(TosMux.OPERAND)
            case Opcode.DUP:
                self.data_path.dup()
            case Opcode.SWAP:
                stack = self.data_path.stack
                stack.tos, stack.nos = stack.nos, stack.tos
                self.data_path.flags = Flag.nz(stack.tos)
            case Opcode.OVER:
                self.data_path.push(TosMux.NOS)
            case Opcode.EI:
                self._ie = True
            case Opcode.DI:
                self._ie = False
            case Opcode.CMP:
                self.data_path.cmp()
            case Opcode.I2L:
                self.data_path.perform_alu(opcode=Opcode.I2L, left=self.data_path.stack.tos)
                self.data_path.push(TosMux.ALU)
            case _ if self.data_path.is_alu_unary_opcode(opcode):
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
                self.latch_pc(PCMux.OPERAND)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_pshr(self) -> None:
        match self._step:
            case 0:
                self.write_r_stack(RStackMux.TOS)
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.pop()
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_popr(self) -> None:
        match self._step:
            case 0:
                self.return_stack.latch_sp(RSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.set_r_top(self.return_stack.read())
                self.data_path.push(TosMux.R_STACK)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_load(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.OPERAND)
                self.advance_step()
            case 1:
                self.data_path.read()
                self.data_path.push(TosMux.MEMORY)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_store(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.OPERAND)
                self.advance_step()
            case 1:
                self.data_path.write(self.data_path.stack.tos)
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 2:
                self.data_path.pop()
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_loadi(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.advance_step()
            case 1:
                self.data_path.read()
                self.data_path.latch_tos(TosMux.MEMORY)
                self.data_path.set_nz_from_tos()
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_storei(self) -> None:
        match self._step:
            case 0:
                self.data_path.latch_ar(ARMux.TOS)
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.pop()
                self.advance_step()
            case 2:
                self.data_path.write(self.data_path.stack.tos)
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 3:
                self.data_path.pop()
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_drop(self) -> None:
        match self._step:
            case 0:
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.pop()
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_ret(self) -> None:
        match self._step:
            case 0:
                self.return_stack.latch_sp(RSPMux.DEC)
                self.advance_step()
            case 1:
                self.latch_pc(PCMux.R_STACK)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_binary(self, *, carry: bool = False) -> None:
        match self._step:
            case 0:
                opcode = Opcode.ADD if carry else self._instr.opcode
                carry_in = int(self.data_path.flags.has(Flag.C)) if carry else 0
                self.data_path.perform_alu(
                    opcode=opcode,
                    left=self.data_path.stack.nos,
                    right=self.data_path.stack.tos,
                    carry_in=carry_in,
                )
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.latch_tos(TosMux.ALU)
                self.data_path.latch_nos(NosMux.D_STACK)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_rti(self) -> None:
        match self._step:
            case 0:
                self.return_stack.latch_sp(RSPMux.DEC)
                self.advance_step()
            case 1:
                self.latch_pc(PCMux.R_STACK)
                self.return_stack.latch_sp(RSPMux.DEC)
                self.advance_step()
            case 2:
                self.data_path.flags = self.return_stack.read()
                self.advance_step()
            case 3:
                self._ie = True
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_loop(self) -> None:
        match self._step:
            case 0:
                self.return_stack.latch_sp(RSPMux.DEC)
                self.advance_step()
            case 1:
                self._loop_cnt = self.data_path.perform_alu(Opcode.DEC, self.return_stack.read())
                self.advance_step()
            case 2:
                if self._loop_cnt != 0:
                    self.write_r_stack(RStackMux.ALU)
                    self.latch_pc(PCMux.OPERAND)
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_dadd(self) -> None:
        match self._step:
            case 0:
                self._alu_l_buff = self.data_path.stack.tos
                self._alu_r_buff = self.data_path.stack.nos

                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.pop()
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 2:
                self.data_path.pop()
                self.data_path.perform_alu(
                    opcode=Opcode.ADD,
                    left=self.data_path.stack.nos,
                    right=self._alu_r_buff,
                )
                self.data_path.latch_nos(NosMux.ALU)
                self.advance_step()
            case 3:
                carry_in = int(self.data_path.flags.has(Flag.C))
                rlo = self.data_path.stack.nos
                self.data_path.perform_alu(
                    opcode=Opcode.ADD,
                    left=self.data_path.stack.tos,
                    right=self._alu_l_buff,
                    carry_in=carry_in,
                )
                self.data_path.latch_tos(TosMux.ALU)
                if rlo != 0:
                    self.data_path.flags = self.data_path.flags & ~Flag.Z
                self.complete_instruction()
            case _:
                self._invalid_step()

    def _execute_dsub(self) -> None:
        match self._step:
            case 0:
                self._alu_l_buff = self.data_path.stack.tos
                self._alu_r_buff = self.data_path.stack.nos

                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 1:
                self.data_path.pop()
                self.data_path.stack.latch_sp(DSPMux.DEC)
                self.advance_step()
            case 2:
                self.data_path.pop()
                self.data_path.perform_alu(
                    opcode=Opcode.SUB,
                    left=self.data_path.stack.nos,
                    right=self._alu_r_buff,
                )
                self.data_path.latch_nos(NosMux.ALU)
                self.advance_step()
            case 3:
                borrow = int(self.data_path.flags.has(Flag.C))
                rlo = self.data_path.stack.nos
                self.data_path.perform_alu(
                    opcode=Opcode.SUB,
                    left=self.data_path.stack.tos,
                    right=self._alu_l_buff,
                    carry_in=-borrow,
                )
                self.data_path.latch_tos(TosMux.ALU)
                if rlo != 0:
                    self.data_path.flags = self.data_path.flags & ~Flag.Z
                self.complete_instruction()
            case _:
                self._invalid_step()

    def execute_branch(self, condition: bool) -> None:
        if condition:
            self.latch_pc(PCMux.OPERAND)

    def branch_condition(self, opcode: Opcode) -> bool:
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

    def latch_pc(self, mux: PCMux) -> None:
        match mux:
            case PCMux.NEXT:
                self._pc += INSTR_BYTES
            case PCMux.OPERAND:
                self._pc = self._instr.operand
            case PCMux.R_STACK:
                self._pc = self.return_stack.read()
            case PCMux.VECTOR:
                if self._pending_vector is None:
                    msg = "Interrupt vector latch requested without pending vector"
                    raise RuntimeError(msg)
                try:
                    self._pc = self._vector_table[self._pending_vector]
                except KeyError as error:
                    msg = f"Unknown interrupt vector: {self._pending_vector}"
                    raise RuntimeError(msg) from error

    def write_r_stack(self, mux: RStackMux) -> None:
        match mux:
            case RStackMux.PC:
                value = self._pc
            case RStackMux.TOS:
                value = self.data_path.stack.tos
            case RStackMux.FLAGS:
                value = int(self.data_path.flags)
            case RStackMux.ALU:
                value = self.data_path.alu_out

        self.return_stack.write(value)
        self.return_stack.latch_sp(RSPMux.INC)

    def apply_state(self, state: State) -> None:
        self._state = state
        self._step = 0

    def advance_step(self) -> None:
        self._step += 1

    def complete_instruction(self) -> None:
        if self._ie:
            self.apply_state(State.CHECK_IRQ)
        else:
            self.apply_state(State.FETCH)

    def _invalid_step(self) -> Never:
        msg = f"Invalid {self._state.name} step {self._step} for {self._instr.opcode.name}"
        raise RuntimeError(msg)
