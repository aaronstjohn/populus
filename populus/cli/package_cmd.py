import click
import json
import os

from populus.utils.cli import (
    select_chain,
)

from .main import main


@main.group('package')
@click.pass_context
def package_cmd(ctx):
    """
    Package management commands.
    """
    pass


def split_on_commas(values):
    return [value.strip() for value in values.split(',') if value]


@package_cmd.command('init')
@click.pass_context
def package_init(ctx):
    """
    Initialize the `epm.json` file.
    """
    project = ctx.obj['PROJECT']

    if os.path.exists(project.package_manifest_path):
        overwrite_msg = "An `epm.json` file is already present. Overwrite it?"
        if not click.confirm(overwrite_msg, default=False):
            ctx.exit(1)

    raw_package_manifest = {
        'manifest_version': 1,
    }

    click.echo("Writing new epm.json file.")

    # TODO: pull from git configuration if present.
    raw_package_manifest['package_name'] = click.prompt(
        'Package Name',
        default='',
    )

    # TODO: pull from git configuration.
    raw_package_manifest['authors'] = click.prompt(
        'Author(s)',
        value_proc=split_on_commas,
        default='',
    )

    raw_package_manifest['version'] = click.prompt(
        'Version',
        default='1.0.0',
    )

    # TODO: auto detect this from a LICENSE file if present.
    raw_package_manifest['license'] = click.prompt(
        'License',
        default='MIT',
    )

    raw_package_manifest['description'] = click.prompt(
        'Description',
        default='',
    )

    # TODO: decide if these should be included.
    raw_package_manifest['keywords'] = click.prompt(
        'Keywords',
        value_proc=split_on_commas,
        default='',
    )

    raw_package_manifest['links'] = click.prompt(
        'Links',
        value_proc=split_on_commas,
        default='',
    )

    raw_package_manifest['sources'] = click.prompt(
        'Sources',
        value_proc=split_on_commas,
        default=['./contracts/*.sol', './contracts/**/*.sol'],
    )

    # TODO: pull these from the compiled sources.
    raw_package_manifest['contracts'] = click.prompt(
        'Contracts',
        value_proc=split_on_commas,
        default='',
    )

    package_manifest = {
        key: value
        for key, value
        in raw_package_manifest.items()
        if value
    }

    with open(project.package_manifest_path, 'w') as package_manifest_file:
        json.dump(package_manifest, package_manifest_file, sort_keys=True, indent=2)

    click.echo("Wrote package manifest: {0}".format(project.package_manifest_path))


@package_cmd.command('release')
@click.option(
    'chain_name',
    '--chain',
    '-c',
    help=(
        "Specifies the chain that this release is being created for."
    ),
)
@click.option('--wait-for-sync/--no-wait-for-sync', default=True)
@click.pass_context
def package_release(ctx, chain_name, wait_for_sync):
    """
    Create a release.

    1. Load package manifest.
    """
    project = ctx.obj['PROJECT']

    if not project.has_package_manifest:
        click.echo("No package manifest found in project.")
        ctx.exit(1)

    package_manifest = project.package_manifest
    # TODO: validate that the package manifest file is compliant with spec.

    # Determine which chain should be used.
    if not chain_name:
        chain_name = select_chain(project)

    with project.get_chain(chain_name) as chain:
        if wait_for_sync and chain_name in {'mainnet', 'morden'}:
            show_chain_sync_progress(chain)

        web3 = chain.web3
        chain_definition = get_chain_definition(web3)

    release_lock_data = {
        'lock_file_version': '1',
        'package_manifest': 'TODO',  # IPFS?
        'version': package_manifest['version'],  # direct from PM
        'license': package_manifest['license'],  # direct from PM
        'sources': 'TODO',  # IPFS?
        'chain': [chain_definition],
        'contracts': 'TODO',
        'build_dependencies': 'TODO',  # pull from populus.lock
    }
