import click

from app.debuger.debug import Debugger
from app.simulation.simulation import Mode


@click.command()
@click.option("--mode", "-m", default=Mode.DEFAULT, type=Mode)
def cli(mode: Mode) -> None:
    app = Debugger(mode=mode)
    app.run()


if __name__ == '__main__':
    cli()
