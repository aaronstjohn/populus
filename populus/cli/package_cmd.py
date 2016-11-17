import click

from .main import main


@main.group('package')
@click.pass_context
def package_cmd(ctx):
    """
    Package management commands.
    """
    pass


@package_cmd.command('reset')
@click.pass_context
def package_init(ctx):
    """
    Initialize the `epm.json` file.
    """
