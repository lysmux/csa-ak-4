from app.isa.opcode import Opcode


class ALU:
    def perform(self, opcode: Opcode, left: int, right: int) -> int:
        match opcode:
            case Opcode.ADD:
                return left + right
            case Opcode.SUB:
                return left - right
            case Opcode.INC:
                return left + 1
            case Opcode.DEC:
                return left - 1
            case _:
                return 0
