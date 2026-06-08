from app.isa.consts import INSTR_BYTES
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.control_unit import ControlUnit, CUSnapshot
from app.simulation.data_path import DataPath
from app.simulation.io import Device, Input, Output
from app.simulation.memory import DataMemory, InstrMemory
from app.simulation.runner import run_control_unit
from app.simulation.stack import DataStack, ReturnStack

from tests.shared import read_word

_IN_ADDR = 0x80  # memory-mapped input port (byte address)


def _run(
    instructions: list[Instruction],
    *,
    io_map: dict[int, Device] | None = None,
    vector_table: dict[int, int] | None = None,
    limit: int = 1000,
) -> CUSnapshot:
    instr_mem = InstrMemory(512)
    instr_mem.fill([i.to_binary() for i in instructions])
    data_mem = DataMemory(256)
    data_path = DataPath(memory=data_mem, stack=DataStack(64), io_map=io_map or {})
    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_mem,
        return_stack=ReturnStack(64),
        vector_table=vector_table or {},
    )
    run_control_unit(cu, limit=limit)
    return cu.snapshot


def addr(index: int) -> int:
    return index * INSTR_BYTES


# ---------------------------------------------------------------------------
# Device units
# ---------------------------------------------------------------------------


def test_output_raw_format():
    out = Output(mode="raw")
    out.write(65)
    out.write(66)
    assert out.buffer == [65, 66]
    assert out.as_string() == "65 66"


def test_output_string_format():
    out = Output(mode="string")
    out.write(ord("H"))
    out.write(ord("i"))
    assert out.as_string() == "Hi"


def test_input_schedule_and_read_clears_port():
    dev = Input(schedule=[(3, "A")], vector=2)
    assert dev.tick(1) is None  # nothing scheduled yet
    assert dev.tick(3) == 2  # fires at tick 3, raises its vector
    assert dev.read() == ord("A")
    assert dev.read() == 0  # port cleared after a read


# ---------------------------------------------------------------------------
# Output device through STORE
# ---------------------------------------------------------------------------


def test_store_routes_to_output_device():
    out = Output(mode="raw")
    instructions = [
        Instruction(Opcode.PUSH, 0x41),
        Instruction(Opcode.STORE, _IN_ADDR),
        Instruction(Opcode.PUSH, 0x42),
        Instruction(Opcode.STORE, _IN_ADDR),
        Instruction(Opcode.HALT),
    ]
    _run(instructions, io_map={_IN_ADDR: out})
    assert out.buffer == [0x41, 0x42]


# ---------------------------------------------------------------------------
# Interrupts: EI enables, the handler runs and RTI returns
# ---------------------------------------------------------------------------


# Shared layout:
#   0: EI / 1: DI(optional) / NOP padding / HALT
#   handler: LOAD input ; STORE M[0] ; RTI
def _interrupt_program(*, disable: bool) -> tuple[list[Instruction], int]:
    main = [Instruction(Opcode.EI)]
    if disable:
        main.append(Instruction(Opcode.DI))
    main += [Instruction(Opcode.NOP) for _ in range(12)]
    main.append(Instruction(Opcode.HALT))
    handler_index = len(main)
    handler = [
        Instruction(Opcode.LOAD, _IN_ADDR),  # read the input port
        Instruction(Opcode.STORE, 0),  # M[0] = value
        Instruction(Opcode.RTI),
    ]
    return main + handler, handler_index


def test_ei_interrupt_runs_handler_and_rti_returns():
    program, handler_index = _interrupt_program(disable=False)
    dev = Input(schedule=[(3, 0x42)], vector=1)
    snapshot = _run(program, io_map={_IN_ADDR: dev}, vector_table={1: addr(handler_index)})
    # the handler read the port and stored it; RTI let the program reach HALT
    assert read_word(snapshot.data_memory, 0) == 0x42


def test_di_suppresses_interrupt():
    program, handler_index = _interrupt_program(disable=True)
    # Fire only after EI then DI have both executed, so DI has cleared IE by then.
    dev = Input(schedule=[(12, 0x42)], vector=1)
    snapshot = _run(program, io_map={_IN_ADDR: dev}, vector_table={1: addr(handler_index)})
    # interrupts disabled → handler never runs → M[0] stays 0
    assert read_word(snapshot.data_memory, 0) == 0
