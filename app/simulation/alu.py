from collections.abc import Callable
from dataclasses import dataclass

from app.isa.consts import MAX_SIGNED, MIN_SIGNED, SIGN_BIT, WORD_MASK, WORD_WIDTH
from app.isa.flag import Flag
from app.isa.opcode import Opcode

type BinaryOp = Callable[[int, int], int]
type UnaryOp = Callable[[int], int]


@dataclass(frozen=True)
class AluResult:
    value: int
    flags: Flag


def _signed(value: int) -> int:
    value &= WORD_MASK
    return value - (1 << WORD_WIDTH) if value & SIGN_BIT else value


def _trunc_div(a: int, b: int) -> int:
    q, r = divmod(a, b)
    if r != 0 and (a < 0) != (b < 0):
        q += 1
    return q


DWORD_WIDTH = 2 * WORD_WIDTH
DWORD_MASK = (1 << DWORD_WIDTH) - 1
DWORD_SIGN_BIT = 1 << (DWORD_WIDTH - 1)
DWORD_MAX_SIGNED = (1 << (DWORD_WIDTH - 1)) - 1
DWORD_MIN_SIGNED = -(1 << (DWORD_WIDTH - 1))


def _signed_dword(value: int) -> int:
    value &= DWORD_MASK
    return value - (1 << DWORD_WIDTH) if value & DWORD_SIGN_BIT else value


def _flags_dword(value: int) -> Flag:
    flags = Flag(0)
    if value == 0:
        flags |= Flag.Z
    if value & DWORD_SIGN_BIT:
        flags |= Flag.N
    return flags


def dword_mul(a: int, b: int) -> tuple[int, Flag]:
    """Double-word (2*WORD_WIDTH) multiply, modelled at value level. Returns (low_dword, flags)."""
    a &= DWORD_MASK
    b &= DWORD_MASK
    value = (a * b) & DWORD_MASK
    flags = _flags_dword(value)
    signed_product = _signed_dword(a) * _signed_dword(b)
    if signed_product < DWORD_MIN_SIGNED or signed_product > DWORD_MAX_SIGNED:
        flags |= Flag.V | Flag.C
    return value, flags


def dword_div(a: int, b: int) -> tuple[int, Flag]:
    """Double-word signed truncating division, modelled at value level. Returns (quotient, flags)."""
    value = _trunc_div(_signed_dword(a), _signed_dword(b)) & DWORD_MASK
    flags = _flags_dword(value)
    if _signed_dword(a) == DWORD_MIN_SIGNED and _signed_dword(b) == -1:
        flags |= Flag.V
    return value, flags


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

    def perform(self, opcode: Opcode, left: int, right: int = 0, carry_in: int = 0) -> AluResult:
        if opcode in self.BINARY_OPERATIONS:
            return self.perform_binary(opcode, left, right, carry_in)
        if opcode in self.UNARY_OPERATIONS:
            return self.perform_unary(opcode, left, carry_in)

        msg = f"{opcode.name} is not an ALU operation"
        raise ValueError(msg)

    def perform_binary(self, opcode: Opcode, left: int, right: int, carry_in: int = 0) -> AluResult:
        operation = self.BINARY_OPERATIONS.get(opcode)
        if operation is None:
            msg = f"{opcode.name} is not a binary ALU operation"
            raise ValueError(msg)

        left &= WORD_MASK
        right &= WORD_MASK
        value = (operation(left, right) + carry_in) & WORD_MASK
        flags = self._flags_binary(opcode, left, right, value, carry_in)
        return AluResult(value, flags)

    def perform_unary(self, opcode: Opcode, operand: int, carry_in: int = 0) -> AluResult:
        operation = self.UNARY_OPERATIONS.get(opcode)
        if operation is None:
            msg = f"{opcode.name} is not a unary ALU operation"
            raise ValueError(msg)

        operand &= WORD_MASK
        value = (operation(operand) + carry_in) & WORD_MASK
        flags = self._flags_unary(opcode, operand, value)
        return AluResult(value, flags)

    @staticmethod
    def _flags_binary(opcode: Opcode, a: int, b: int, value: int, carry_in: int = 0) -> Flag:
        flags = Flag.nz(value)

        if opcode == Opcode.ADD:
            if a + b + carry_in > WORD_MASK:
                flags |= Flag.C
            if (a ^ value) & (b ^ value) & SIGN_BIT:
                flags |= Flag.V
        elif opcode in (Opcode.SUB, Opcode.CMP):
            # carry_in carries a negative borrow (-1) for subtract-with-borrow (SBB).
            if a - b + carry_in < 0:
                flags |= Flag.C
            if (a ^ b) & (a ^ value) & SIGN_BIT:
                flags |= Flag.V
        elif opcode == Opcode.MUL:
            signed_product = _signed(a) * _signed(b)
            if signed_product < MIN_SIGNED or signed_product > MAX_SIGNED:
                flags |= Flag.V | Flag.C
        elif opcode == Opcode.DIV:
            if _signed(a) == MIN_SIGNED and _signed(b) == -1:
                flags |= Flag.V

        return flags

    @staticmethod
    def _flags_unary(opcode: Opcode, a: int, value: int) -> Flag:
        flags = Flag.nz(value)

        if opcode == Opcode.INC:
            if a == WORD_MASK:
                flags |= Flag.C
            if _signed(a) == MAX_SIGNED:
                flags |= Flag.V
        elif opcode == Opcode.DEC:
            if a == 0:
                flags |= Flag.C
            if _signed(a) == MIN_SIGNED:
                flags |= Flag.V
        elif opcode == Opcode.NEG:
            if a != 0:
                flags |= Flag.C
            if _signed(a) == MIN_SIGNED:
                flags |= Flag.V
        elif opcode == Opcode.SHL:
            if a & SIGN_BIT:
                flags |= Flag.C
        elif opcode == Opcode.SHR:
            if a & 1:
                flags |= Flag.C

        return flags
