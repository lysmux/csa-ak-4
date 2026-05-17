from __future__ import annotations

from functools import partial
from pathlib import Path

import click

from app import binary
from app.cli.errors import error_wrap
from app.cli.helpers import Output, ReadableFile, load_config
from app.cli.trace import trace_line
from app.simulation.control_unit import ControlUnit
from app.simulation.runner import simulate


@click.command()
@click.argument("file", type=ReadableFile)
@click.option("-c", "--config", "config_path", type=ReadableFile)
@click.option("--trace", is_flag=True, default=False, help="Print CPU state on every tick")
@error_wrap
def run(file: Path, config_path: Path | None, trace: bool) -> None:
    config = load_config(config_path)
    with file.open("rb") as f:
        program = binary.read(f)

    out = Output()

    on_tick = None
    if trace:
        out.section("Trace")

        def on_tick(unit: ControlUnit) -> None:
            out.line(trace_line(unit))

    result = simulate(program, config, on_tick=on_tick)

    out.section("Output")
    out.table(list(result.outputs.items()), key_fmt=partial(click.style, fg="cyan"))

    out.section("Summary").table(
        [
            ("stop reason:", result.stop_reason.value),
            ("ticks:", str(result.ticks)),
            ("time:", f"{result.wall_ms:.3f} ms"),
        ],
        key_fmt=partial(click.style, bold=True),
        val_fmt=partial(click.style, fg="yellow"),
    )
