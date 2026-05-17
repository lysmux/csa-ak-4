import pytest
from app.config import InputDeviceConfig
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import Device, Input, Output
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer, SemanticError
from app.translator.codegen import CodeGen, CodeGenError
from app.translator.lexer import Lexer
from app.translator.parser import Parser

OUT_ADDR = 0x222
KEYBOARD_ADDR = 0x223
DEBUG_IN_ADDR = 0x225

INPUTS: dict[str, InputDeviceConfig] = {
    "keyboard": InputDeviceConfig(address=KEYBOARD_ADDR, vector=0),
    "debug_input": InputDeviceConfig(address=DEBUG_IN_ADDR, vector=1),
}


def _compile(
        src: str,
        inputs: dict[str, InputDeviceConfig] = INPUTS,
):
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(input_devices=set(inputs)).analyze(ast)
    return CodeGen(output_address=OUT_ADDR, input_devices=inputs).generate(ast)


def _run(src: str, schedules: dict[int, list[tuple[int, str]]] | None = None,
         limit: int = 2000) -> str:
    program = _compile(src)
    instr_mem = Memory(2000)
    instr_mem.fill(program.instructions)
    data_mem = Memory(2000)
    data_mem.fill(program.data)
    return_stack = Stack(2000)
    data_stack = Stack(2000)

    output = Output(format="string")
    keyboard = Input(schedule=(schedules or {}).get(KEYBOARD_ADDR, []), vector=0)
    debug_input = Input(schedule=(schedules or {}).get(DEBUG_IN_ADDR, []), vector=1)
    io_map: dict[int, Device] = {
        OUT_ADDR: output,
        KEYBOARD_ADDR: keyboard,
        DEBUG_IN_ADDR: debug_input,
    }
    data_path = DataPath(memory=data_mem, stack=data_stack, io_map=io_map)
    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_mem,
        return_stack=return_stack,
        vector_table=dict(program.interrupt_handlers),
    )
    cu.run(limit=limit)
    return output.as_string()


# ---------------------------------------------------------------------------
# Codegen: address resolution
# ---------------------------------------------------------------------------

def test_read_in_handler_uses_vector_device():
    """read() inside interrupt 0 reads from device with vector=0 (keyboard)."""
    out = _run(
        """
        interrupt 0 on_input() { print(read()); }
        fun main() { enable_interrupts(); while (true) {} }
        """,
        schedules={KEYBOARD_ADDR: [(10, "x"), (50, "y")]},
        limit=2000,
    )
    assert "x" in out
    assert "y" in out


def test_read_with_explicit_label():
    """read(debug_input) inside interrupt 0 reads from debug_input (vector 1)."""
    out = _run(
        """
        interrupt 0 on_input() { print(read(debug_input)); }
        fun main() { enable_interrupts(); while (true) {} }
        """,
        schedules={
            KEYBOARD_ADDR: [(10, "k")],
            DEBUG_IN_ADDR: [(10, "d")],
        },
        limit=2000,
    )
    # Handler reads from debug_input regardless of which device raised IRQ.
    assert "d" in out


# ---------------------------------------------------------------------------
# Analyzer errors
# ---------------------------------------------------------------------------

def test_read_without_label_outside_handler_raises():
    with pytest.raises(SemanticError, match="read"):
        _compile("fun main() { var c: int = read(); }")


def test_read_with_unknown_label_raises():
    with pytest.raises(SemanticError, match="not an input device"):
        _compile(
            """
            interrupt 0 on_input() { print(read(no_such_input)); }
            fun main() { while (true) {} }
            """,
        )


def test_input_label_as_value_raises():
    with pytest.raises(SemanticError, match="input device label 'keyboard'"):
        _compile("fun main() { var x: int = keyboard; }")


# ---------------------------------------------------------------------------
# Codegen errors
# ---------------------------------------------------------------------------

def test_read_in_handler_with_no_matching_input_raises():
    """Interrupt vector 7 has no input device → CodeGenError."""
    with pytest.raises(CodeGenError, match="no input device configured for interrupt vector 7"):
        _compile(
            """
            interrupt 7 on_x() { print(read()); }
            fun main() { while (true) {} }
            """,
        )


def test_codegen_with_no_input_devices_outside_handler():
    """No input devices configured, read() inside handler still wants one."""
    with pytest.raises(CodeGenError, match="no input device"):
        tokens = Lexer(
            """
            interrupt 0 h() { print(read()); }
            fun main() { while (true) {} }
            """
        ).tokenize()
        ast = Parser(tokens).parse()
        Analyzer().analyze(ast)
        CodeGen(
            output_address=OUT_ADDR,
            input_devices={},
        ).generate(ast)
