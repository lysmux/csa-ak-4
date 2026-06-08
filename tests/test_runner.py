from app.config import Config, IOConfig, OutputDeviceConfig
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.simulation.control_unit import ControlUnit
from app.simulation.runner import SimulationResult, StopReason, simulate
from app.translator.codegen import CompiledProgram

_OUT_ADDR = 0x222


def _config(limit: int = 1000) -> Config:
    return Config(
        limit=limit,
        io=IOConfig(outputs={"out": OutputDeviceConfig(address=_OUT_ADDR, mode="raw", default=True)}),
    )


def test_simulate_halts_and_collects_output():
    program = CompiledProgram(
        instructions=[
            Instruction(Opcode.PUSH, 65).to_binary(),
            Instruction(Opcode.STORE, _OUT_ADDR).to_binary(),
            Instruction(Opcode.HALT).to_binary(),
        ],
        data=[],
        interrupt_handlers={},
    )
    result = simulate(program, _config())

    assert isinstance(result, SimulationResult)
    assert result.stop_reason is StopReason.HALT
    assert result.outputs["out"] == "65"
    assert result.ticks > 0


def test_simulate_hits_tick_limit():
    program = CompiledProgram(
        instructions=[Instruction(Opcode.JMP, 0).to_binary()],  # infinite self-loop
        data=[],
        interrupt_handlers={},
    )
    result = simulate(program, _config(limit=50))

    assert result.stop_reason is StopReason.TICK_LIMIT


def test_simulate_invokes_on_tick():
    program = CompiledProgram(
        instructions=[Instruction(Opcode.HALT).to_binary()],
        data=[],
        interrupt_handlers={},
    )
    ticks: list[int] = []

    def on_tick(cu: ControlUnit) -> None:
        ticks.append(cu.current_tick)

    simulate(program, _config(), on_tick=on_tick)

    assert ticks  # callback fired at least once
    assert ticks == sorted(ticks)  # monotonically increasing tick count
