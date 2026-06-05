import pytest
from app.isa.consts import INSTR_BYTES
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import run_simulation


def addr(index: int) -> int:
    """Byte address of the instruction at the given list index."""
    return index * INSTR_BYTES


# ---------------------------------------------------------------------------
# NOP
# ---------------------------------------------------------------------------


def test_nop_does_nothing():
    instructions = [
        Instruction(Opcode.PUSH, 0x7),
        Instruction(Opcode.NOP),
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x7


# ---------------------------------------------------------------------------
# JMP — unconditional
# ---------------------------------------------------------------------------


def test_jmp_skips_instruction():
    instructions = [
        Instruction(Opcode.JMP, addr(2)),  # 0: jump over the poison PUSH
        Instruction(Opcode.PUSH, 0xBAD),  # 1: must be skipped
        Instruction(Opcode.PUSH, 0x600D),  # 2: target
        Instruction(Opcode.HALT),  # 3
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0x600D
    # only the target PUSH ran → a single cell on the stack
    assert snapshot.data_stack[0] == 0x600D
    assert snapshot.data_stack[1] == 0


# ---------------------------------------------------------------------------
# Conditional jumps — FLAGS are set with CMP (FLAGS = NOS - TOS)
# ---------------------------------------------------------------------------

# Each setup leaves a known flag state and both operands on the stack:
#   Z   : 5 - 5 = 0          → Z
#   POS : 5 - 3 = 2          → (no flags)
#   NEG : 1 - 2 = -1         → N C
#   OVF : MIN - MAX = 1      → V
_SETUPS = {
    "Z": [Instruction(Opcode.PUSH, 5), Instruction(Opcode.PUSH, 5), Instruction(Opcode.CMP)],
    "POS": [Instruction(Opcode.PUSH, 5), Instruction(Opcode.PUSH, 3), Instruction(Opcode.CMP)],
    "NEG": [Instruction(Opcode.PUSH, 1), Instruction(Opcode.PUSH, 2), Instruction(Opcode.CMP)],
    "OVF": [Instruction(Opcode.PUSH, 0x80000000), Instruction(Opcode.PUSH, 0x7FFFFFFF), Instruction(Opcode.CMP)],
}

# (opcode, setup_key, taken?)
_BRANCH_CASES = [
    (Opcode.JZ, "Z", True),
    (Opcode.JZ, "POS", False),
    (Opcode.JNZ, "POS", True),
    (Opcode.JNZ, "Z", False),
    (Opcode.JPL, "POS", True),
    (Opcode.JPL, "NEG", False),
    (Opcode.JMI, "NEG", True),
    (Opcode.JMI, "POS", False),
    (Opcode.JGE, "POS", True),
    (Opcode.JGE, "NEG", False),
    (Opcode.JL, "NEG", True),
    (Opcode.JL, "POS", False),
    (Opcode.JG, "POS", True),
    (Opcode.JG, "Z", False),
    (Opcode.JLE, "Z", True),
    (Opcode.JLE, "POS", False),
    (Opcode.JC, "NEG", True),
    (Opcode.JC, "POS", False),
    (Opcode.JNC, "POS", True),
    (Opcode.JNC, "NEG", False),
    (Opcode.JV, "OVF", True),
    (Opcode.JV, "POS", False),
    (Opcode.JNV, "POS", True),
    (Opcode.JNV, "OVF", False),
]


@pytest.mark.parametrize(("opcode", "setup_key", "taken"), _BRANCH_CASES)
def test_conditional_jump(opcode: Opcode, setup_key: str, taken: bool):
    setup = _SETUPS[setup_key]
    s = len(setup)
    # layout: [setup] ; s: Jcc target ; s+1: PUSH 0 ; s+2: HALT ; s+3: PUSH 1 ; s+4: HALT
    target = s + 3
    instructions = [
        *setup,
        Instruction(opcode, addr(target)),
        Instruction(Opcode.PUSH, 0),  # not-taken marker
        Instruction(Opcode.HALT),
        Instruction(Opcode.PUSH, 1),  # taken marker
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == (1 if taken else 0)


# ---------------------------------------------------------------------------
# LOOP — return-stack counter; jumps until the decremented counter hits 0
# ---------------------------------------------------------------------------


def test_loop_runs_body_n_times():
    # Increment M[0] once per iteration; counter starts at 3 → body runs 3 times.
    instructions = [
        Instruction(Opcode.PUSH, 0),  # 0
        Instruction(Opcode.STORE, 0),  # 1: M[0] = 0
        Instruction(Opcode.PUSH, 3),  # 2: loop counter
        Instruction(Opcode.PSHR),  # 3: move counter to return stack
        Instruction(Opcode.LOAD, 0),  # 4: <- loop body start
        Instruction(Opcode.INC),  # 5
        Instruction(Opcode.STORE, 0),  # 6: M[0]++
        Instruction(Opcode.LOOP, addr(4)),  # 7: dec counter, jump back while != 0
        Instruction(Opcode.HALT),  # 8
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.data_memory[0] == 3


# ---------------------------------------------------------------------------
# CALL / RET
# ---------------------------------------------------------------------------


def test_call_ret_returns_after_call():
    instructions = [
        Instruction(Opcode.PUSH, 5),  # 0
        Instruction(Opcode.CALL, addr(3)),  # 1: call fn
        Instruction(Opcode.HALT),  # 2: return lands here
        Instruction(Opcode.INC),  # 3: fn: 5 -> 6
        Instruction(Opcode.RET),  # 4
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 6
    # the return stack is empty again after RET
    assert snapshot.return_stack[0] == 0


def test_call_pushes_return_address():
    # CALL must push the address of the instruction right after it, so RET resumes there.
    instructions = [
        Instruction(Opcode.CALL, addr(2)),  # 0
        Instruction(Opcode.HALT),  # 1: return target
        Instruction(Opcode.RET),  # 2: fn returns immediately
    ]
    snapshot = run_simulation(instructions, {})
    # RET landed on the HALT at index 1 (fetch then advanced PC to addr(2)).
    assert snapshot.instruction.opcode == Opcode.HALT
    assert snapshot.pc == addr(2)


# ---------------------------------------------------------------------------
# PSHR / POPR — move the top of the data stack to/from the return stack
# ---------------------------------------------------------------------------


def test_pshr_popr_round_trip():
    instructions = [
        Instruction(Opcode.PUSH, 0xABC),
        Instruction(Opcode.PSHR),  # data -> return stack
        Instruction(Opcode.POPR),  # return stack -> data
        Instruction(Opcode.HALT),
    ]
    snapshot = run_simulation(instructions, {})
    assert snapshot.tos == 0xABC
    assert snapshot.return_stack[0] == 0
