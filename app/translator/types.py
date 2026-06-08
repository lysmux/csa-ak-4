from enum import StrEnum


class Type(StrEnum):
    INT = "int"
    LONG = "long"
    BOOL = "bool"
    STRING = "string"
    ARRAY = "array"
    FUN = "fun"
    INTERRUPT = "interrupt"
    OUTPUT_DEVICE = "output_device"
    INPUT_DEVICE = "input_device"


NUMERIC = {Type.INT, Type.LONG}
PRINTABLE = frozenset({Type.STRING, Type.INT, Type.LONG, Type.BOOL})
