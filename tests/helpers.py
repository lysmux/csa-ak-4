from collections import deque

from app.cli.trace import trace_line
from app.config import Config, InputDeviceConfig, OutputDeviceConfig
from app.simulation.control_unit import ControlUnit
from app.simulation.runner import SimulationResult, simulate
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, CompiledProgram
from app.translator.lexer import Lexer
from app.translator.nodes import Program
from app.translator.parser import Parser

from tests.schema import GoldenInput, GoldenSnapshot, GoldenTrace


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
    trace_window: int,
) -> tuple[SimulationResult, list[str]]:
    first: list[str] = []
    last: deque[str] = deque(maxlen=trace_window)
    trace_count = 0

    def on_tick(cu: ControlUnit) -> None:
        nonlocal trace_count
        line = trace_line(cu, styled=False)
        if trace_count < trace_window:
            first.append(line)
        else:
            last.append(line)
        trace_count += 1

    result = simulate(program, config, on_tick=on_tick)
    trace = first.copy()
    omitted = trace_count - len(first) - len(last)
    if omitted > 0:
        trace.append(f"... {omitted} tick(s) omitted ...")
    trace.extend(last)
    return result, trace


def run_and_snapshot(input_: GoldenInput) -> GoldenSnapshot:
    ast, prog = compile_source(input_.source, input_.config.io.outputs, input_.config.io.inputs)
    result, trace = run_golden(prog, input_.config, trace_window=input_.trace_window)

    return GoldenSnapshot(
        output=result.outputs,
        ast=str(ast),
        machine_code=str(prog),
        trace=GoldenTrace(total_ticks=result.ticks, lines="\n".join(trace)),
    )
