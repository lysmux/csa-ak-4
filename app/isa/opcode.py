from enum import IntEnum, unique


@unique
class Opcode(IntEnum):
    NOP = 0x01
    HALT = 0x02

    # Стек
    PUSH = 0x10
    DUP = 0x11
    DROP = 0x12
    SWAP = 0x13
    OVER = 0x14

    # Память
    LOAD = 0x20
    STORE = 0x21
    LOADI = 0x22
    STOREI = 0x23

    # Арифметические операции
    ADD = 0x30
    SUB = 0x31
    MUL = 0x32
    DIV = 0x33
    CMP = 0x34
    INC = 0x35
    DEC = 0x36
    NEG = 0x37
    ADDC = 0x38
    DADD = 0x39
    DSUB = 0x3A
    DMUL = 0x3B
    DDIV = 0x3C
    I2L = 0x3D

    # Логические операции
    AND = 0x40
    OR = 0x41
    XOR = 0x42
    NOT = 0x43
    SHL = 0x44
    SHR = 0x45

    # Условные переходы
    JZ = 0x50
    JNZ = 0x51
    JPL = 0x52
    JMI = 0x53
    JGE = 0x54
    JL = 0x55
    JG = 0x56
    JLE = 0x57
    JC = 0x58
    JNC = 0x59
    JV = 0x5A
    JNV = 0x5B

    # Управление потоком выполнения
    JMP = 0x60
    CALL = 0x61
    RET = 0x62
    LOOP = 0x63
    PSHR = 0x64
    POPR = 0x65

    # Прерывания
    EI = 0x70
    DI = 0x71
    RTI = 0x72


BRANCH_OPCODES = {
    Opcode.JMP,
    Opcode.JZ,
    Opcode.JNZ,
    Opcode.JPL,
    Opcode.JMI,
    Opcode.JGE,
    Opcode.JL,
    Opcode.JG,
    Opcode.JLE,
    Opcode.JC,
    Opcode.JNC,
    Opcode.JV,
    Opcode.JNV,
}
ONE_CYCLE_OPCODES = {
    Opcode.NOP,
    Opcode.PUSH,
    Opcode.DUP,
    Opcode.SWAP,
    Opcode.OVER,
    Opcode.EI,
    Opcode.DI,
    Opcode.CMP,
    Opcode.I2L,
    Opcode.INC,
    Opcode.DEC,
    Opcode.NEG,
    Opcode.NOT,
    Opcode.SHL,
    Opcode.SHR,
    *BRANCH_OPCODES,
}
