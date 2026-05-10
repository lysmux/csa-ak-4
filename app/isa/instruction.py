from dataclasses import dataclass

from app.isa.opcode import Opcode


@dataclass
class Instruction:
    opcode: Opcode
    operand: int = 0

    def to_binary(self) -> int:
        return self.opcode << 32 | (self.operand & 0xFFFFFFFF)

    @classmethod
    def from_binary(cls, binary: int) -> "Instruction":
        if binary.bit_length() > 40:
            msg = f"Instruction code too long: {binary:#X}"
            raise ValueError(msg)

        opcode = Opcode((binary >> 32) & 0xFF)
        operand = binary & 0xFFFFFFFF

        return Instruction(opcode, operand)
