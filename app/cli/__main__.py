import click

from app.cli.commands.compile import compile
from app.cli.commands.run import run


@click.group()
def cli() -> None:
    pass


cli.add_command(compile)
cli.add_command(run)

if __name__ == "__main__":
    cli()
