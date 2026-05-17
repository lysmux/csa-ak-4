from typing import Literal

from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import Device, Output
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen
from app.translator.lexer import Lexer
from app.translator.parser import Parser

OUT_ADDR = 0x222


def _run(src: str, format: Literal["string", "raw"] = "string", limit: int = 1_000_000) -> Output:
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    Analyzer().analyze(ast)
    program = CodeGen(output_address=OUT_ADDR).generate(ast)

    instr_mem = Memory(2000)
    instr_mem.fill(program.instructions)
    data_mem = Memory(2000)
    data_mem.fill(program.data)

    output = Output(format=format)
    io_map: dict[int, Device] = {OUT_ADDR: output}
    data_path = DataPath(memory=data_mem, stack=Stack(2000), io_map=io_map)
    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_mem,
        return_stack=Stack(2000),
        vector_table=dict(program.interrupt_handlers),
    )
    cu.run(limit=limit)
    return output


def test_print_string_format():
    out = _run('fun main() { print("hi"); }', format="string")
    assert out.as_string() == "hi"


def test_print_int_raw_format():
    out = _run("fun main() { print(42); }", format="raw")
    assert out.buffer == [42]
    assert out.as_string() == "42"


def test_print_multiple_ints_raw():
    out = _run("fun main() { print(42); print(100); }", format="raw")
    assert out.buffer == [42, 100]
    assert out.as_string() == "42 100"


def test_print_string_with_newline():
    out = _run('fun main() { print("ab\n"); }', format="string")
    assert out.as_string() == "ab\n"


def test_print_int_string_format_renders_as_chars():
    out = _run("fun main() { print(65); print(66); }", format="string")
    assert out.buffer == [65, 66]
    assert out.as_string() == "AB"


def test_print_mixed_string_and_int():
    out = _run('fun main() { print("x="); print(7); }', format="raw")
    assert out.buffer == [ord("x"), ord("="), 7]
    assert out.as_string() == "120 61 7"
