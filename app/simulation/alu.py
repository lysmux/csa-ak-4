from collections.abc import Callable
from dataclasses import dataclass

from app.isa.consts import WORD_WIDTH
from app.isa.flag import Flag
from app.isa.opcode import Opcode

type BinaryOp = Callable[[int, int], int]
type UnaryOp = Callable[[int], int]


@dataclass(frozen=True)
class AluResult:
    value: int
    flags: Flag


@dataclass(frozen=True)
class NumberFormat:
    width: int

    @property
    def mask(self) -> int:
        return (1 << self.width) - 1

    @property
    def sign_bit(self) -> int:
        return 1 << (self.width - 1)

    @property
    def min_signed(self) -> int:
        return -(1 << (self.width - 1))

    @property
    def max_signed(self) -> int:
        return (1 << (self.width - 1)) - 1

    def normalize(self, value: int) -> int:
        return value & self.mask

    def signed(self, value: int) -> int:
        value = self.normalize(value)
        return value - (1 << self.width) if value & self.sign_bit else value

    def nz_flags(self, value: int) -> Flag:
        value = self.normalize(value)
        flags = Flag(0)

        if value == 0:
            flags |= Flag.Z
        if value & self.sign_bit:
            flags |= Flag.N

        return flags

    def is_signed_overflow(self, value: int) -> bool:
        return value < self.min_signed or value > self.max_signed


WORD = NumberFormat(WORD_WIDTH)


def _trunc_div(a: int, b: int) -> int:
    quotient, remainder = divmod(a, b)

    if remainder != 0 and (a < 0) != (b < 0):
        quotient += 1

    return quotient


class Alu:
    BINARY_OPERATIONS: dict[Opcode, BinaryOp] = {
        Opcode.ADD: lambda a, b: a + b,
        Opcode.SUB: lambda a, b: a - b,
        Opcode.CMP: lambda a, b: a - b,
        Opcode.MUL: lambda a, b: a * b,
        Opcode.DIV: lambda a, b: _trunc_div(WORD.signed(a), WORD.signed(b)),
        Opcode.AND: lambda a, b: a & b,
        Opcode.OR: lambda a, b: a | b,
        Opcode.XOR: lambda a, b: a ^ b,
    }

    UNARY_OPERATIONS: dict[Opcode, UnaryOp] = {
        Opcode.INC: lambda a: a + 1,
        Opcode.DEC: lambda a: a - 1,
        Opcode.NEG: lambda a: -WORD.signed(a),
        Opcode.NOT: lambda a: ~a,
        Opcode.SHL: lambda a: a << 1,
        Opcode.SHR: lambda a: a >> 1,
        Opcode.I2L: lambda a: WORD.mask if a & WORD.sign_bit else 0,
    }

    CARRY_BINARY_OPERATIONS = {
        Opcode.ADD,
        Opcode.SUB,
        Opcode.CMP,
    }

    def is_binary(self, opcode: Opcode) -> bool:
        return opcode in self.BINARY_OPERATIONS

    def is_unary(self, opcode: Opcode) -> bool:
        return opcode in self.UNARY_OPERATIONS

    def perform(
        self,
        opcode: Opcode,
        left: int,
        right: int = 0,
        carry_in: int = 0,
    ) -> AluResult:
        if self.is_binary(opcode):
            return self.perform_binary(opcode, left, right, carry_in)

        if self.is_unary(opcode):
            return self.perform_unary(opcode, left)

        msg = f"{opcode.name} is not an ALU operation"
        raise ValueError(msg)

    def perform_binary(
        self,
        opcode: Opcode,
        left: int,
        right: int,
        carry_in: int = 0,
    ) -> AluResult:
        operation = self.BINARY_OPERATIONS.get(opcode)

        if operation is None:
            msg = f"{opcode.name} is not a binary ALU operation"
            raise ValueError(msg)

        left = WORD.normalize(left)
        right = WORD.normalize(right)

        effective_carry = carry_in if opcode in self.CARRY_BINARY_OPERATIONS else 0
        raw_value = operation(left, right) + effective_carry
        value = WORD.normalize(raw_value)

        flags = self._flags_binary(
            opcode=opcode,
            left=left,
            right=right,
            value=value,
            carry_in=effective_carry,
        )

        return AluResult(value, flags)

    def perform_unary(self, opcode: Opcode, operand: int) -> AluResult:
        operation = self.UNARY_OPERATIONS.get(opcode)

        if operation is None:
            msg = f"{opcode.name} is not a unary ALU operation"
            raise ValueError(msg)

        operand = WORD.normalize(operand)
        value = WORD.normalize(operation(operand))
        flags = self._flags_unary(opcode, operand, value)

        return AluResult(value, flags)

    @staticmethod
    def _flags_binary(
        opcode: Opcode,
        left: int,
        right: int,
        value: int,
        carry_in: int = 0,
    ) -> Flag:
        flags = WORD.nz_flags(value)

        if opcode == Opcode.ADD:
            if left + right + carry_in > WORD.mask:
                flags |= Flag.C
            if (left ^ value) & (right ^ value) & WORD.sign_bit:
                flags |= Flag.V

        elif opcode in (Opcode.SUB, Opcode.CMP):
            if left - right + carry_in < 0:
                flags |= Flag.C
            if (left ^ right) & (left ^ value) & WORD.sign_bit:
                flags |= Flag.V

        elif opcode == Opcode.MUL:
            product = WORD.signed(left) * WORD.signed(right)
            if WORD.is_signed_overflow(product):
                flags |= Flag.V | Flag.C

        elif opcode == Opcode.DIV:
            if WORD.signed(left) == WORD.min_signed and WORD.signed(right) == -1:
                flags |= Flag.V

        return flags

    @staticmethod
    def _flags_unary(opcode: Opcode, operand: int, value: int) -> Flag:
        flags = WORD.nz_flags(value)

        if opcode == Opcode.INC:
            if operand == WORD.mask:
                flags |= Flag.C
            if WORD.signed(operand) == WORD.max_signed:
                flags |= Flag.V

        elif opcode == Opcode.DEC:
            if operand == 0:
                flags |= Flag.C
            if WORD.signed(operand) == WORD.min_signed:
                flags |= Flag.V

        elif opcode == Opcode.NEG:
            if operand != 0:
                flags |= Flag.C
            if WORD.signed(operand) == WORD.min_signed:
                flags |= Flag.V

        elif opcode == Opcode.SHL:
            if operand & WORD.sign_bit:
                flags |= Flag.C

        elif opcode == Opcode.SHR:
            if operand & 1:
                flags |= Flag.C

        return flags
