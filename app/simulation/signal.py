from enum import Enum, auto


class Signal(Enum):
    # ── PC ──────────────────────────────────────────────────────────────────
    PC_INC       = auto()   # PC ← PC + 1
    PC_LATCH_IMM = auto()   # PC ← IR.operand
    PC_LATCH_RET = auto()   # PC ← RS.pop()

    # ── Память команд ───────────────────────────────────────────────────────
    IMEM_LATCH_PC = auto()  # instr_mem.AR ← PC
    IMEM_READ     = auto()  # чтение из памяти команд
    IR_LATCH      = auto()  # IR ← instr_mem.out

    # ── Память данных ───────────────────────────────────────────────────────
    DMEM_LATCH_IMM = auto() # data_mem.AR ← IR.operand
    DMEM_LATCH_TOS = auto() # data_mem.AR ← TOS (без pop)
    DMEM_LATCH_A   = auto() # data_mem.AR ← A
    DMEM_READ      = auto() # чтение из памяти данных
    DMEM_WRITE     = auto() # M[AR] ← DR

    # ── Регистр DR ──────────────────────────────────────────────────────────
    DR_LATCH_MEM = auto()   # DR ← data_mem.out
    DR_LATCH_TOS = auto()   # DR ← TOS (без pop)

    # ── Стек данных ─────────────────────────────────────────────────────────
    PUSH_DR  = auto()       # push DR
    PUSH_IMM = auto()       # push IR.operand
    DROP     = auto()       # pop (отбросить)
    DUP      = auto()       # push TOS
    SWAP     = auto()       # TOS ↔ NOS
    OVER     = auto()       # push NOS

    # ── ALU binary: NOS op TOS → pop оба, push result ───────────────────────
    ALU_ADD = auto()
    ALU_SUB = auto()
    ALU_MUL = auto()
    ALU_DIV = auto()
    ALU_AND = auto()
    ALU_OR  = auto()
    ALU_XOR = auto()
    ALU_CMP = auto()        # flags ← NOS − TOS; стек не изменяется

    # ── ALU unary: TOS → pop, push result ───────────────────────────────────
    ALU_INC = auto()
    ALU_DEC = auto()
    ALU_NEG = auto()
    ALU_NOT = auto()
    ALU_SHL = auto()
    ALU_SHR = auto()

    # ── Стек возвратов ───────────────────────────────────────────────────────
    RS_PUSH_PC    = auto()  # RS.push(PC)
    RS_PUSH_FLAGS = auto()  # RS.push(FLAGS)
    RS_POP_PC     = auto()  # PC ← RS.pop()
    RS_POP_FLAGS  = auto()  # FLAGS ← RS.pop()
    RS_PUSH_TOS   = auto()  # RS.push(TOS); pop  — PSHR
    RS_POP_TOS    = auto()  # push(RS.pop())      — POPR
    RS_LOOP       = auto()  # RS.top--; если > 0 → PC ← IR.operand

    # ── Регистр A ────────────────────────────────────────────────────────────
    A_LATCH_TOS = auto()    # A ← TOS; pop
    PUSH_A      = auto()    # push A
    A_INC       = auto()    # A ← A + 1
    A_DEC       = auto()    # A ← A − 1

    # ── Условные переходы (PC ← IR.operand если условие выполнено) ─────────
    JZ_BRANCH  = auto()    # if Z
    JNZ_BRANCH = auto()    # if not Z
    JGE_BRANCH = auto()    # if N == V
    JL_BRANCH  = auto()    # if N != V
    JG_BRANCH  = auto()    # if not Z and N == V
    JLE_BRANCH = auto()    # if Z or N != V
    JC_BRANCH  = auto()    # if C
    JNC_BRANCH = auto()    # if not C
