import click
from app.cli.trace import trace_line
from app.config import Config, InputDeviceConfig, OutputDeviceConfig
from app.simulation.control_unit import ControlUnit
from app.simulation.runner import SimulationResult, simulate
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, CompiledProgram
from app.translator.lexer import Lexer
from app.translator.nodes import Program
from app.translator.parser import Parser

from tests.golden.schema import GoldenInput, GoldenSnapshot, GoldenTrace


def compile_source(
    src: str,
    output_devices: dict[str, OutputDeviceConfig] | None = None,
    input_devices: dict[str, InputDeviceConfig] | None = None,
) -> tuple[Program, CompiledProgram]:
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()

    Analyzer(
        output_devices=set(output_devices or {}),
        input_devices=set(input_devices or {}),
    ).analyze(ast)

    program = CodeGen(
        output_devices=output_devices or {},
        input_devices=input_devices or {},
    ).generate(ast)

    return ast, program


def run_golden(
    program: CompiledProgram,
    config: Config,
    max_trace: int,
) -> tuple[SimulationResult, list[str]]:
    trace: list[str] = []

    def on_tick(cu: ControlUnit) -> None:
        if len(trace) < max_trace:
            trace.append(click.unstyle(trace_line(cu)))

    result = simulate(program, config, on_tick=on_tick)
    return result, trace


def run_and_snapshot(input_: GoldenInput) -> GoldenSnapshot:
    ast, prog = compile_source(input_.source, input_.config.io.outputs, input_.config.io.inputs)
    result, trace = run_golden(prog, input_.config, max_trace=input_.max_trace)

    return GoldenSnapshot(
        output=result.outputs,
        ast=str(ast),
        machine_code=str(prog),
        trace=GoldenTrace(total_ticks=result.ticks, lines="\n".join(trace)),
    )
