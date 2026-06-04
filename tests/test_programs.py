from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

from tests.shared import run_simulation


def test_factorial():
    """Computes 8! = 40320 recursively.

    Calling convention: n on TOS before CALL, result on TOS after RET.
    CMP peeks at TOS and NOS, sets FLAGS = NOS-TOS, stack unchanged.

    Layout:
        0: LOAD  0x0        load n=8
        1: CALL  4          call fac; return addr=2
        2: STORE 0x2        store result
        3: HALT

    fac(n):
        4: PUSH 1           [1, n]
        5: CMP              FLAGS = NOS-TOS = n-1; stack unchanged
        6: JLE  15          n <= 1 → base case

        ; recursive branch: stack=[1, n]
        7: DROP             [n]
        8: DUP              [n, n]
        9: PSHR             save n to return stack; data=[n]
        10: DEC             [n-1]
        11: CALL 4          fac(n-1); return addr=12
        12: POPR            [n, fac(n-1)]
        13: MUL             [n * fac(n-1)]
        14: RET

        ; base case: stack=[1, n]
        15: DROP            [n]
        16: DROP            []
        17: PUSH 1          [1]
        18: RET
    """
    memory = {0x0: 8}
    instructions = [
        # main
        Instruction(Opcode.LOAD, 0x0),  # 0
        Instruction(Opcode.CALL, 4),  # 1
        Instruction(Opcode.STORE, 0x2),  # 2
        Instruction(Opcode.HALT),  # 3
        # fac(n)
        Instruction(Opcode.PUSH, 1),  # 4
        Instruction(Opcode.CMP),  # 5  FLAGS = n-1
        Instruction(Opcode.JLE, 15),  # 6  n <= 1 → base
        # recursive branch
        Instruction(Opcode.DROP),  # 7
        Instruction(Opcode.DUP),  # 8
        Instruction(Opcode.PSHR),  # 9
        Instruction(Opcode.DEC),  # 10
        Instruction(Opcode.CALL, 4),  # 11
        Instruction(Opcode.POPR),  # 12
        Instruction(Opcode.MUL),  # 13
        Instruction(Opcode.RET),  # 14
        # base case
        Instruction(Opcode.DROP),  # 15
        Instruction(Opcode.DROP),  # 16
        Instruction(Opcode.PUSH, 1),  # 17
        Instruction(Opcode.RET),  # 18
    ]

    snapshot = run_simulation(instructions, memory)

    assert snapshot.data_memory[0x2] == 40320
