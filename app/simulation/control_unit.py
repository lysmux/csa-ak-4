from collections.abc import Generator
from dataclasses import dataclass

from app.isa.flags import Flags
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.isa.state import State
from app.simulation.data_path import DataPath
from app.simulation.decoder import EXECUTE_SIGNALS, MicroProgram, FETCH, FETCH_SIGNALS
from app.simulation.memory import Memory
from app.simulation.register import Register
from app.simulation.signal import Signal
from app.simulation.stack import Stack


@dataclass(frozen=True)
class CUSnapshot:
    state: State
    tick: int
    pc: int
    instruction: Instruction
    signals: set[Signal]

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
    ) -> None:
        self._data_path = data_path
        self._instr_memory = instr_memory
        self._return_stack = return_stack

        self._pc = Register()
        self._instr = Instruction(Opcode.HALT)
        self._state = State.HALT
        self._signals_seq: list[set[Signal]] = []
        self._signals: set[Signal] = set()
        self._tick = 0


    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def current_pc(self) -> int:
        return self._pc.current

    @property
    def current_instr(self) -> Instruction:
        return self._instr

    @property
    def snapshot(self) -> CUSnapshot:
        return CUSnapshot(
            state=self._state,
            tick=self._tick,
            pc=self._pc.current,
            instruction=self._instr,
            signals=self._signals,
            ar=self._data_path.memory.addr.current,
            dr=self._data_path._dr.current,
            data_memory=self._data_path.memory._memory,
            instr_memory=self._instr_memory._memory,
            data_stack=self._data_path._stack.stack,
            tos=self._data_path.tos,
            nos=self._data_path.nos,
            return_stack=self._return_stack.stack,
            r_tos=self._return_stack.tos.current
        )

    def tick(self) -> CUSnapshot:
        self._tick += 1

        match self._state:
            case State.FETCH:
                self._signals_seq = FETCH_SIGNALS
            case State.EXECUTE:
                self._signals_seq = EXECUTE_SIGNALS[self._instr.opcode]

        return self.snapshot

    # ── Обработка сигналов ───────────────────────────────────────────────────

    def process_signal(self, sig: Signal) -> None:
        dp = self._data_path

        match sig:
            # ── PC ───────────────────────────────────────────────────────────
            case Signal.PC_INC:
                self._pc.latch(self._pc.current + 1)
            case Signal.PC_LATCH_IMM:
                self._pc.latch(self._instr.operand)
            case Signal.PC_LATCH_RET:
                self._pc.latch(self._return_stack.pop())

            # ── Память команд ────────────────────────────────────────────────
            case Signal.IMEM_LATCH_PC:
                self._instr_memory.addr.latch(self._pc.current)
            case Signal.IMEM_READ:
                self._instr_memory.get_signal()
            case Signal.IR_LATCH:
                self._instr = Instruction.from_binary(self._instr_memory.out)

            # ── Память данных (адресация) ─────────────────────────────────────
            case Signal.DMEM_LATCH_IMM:
                dp.memory.addr.latch(self._instr.operand)
            case Signal.DMEM_LATCH_TOS:
                dp.memory.addr.latch(dp.tos)
            case Signal.DMEM_LATCH_A:
                dp.memory.addr.latch(dp.a)
            case Signal.DMEM_READ:
                dp.dmem_read()
            case Signal.DMEM_WRITE:
                dp.dmem_write()

            # ── Регистр DR ───────────────────────────────────────────────────
            case Signal.DR_LATCH_MEM:
                dp.dr_latch_mem()
            case Signal.DR_LATCH_TOS:
                dp.dr_latch_tos()

            # ── Стек данных ──────────────────────────────────────────────────
            case Signal.PUSH_DR:
                dp.push_dr()
            case Signal.PUSH_IMM:
                dp.push(self._instr.operand)
            case Signal.DROP:
                dp.pop()
            case Signal.DUP:
                dp.dup()
            case Signal.SWAP:
                dp.swap()
            case Signal.OVER:
                dp.over()

            # ── ALU binary ───────────────────────────────────────────────────
            case Signal.ALU_ADD:
                dp.alu_binary(Opcode.ADD)
            case Signal.ALU_SUB:
                dp.alu_binary(Opcode.SUB)
            case Signal.ALU_MUL:
                dp.alu_binary(Opcode.MUL)
            case Signal.ALU_DIV:
                dp.alu_binary(Opcode.DIV)
            case Signal.ALU_AND:
                dp.alu_binary(Opcode.AND)
            case Signal.ALU_OR:
                dp.alu_binary(Opcode.OR)
            case Signal.ALU_XOR:
                dp.alu_binary(Opcode.XOR)
            case Signal.ALU_CMP:
                dp.alu_cmp()

            # ── ALU unary ────────────────────────────────────────────────────
            case Signal.ALU_INC:
                dp.alu_unary(Opcode.INC)
            case Signal.ALU_DEC:
                dp.alu_unary(Opcode.DEC)
            case Signal.ALU_NEG:
                dp.alu_unary(Opcode.NEG)
            case Signal.ALU_NOT:
                dp.alu_unary(Opcode.NOT)
            case Signal.ALU_SHL:
                dp.alu_unary(Opcode.SHL)
            case Signal.ALU_SHR:
                dp.alu_unary(Opcode.SHR)

            # ── Условные переходы ────────────────────────────────────────────
            case Signal.JZ_BRANCH:
                if Flags.Z in dp.flags:
                    self._pc.latch(self._instr.operand)
            case Signal.JNZ_BRANCH:
                if Flags.Z not in dp.flags:
                    self._pc.latch(self._instr.operand)
            case Signal.JGE_BRANCH:
                if (Flags.N in dp.flags) == (Flags.V in dp.flags):
                    self._pc.latch(self._instr.operand)
            case Signal.JL_BRANCH:
                if (Flags.N in dp.flags) != (Flags.V in dp.flags):
                    self._pc.latch(self._instr.operand)
            case Signal.JG_BRANCH:
                if Flags.Z not in dp.flags and (Flags.N in dp.flags) == (Flags.V in dp.flags):
                    self._pc.latch(self._instr.operand)
            case Signal.JLE_BRANCH:
                if Flags.Z in dp.flags or (Flags.N in dp.flags) != (Flags.V in dp.flags):
                    self._pc.latch(self._instr.operand)
            case Signal.JC_BRANCH:
                if Flags.C in dp.flags:
                    self._pc.latch(self._instr.operand)
            case Signal.JNC_BRANCH:
                if Flags.C not in dp.flags:
                    self._pc.latch(self._instr.operand)

            # ── Стек возвратов ───────────────────────────────────────────────
            case Signal.RS_PUSH_PC:
                self._return_stack.push(self._pc.current)
            case Signal.RS_PUSH_FLAGS:
                self._return_stack.push(int(dp.flags))
            case Signal.RS_POP_PC:
                self._pc.latch(self._return_stack.pop())
            case Signal.RS_POP_FLAGS:
                dp.flags = self._return_stack.pop()
            case Signal.RS_PUSH_TOS:
                self._return_stack.push(dp.pop())
            case Signal.RS_POP_TOS:
                dp.push(self._return_stack.pop())
            case Signal.RS_LOOP:
                counter = self._return_stack.tos.current - 1
                if counter != 0:
                    self._return_stack.tos.latch(counter)
                    self._pc.latch(self._instr.operand)
                else:
                    self._return_stack.pop()

            # ── Регистр A ────────────────────────────────────────────────────
            case Signal.A_LATCH_TOS:
                dp.a_latch_tos()
            case Signal.PUSH_A:
                dp.push_a()
            case Signal.A_INC:
                dp.a_inc()
            case Signal.A_DEC:
                dp.a_dec()
