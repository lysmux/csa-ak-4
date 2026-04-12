from dataclasses import dataclass

from app.isa.opcode import Opcode


@dataclass
class Instruction:
    opcode: Opcode
    operand: int = 0

    def to_binary(self) -> int:
        return self.opcode << 24 | self.operand

    @classmethod
    def from_binary(cls, binary: int) -> "Instruction":
        if binary.bit_length() > 32:
            raise ValueError("Invalid instruction code")

        opcode = Opcode((binary >> 24) & 0xFF)
        operand = binary & (1 << 24) - 1

        return Instruction(opcode, operand)
