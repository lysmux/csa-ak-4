"""End-to-end tests for the 64-bit `long` type through lexer -> analyzer -> codegen -> sim."""

from app.simulation.control_unit import ControlUnit, CUSnapshot
from app.simulation.data_path import DataPath
from app.simulation.memory import Memory
from app.simulation.runner import run_control_unit
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen
from app.translator.lexer import Lexer
from app.translator.parser import Parser

MASK64 = 0xFFFFFFFFFFFFFFFF


def run_source(src: str) -> CUSnapshot:
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    Analyzer().analyze(ast)
    program = CodeGen(output_devices={}).generate(ast)

    instr_mem = Memory(512)
    instr_mem.fill(program.instructions)
    data_mem = Memory(128)
    data_mem.fill(program.data)

    cu = ControlUnit(
        data_path=DataPath(memory=data_mem, stack=Stack(128), io_map={}),
        instr_memory=instr_mem,
        return_stack=Stack(128),
    )
    run_control_unit(cu, limit=200_000)
    return cu.snapshot


def read_long(snapshot: CUSnapshot, addr: int) -> int:
    return (snapshot.data_memory[addr + 1] << 32) | snapshot.data_memory[addr]


def _prog(body: str) -> str:
    return f"var r: long = 0;\nfun main(): int {{\n{body}\nreturn 0;\n}}\n"


def test_long_static_literal():
    # A long literal that does not fit in 32 bits is split across two cells.
    snapshot = run_source("var r: long = 5000000000;\nfun main(): int { return 0; }\n")
    assert read_long(snapshot, 0) == 5000000000


def test_long_assign_and_load():
    snapshot = run_source(_prog("var a: long = 9876543210;\nr = a;"))
    assert read_long(snapshot, 0) == 9876543210


def test_long_add():
    snapshot = run_source(_prog("var a: long = 5000000000;\nvar b: long = 1000000000;\nr = a + b;"))
    assert read_long(snapshot, 0) == 6000000000


def test_long_sub():
    snapshot = run_source(_prog("var a: long = 5000000000;\nvar b: long = 1000000000;\nr = a - b;"))
    assert read_long(snapshot, 0) == 4000000000


def test_long_mul():
    snapshot = run_source(_prog("var a: long = 100000;\nvar b: long = 100000;\nr = a * b;"))
    assert read_long(snapshot, 0) == 10000000000


def test_long_div():
    snapshot = run_source(_prog("var a: long = 10000000000;\nvar b: long = 100000;\nr = a / b;"))
    assert read_long(snapshot, 0) == 100000


def test_long_widen_int_literal():
    # `1` is an int literal widened to long at compile time.
    snapshot = run_source(_prog("var a: long = 5000000000;\nr = a + 1;"))
    assert read_long(snapshot, 0) == 5000000001


def test_long_widen_int_var_positive():
    # int variable widened to long via I2L at runtime.
    snapshot = run_source(_prog("var a: long = 5000000000;\nvar k: int = 7;\nr = a + k;"))
    assert read_long(snapshot, 0) == 5000000007


def test_long_widen_int_var_negative_sign_extend():
    # I2L must sign-extend: a + (-1) = a - 1.
    snapshot = run_source(_prog("var a: long = 5000000000;\nvar k: int = 0;\nk = k - 1;\nr = a + k;"))
    assert read_long(snapshot, 0) == 4999999999


def test_long_compare_greater_true():
    snapshot = run_source(
        _prog("var a: long = 5000000000;\nvar b: long = 3000000000;\nif (a > b) { r = 111; } else { r = 222; }")
    )
    assert read_long(snapshot, 0) == 111


def test_long_compare_greater_false():
    snapshot = run_source(
        _prog("var a: long = 1000000000;\nvar b: long = 3000000000;\nif (a > b) { r = 111; } else { r = 222; }")
    )
    assert read_long(snapshot, 0) == 222


def test_long_compare_equal():
    snapshot = run_source(
        _prog("var a: long = 8000000000;\nif (a == 8000000000) { r = 1; } else { r = 2; }")
    )
    assert read_long(snapshot, 0) == 1


def test_long_while_countdown():
    # Drive a while loop on a long counter down to zero.
    src = _prog(
        "var a: long = 5000000000;\n"
        "var n: long = 3;\n"
        "while (n > 0) {\n"
        "  a = a + 1000000000;\n"
        "  n = n - 1;\n"
        "}\n"
        "r = a;"
    )
    snapshot = run_source(src)
    assert read_long(snapshot, 0) == 8000000000
