from enum import IntEnum, unique


@unique
class Opcode(IntEnum):
    # --- Системные ---
    NOP = 0x01
    HALT = 0x02

    # --- Стек ---
    PUSH = 0x10
    DUP = 0x11
    DROP = 0x12
    SWAP = 0x13
    OVER = 0x14

    # --- Память ---
    LOAD = 0x20
    STORE = 0x21

    # --- Арифметические операции ---
    ADD = 0x30
    SUB = 0x31
    MUL = 0x32
    DIV = 0x33
    CMP = 0x34
    INC = 0x35
    DEC = 0x36
    NEG = 0x37

    # --- Логические операции ---
    AND = 0x40
    OR = 0x41
    XOR = 0x42
    NOT = 0x43
    SHL = 0x44
    SHR = 0x45

    # --- Условные переходы ---
    JZ = 0x50
    JNZ = 0x51
    JGE = 0x52
    JL = 0x53
    JG = 0x54
    JLE = 0x55
    JC = 0x56
    JNC = 0x57

    # --- Управление потоком выполнения ---
    JMP = 0x60
    CALL = 0x61
    RET = 0x62
    LOOP = 0x63
    PSHR = 0x64
    POPR = 0x65

    # --- Прерывания ---
    EI = 0x70
    DI = 0x71
    RTI = 0x72

    # --- Регистр A ---
    PSHA = 0x82
    POPA = 0x83
    LDA_INC = 0x86
    LDA_DEC = 0x87
    STA_INC = 0x88
    STA_DEC = 0x89
