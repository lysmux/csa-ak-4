from collections.abc import Callable
from pathlib import Path
from typing import Self

import click

_INDENT_SIZE = 4


class Output:
    def __init__(self) -> None:
        self._started = False

    def section(self, title: str) -> Self:
        if self._started:
            click.echo()
        self._started = True
        click.echo(click.style(title, bold=True, fg="blue"))
        return self

    def line(self, content: str) -> Self:
        click.echo(" " * _INDENT_SIZE + content)
        return self

    def table(
        self,
        rows: list[tuple[str, str]],
        *,
        key_fmt: Callable[[str], str] = str,
        val_fmt: Callable[[str], str] = str,
    ) -> Self:
        width = max(len(k) for k, _ in rows)
        for key, val in rows:
            self.line(f"{key_fmt(key.ljust(width))} │ {val_fmt(val)}")
        return self


ReadableFile = click.Path(
    exists=True,
    resolve_path=True,
    dir_okay=False,
    readable=True,
    path_type=Path,
)
WritableFile = click.Path(
    resolve_path=True,
    dir_okay=False,
    writable=True,
    path_type=Path,
)
