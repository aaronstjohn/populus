import os

import click

from populus.migrations.writer import (
    get_next_migration_number,
    write_empty_migration,
)
from populus.migrations.loading import (
    is_valid_migration_filename,
)

from .main import main


@main.command('makemigration')
@click.option(
    '--empty',
    '-e',
    is_flag=True,
    default=False,
    help="Write an empty migration file",
)
@click.argument('migration_name', required=False)
@click.pass_context
def make_migration(ctx, empty, migration_name):
    """
    Generate an empty migration.
    """
    if not empty:
        ctx.fail((
            "Creation of non-empty migrations is currently not supported. "
            "Please rerun with `--empty`."
        ))

    project = ctx.obj['PROJECT']

    next_migration_number = get_next_migration_number(project.project_dir)

    if migration_name is None:
        if next_migration_number == 1:
            migration_name = 'initial'
        else:
            migration_name = 'auto'

    migration_id = "{num:04d}_{migration_name}".format(
        num=next_migration_number,
        migration_name=migration_name,
    )

    migration_filename = "{migration_id}.py".format(migration_id=migration_id)

    if not is_valid_migration_filename(migration_filename):
        ctx.fail(
            "Migration filenames may only contain letters, numbers, and "
            "underscores: {0!r}".format(migration_filename)
        )

    migration_file_path = os.path.join(project.migrations_dir, migration_filename)
    if os.path.exists(migration_file_path):
        ctx.fail((
            "Unexpectedly found duplicate migration name: {0}".format(
                os.path.abspath(migration_file_path),
            )
        ))

    compiled_contracts = project.compiled_contracts

    with open(migration_file_path, 'w') as file_obj:
        write_empty_migration(file_obj, migration_id, compiled_contracts)

    click.echo(
        "Wrote new migration to: {0}".format(os.path.relpath(
            migration_file_path, project.project_dir,
        ))
    )