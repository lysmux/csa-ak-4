from app.isa.opcode import Opcode
from app.simulation.signal import Signal

type MicroTick    = set[Signal]
type MicroProgram = list[MicroTick]

FETCH_SIGNALS: MicroProgram = [
    {Signal.IMEM_LATCH_PC, Signal.IMEM_READ},  # тик 1: AR ← PC, чтение
    {Signal.IR_LATCH,      Signal.PC_INC},      # тик 2: IR ← M[AR], PC ← PC + 1
]

EXECUTE_SIGNALS: dict[Opcode, MicroProgram] = {
    # ── Системные ──────────────────────────────────────────────────────────
    Opcode.NOP:  [],
    Opcode.HALT: [],

    # ── Стек ───────────────────────────────────────────────────────────────
    Opcode.PUSH: [{Signal.PUSH_IMM}],
    Opcode.DUP:  [{Signal.DUP}],
    Opcode.DROP: [{Signal.DROP}],
    Opcode.SWAP: [{Signal.SWAP}],
    Opcode.OVER: [{Signal.OVER}],

    # ── Память ─────────────────────────────────────────────────────────────
    # LOAD addr : push M[addr]
    Opcode.LOAD: [
        {Signal.DMEM_LATCH_IMM, Signal.DMEM_READ},
        {Signal.DR_LATCH_MEM,   Signal.PUSH_DR},
    ],
    # STORE addr : M[addr] ← TOS; pop
    Opcode.STORE: [
        {Signal.DR_LATCH_TOS, Signal.DROP},
        {Signal.DMEM_LATCH_IMM, Signal.DMEM_WRITE},
    ],

    # ── Арифметика ─────────────────────────────────────────────────────────
    Opcode.ADD: [{Signal.ALU_ADD}],
    Opcode.SUB: [{Signal.ALU_SUB}],
    Opcode.MUL: [{Signal.ALU_MUL}],
    Opcode.DIV: [{Signal.ALU_DIV}],
    Opcode.CMP: [{Signal.ALU_CMP}],
    Opcode.INC: [{Signal.ALU_INC}],
    Opcode.DEC: [{Signal.ALU_DEC}],
    Opcode.NEG: [{Signal.ALU_NEG}],

    # ── Логические ─────────────────────────────────────────────────────────
    Opcode.AND: [{Signal.ALU_AND}],
    Opcode.OR:  [{Signal.ALU_OR}],
    Opcode.XOR: [{Signal.ALU_XOR}],
    Opcode.NOT: [{Signal.ALU_NOT}],
    Opcode.SHL: [{Signal.ALU_SHL}],
    Opcode.SHR: [{Signal.ALU_SHR}],

    # ── Условные переходы ──────────────────────────────────────────────────
    Opcode.JZ:  [{Signal.JZ_BRANCH}],
    Opcode.JNZ: [{Signal.JNZ_BRANCH}],
    Opcode.JGE: [{Signal.JGE_BRANCH}],
    Opcode.JL:  [{Signal.JL_BRANCH}],
    Opcode.JG:  [{Signal.JG_BRANCH}],
    Opcode.JLE: [{Signal.JLE_BRANCH}],
    Opcode.JC:  [{Signal.JC_BRANCH}],
    Opcode.JNC: [{Signal.JNC_BRANCH}],

    # ── Управление потоком ─────────────────────────────────────────────────
    # JMP addr : PC ← addr
    Opcode.JMP:  [{Signal.PC_LATCH_IMM}],
    # CALL addr : RS.push(PC); PC ← addr
    Opcode.CALL: [{Signal.RS_PUSH_PC, Signal.PC_LATCH_IMM}],
    # RET : PC ← RS.pop()
    Opcode.RET:  [{Signal.RS_POP_PC}],
    # LOOP addr : RS.top--; if ≠ 0 → PC ← addr; else RS.pop()
    Opcode.LOOP: [{Signal.RS_LOOP}],
    # PSHR : RS.push(TOS); pop
    Opcode.PSHR: [{Signal.RS_PUSH_TOS}],
    # POPR : push(RS.pop())
    Opcode.POPR: [{Signal.RS_POP_TOS}],
    # ── Регистр A ──────────────────────────────────────────────────────────
    # PSHA : push A
    Opcode.PSHA: [{Signal.PUSH_A}],
    # POPA : A ← TOS; pop
    Opcode.POPA: [{Signal.A_LATCH_TOS}],

    # LDA+ : push M[A]; A ← A + 1
    Opcode.LDA_INC: [
        {Signal.DMEM_LATCH_A, Signal.DMEM_READ},
        {Signal.DR_LATCH_MEM, Signal.PUSH_DR, Signal.A_INC},
    ],
    # LDA- : A ← A − 1; push M[A]
    Opcode.LDA_DEC: [
        {Signal.A_DEC},
        {Signal.DMEM_LATCH_A, Signal.DMEM_READ},
        {Signal.DR_LATCH_MEM, Signal.PUSH_DR},
    ],
    # STA+ : M[A] ← TOS; pop; A ← A + 1
    Opcode.STA_INC: [
        {Signal.DR_LATCH_TOS, Signal.DROP},
        {Signal.DMEM_LATCH_A, Signal.DMEM_WRITE, Signal.A_INC},
    ],
    # STA- : A ← A − 1; M[A] ← TOS; pop
    Opcode.STA_DEC: [
        {Signal.DR_LATCH_TOS, Signal.DROP},
        {Signal.A_DEC},
        {Signal.DMEM_LATCH_A, Signal.DMEM_WRITE},
    ],
}
