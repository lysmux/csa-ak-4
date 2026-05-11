import pytest
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import CharOutput, Device, IntOutput
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer, SemanticError
from app.translator.codegen import CodeGen, CodeGenError, OutputDevice
from app.translator.lexer import Lexer
from app.translator.parser import Parser

CHAR_OUT_ADDR = 0x222
INT_OUT_ADDR = 0x224

OUTPUTS: dict[str, OutputDevice] = {
    "default": OutputDevice(address=CHAR_OUT_ADDR, kind="char"),
    "char_output": OutputDevice(address=CHAR_OUT_ADDR, kind="char"),
    "int_output": OutputDevice(address=INT_OUT_ADDR, kind="int"),
}


def _compile(src: str, outputs: dict[str, OutputDevice] = OUTPUTS):
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(output_devices=set(outputs)).analyze(ast)
    return CodeGen(output_devices=outputs).generate(ast)


def _run(src: str, outputs: dict[str, OutputDevice] = OUTPUTS, limit: int = 1_000_000):
    program = _compile(src, outputs)

    instr_mem = Memory(2000)
    instr_mem.fill(program.instructions)
    data_mem = Memory(2000)
    data_mem.fill(program.data)
    return_stack = Stack(2000)
    data_stack = Stack(2000)

    char_dev = CharOutput()
    int_dev = IntOutput()
    io_map: dict[int, Device] = {
        CHAR_OUT_ADDR: char_dev,
        INT_OUT_ADDR: int_dev,
    }
    data_path = DataPath(memory=data_mem, stack=data_stack, io_map=io_map)
    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_mem,
        return_stack=return_stack,
        vector_table=dict(program.interrupt_handlers),
    )
    cu.run(limit=limit)
    return char_dev, int_dev


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_print_without_label_uses_default():
    char_dev, _ = _run('fun main() { print("hi"); }')
    assert char_dev.string == "hi"


def test_print_with_char_output_label():
    char_dev, _ = _run('fun main() { print(char_output, "hey"); }')
    assert char_dev.string == "hey"


def test_print_int_value_to_int_output():
    _, int_dev = _run('fun main() { print(int_output, 42); }')
    assert int_dev.buffer == [42]


def test_println_to_char_adds_newline():
    char_dev, _ = _run('fun main() { println(char_output, "ab"); }')
    assert char_dev.string == "ab\n"


def test_println_to_int_no_newline():
    _, int_dev = _run('fun main() { println(int_output, 42); println(int_output, 100); }')
    assert int_dev.buffer == [42, 100]
    assert int_dev.string == "42 100"


def test_mixed_routing():
    char_dev, int_dev = _run("""
        fun main() {
            println(default, "hello");
            println(char_output, "world");
            println(int_output, 42);
            println(int_output, 100);
        }
    """)
    assert char_dev.string == "hello\nworld\n"
    assert int_dev.buffer == [42, 100]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_missing_default_raises():
    outputs = {"char_output": OutputDevice(address=CHAR_OUT_ADDR, kind="char")}
    with pytest.raises(CodeGenError, match="no 'default'"):
        _compile('fun main() { print("hi"); }', outputs=outputs)


def test_device_label_in_expression_raises():
    with pytest.raises(SemanticError, match="device label 'char_output'"):
        _compile("fun main() { var x: int = char_output; }")


def test_device_label_in_arithmetic_raises():
    with pytest.raises(SemanticError, match="device label"):
        _compile('fun main() { print(default, char_output + 1); }')
