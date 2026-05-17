import click

from app.isa.flag import Flag
from app.simulation.control_unit import ControlUnit


def format_flags(flags: Flag) -> str:
    items = [
        ("N", Flag.N),
        ("Z", Flag.Z),
        ("V", Flag.V),
        ("C", Flag.C),
    ]

    return " ".join(
        click.style(ch, fg="yellow", bold=True) if bit in flags else click.style("·", dim=True) for ch, bit in items
    )


def trace_var(name: str, value: str, *, color: str = "white") -> str:
    name = click.style(f"{name:>5}", bold=True, fg="cyan")
    value = click.style(value, fg=color)

    return f"{name}: {value}"


def trace_line(cu: ControlUnit) -> str:
    s = cu.snapshot
    instr = s.instruction

    parts = [
        trace_var("tick", f"{s.tick:6d}", color="green"),
        trace_var("state", f"{s.state.name:<10}", color="magenta"),
        trace_var("pc", f"0x{s.pc:04X}", color="yellow"),
        trace_var(
            "ir",
            f"{instr.opcode.name:<8} 0x{instr.operand:08X}",
            color="white",
        ),
        trace_var("flags", format_flags(s.flags)),
        trace_var("tos", f"0x{s.tos:08X}", color="green"),
        trace_var("nos", f"0x{s.nos:08X}", color="green"),
        trace_var("rtos", f"0x{s.r_tos:08X}", color="green"),
    ]

    return " │ ".join(parts)
