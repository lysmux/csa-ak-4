import functools
from collections.abc import Callable
from typing import Never

import click
from pydantic import ValidationError


def error(header: str, detail: str | None = None) -> Never:
    click.echo(click.style(header, fg="red", bold=True), err=True)
    if detail:
        click.echo(detail, err=True)
    raise SystemExit(1)


def format_validation_error(e: ValidationError) -> str:
    lines = []
    for err in e.errors():
        loc = click.style(" -> ".join(str(p) for p in err["loc"]), fg="yellow")
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def error_wrap[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except ValidationError as e:
            error("Configuration error:", format_validation_error(e))
        except Exception as e:
            error(f"{type(e).__name__}: {e}")

    return wrapper
