from pathlib import Path

import click

from app import binary
from app.cli.errors import error_wrap
from app.cli.helpers import Output, ReadableFile, WritableFile
from app.config import Config
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, CompiledProgram
from app.translator.lexer import Lexer
from app.translator.parser import Parser


def compile_source(source: Path, config: Config) -> CompiledProgram:
    tokens = Lexer(source.read_text(encoding="utf-8")).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(
        output_devices=set(config.io.outputs),
        input_devices=set(config.io.inputs),
    ).analyze(ast)
    return CodeGen(
        output_devices=config.io.outputs,
        input_devices=config.io.inputs,
    ).generate(ast)


@click.command()
@click.argument("source", type=ReadableFile)
@click.argument("target", type=WritableFile)
@click.option("-c", "--config", "config_path", type=ReadableFile, required=True)
@click.option("--debug", "debug_path", type=WritableFile)
@error_wrap
def compile(
    source: Path,
    target: Path,
    config_path: Path,
    debug_path: Path | None,
) -> None:
    config = Config.from_yaml(config_path)
    program = compile_source(source, config)

    binary.write(target, program)

    debug_path = debug_path or target.with_suffix(".dbg")
    with debug_path.open("w", encoding="utf-8") as f:
        f.write(str(program))

    out = Output()
    out.section("Compiled")
    out.line(f"{click.style(str(source), fg='cyan')} -> {click.style(target.name, bold=True)}")
    out.section("Debug")
    out.line(click.style(debug_path.name, fg="yellow"))
