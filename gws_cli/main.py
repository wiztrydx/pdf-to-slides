"""Main CLI entry point."""

import click

from gws_cli import __version__
from gws_cli.commands.drive import drive
from gws_cli.commands.slides import slides
from gws_cli.commands.gmail import gmail
from gws_cli.commands.docs import docs
from gws_cli.auth import logout


@click.group()
@click.version_option(version=__version__, prog_name="gws")
def cli():
    """Google Workspace CLI - manage Drive, Slides, Gmail, and Docs from the terminal."""


cli.add_command(drive)
cli.add_command(slides)
cli.add_command(gmail)
cli.add_command(docs)


@cli.command()
def auth_logout():
    """Remove stored OAuth credentials."""
    if logout():
        click.echo("Logged out successfully.")
    else:
        click.echo("No stored credentials found.")


if __name__ == "__main__":
    cli()
