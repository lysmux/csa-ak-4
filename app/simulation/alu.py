from collections.abc import Callable
from dataclasses import dataclass

from app.isa.consts import MAX_SIGNED, MIN_SIGNED, SIGN_BIT, WORD_MASK, WORD_WIDTH
from app.isa.flags import Flags
from app.isa.opcode import Opcode

type BinaryOp = Callable[[int, int], int]
type UnaryOp = Callable[[int], int]


@dataclass(frozen=True)
class AluResult:
    value: int
    flags: Flags


def _signed(value: int) -> int:
    value &= WORD_MASK
    return value - (1 << WORD_WIDTH) if value & SIGN_BIT else value


def _trunc_div(a: int, b: int) -> int:
    q, r = divmod(a, b)
    if r != 0 and (a < 0) != (b < 0):
        q += 1
    return q


class Alu:
    BINARY_OPERATIONS: dict[Opcode, BinaryOp] = {
        Opcode.ADD: lambda a, b: a + b,
        Opcode.SUB: lambda a, b: a - b,
        Opcode.MUL: lambda a, b: a * b,
        Opcode.DIV: lambda a, b: _trunc_div(_signed(a), _signed(b)),
        Opcode.AND: lambda a, b: a & b,
        Opcode.OR: lambda a, b: a | b,
        Opcode.XOR: lambda a, b: a ^ b,
    }

    UNARY_OPERATIONS: dict[Opcode, UnaryOp] = {
        Opcode.INC: lambda a: a + 1,
        Opcode.DEC: lambda a: a - 1,
        Opcode.NEG: lambda a: -_signed(a),
        Opcode.NOT: lambda a: ~a,
        Opcode.SHL: lambda a: a << 1,
        Opcode.SHR: lambda a: a >> 1,
    }

    def perform(self, opcode: Opcode, left: int, right: int = 0) -> AluResult:
        if opcode in self.BINARY_OPERATIONS:
            return self.perform_binary(opcode, left, right)
        if opcode in self.UNARY_OPERATIONS:
            return self.perform_unary(opcode, left)

        msg = f"{opcode.name} is not an ALU operation"
        raise ValueError(msg)

    def perform_binary(self, opcode: Opcode, left: int, right: int) -> AluResult:
        operation = self.BINARY_OPERATIONS.get(opcode)
        if operation is None:
            msg = f"{opcode.name} is not a binary ALU operation"
            raise ValueError(msg)

        left &= WORD_MASK
        right &= WORD_MASK
        value = operation(left, right) & WORD_MASK
        flags = self._flags_binary(opcode, left, right, value)
        return AluResult(value, flags)

    def perform_unary(self, opcode: Opcode, operand: int) -> AluResult:
        operation = self.UNARY_OPERATIONS.get(opcode)
        if operation is None:
            msg = f"{opcode.name} is not a unary ALU operation"
            raise ValueError(msg)

        operand &= WORD_MASK
        value = operation(operand) & WORD_MASK
        flags = self._flags_unary(opcode, operand, value)
        return AluResult(value, flags)

    @staticmethod
    def _flags_binary(opcode: Opcode, a: int, b: int, value: int) -> Flags:
        flags = Flags.nz(value)

        if opcode == Opcode.ADD:
            if a + b > WORD_MASK:
                flags |= Flags.C
            if (a ^ value) & (b ^ value) & SIGN_BIT:
                flags |= Flags.V
        elif opcode in (Opcode.SUB, Opcode.CMP):
            if a < b:
                flags |= Flags.C
            if (a ^ b) & (a ^ value) & SIGN_BIT:
                flags |= Flags.V
        elif opcode == Opcode.MUL:
            signed_product = _signed(a) * _signed(b)
            if signed_product < MIN_SIGNED or signed_product > MAX_SIGNED:
                flags |= Flags.V | Flags.C
        elif opcode == Opcode.DIV:
            if _signed(a) == MIN_SIGNED and _signed(b) == -1:
                flags |= Flags.V

        return flags

    @staticmethod
    def _flags_unary(opcode: Opcode, a: int, value: int) -> Flags:
        flags = Flags.nz(value)

        if opcode == Opcode.INC:
            if a == WORD_MASK:
                flags |= Flags.C
            if _signed(a) == MAX_SIGNED:
                flags |= Flags.V
        elif opcode == Opcode.DEC:
            if a == 0:
                flags |= Flags.C
            if _signed(a) == MIN_SIGNED:
                flags |= Flags.V
        elif opcode == Opcode.NEG:
            if a != 0:
                flags |= Flags.C
            if _signed(a) == MIN_SIGNED:
                flags |= Flags.V
        elif opcode == Opcode.SHL:
            if a & SIGN_BIT:
                flags |= Flags.C
        elif opcode == Opcode.SHR:
            if a & 1:
                flags |= Flags.C

        return flags
