from app.isa.instruction import Instruction
from app.isa.opcode import Opcode

print(f"{Instruction(opcode=Opcode.ADD, operand=0).to_binary():02X}")
print(Instruction.from_binary(0x1000001))
