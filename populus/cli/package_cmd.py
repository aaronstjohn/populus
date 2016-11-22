import click
import json
import os
import functools

import ipfsapi

from populus.utils.cli import (
    select_chain,
    select_project_contract,
    show_chain_sync_progress,
)
from populus.utils.ipfs import (
    create_ipfs_uri,
    is_ipfs_uri,
    extract_ipfs_path_from_uri,
)
from populus.utils.packaging import (
    enumerate_sources,
    get_chain_definition,
    get_chain_id,
    create_transaction_uri,
    create_block_uri,
    install_from_release_lock_file,
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
    ipfs_api = ipfsapi.connect('https://ipfs.infura.io', 5001)

    if not project.has_package_manifest:
        click.echo("No package manifest found in project.")
        ctx.exit(1)

    package_manifest = project.package_manifest
    # TODO: validate that the package manifest file is compliant with spec.

    package_manifest_uri = create_ipfs_uri(ipfs_api.add(project.package_manifest_path)['Hash'])

    # TODO: need to validate that a list of sources are present.
    source_file_paths = set(enumerate_sources(package_manifest['sources']))
    source_file_uris = {
        file_path: create_ipfs_uri(ipfs_api.add(file_path)['Hash'])
        for file_path in source_file_paths
    }

    include_any_contracts_msg = (
        "Does this release include any deployed contracts?"
    )
    release_contracts = {}

    if click.confirm(include_any_contracts_msg):
        # Determine which chain should be used.
        if not chain_name:
            chain_name = select_chain(project)

        with project.get_chain(chain_name) as chain:
            if wait_for_sync and chain_name in {'mainnet', 'morden'}:
                show_chain_sync_progress(chain)

            web3 = chain.web3
            chain_definition = [get_chain_definition(web3)]

            chain_id = get_chain_id(web3)

            # TODO: extract this to a helper.
            while True:
                contract_name = select_project_contract(project)
                contract_data = project.compiled_contracts[contract_name]

                raw_data = {
                    'contract_name': contract_name,
                }

                # TODO: ensure that this is not duplicated.
                contract_alias = click.prompt("Contract Alias", default=contract_name)

                if chain.has_registrar:
                    registrar = chain.registrar
                    keys_to_check = set([
                        'contract/{0}'.format(contract_name),
                        'contract/{0}'.format(contract_alias),
                    ])
                    for key in keys_to_check:
                        if not registrar.call().exists(key):
                            continue
                        address = registrar.call().getAddress(key)
                        # TODO: verify bytecode matches.
                        use_this_address_msg = (
                            "Would you like to use the existing deployed "
                            "instance @ {0} ?".format(address)
                        )
                        if click.confirm(use_this_address_msg, default=True):
                            raw_data['address'] = address
                            break

                if 'address' not in raw_data:
                    raw_data['address'] = click.prompt(
                        "Contract Address",
                        default='',
                    )

                raw_data['deploy_transaction'] = click.prompt(
                    'Deploy Transaction Hash',
                    value_proc=functools.partial(create_transaction_uri, chain_id),
                    default='',
                )
                raw_data['deploy_block'] = click.prompt(
                    'Deploy Block Hash',
                    value_proc=functools.partial(create_block_uri, chain_id),
                    default='',
                )
                raw_data['natspec'] = dict(
                    **contract_data.get('userdoc', {}),
                    **contract_data.get('devdoc', {})
                )

                # TODO: verify that the contract at this address matches this bytecode.
                raw_data['bytecode'] = contract_data['code']
                raw_data['runtime_bytecode'] = contract_data['code_runtime']

                # TODO: real validation/normalization
                contract_instance_data = {
                    key: value
                    for key, value
                    in raw_data.items()
                    if value
                }
                release_contracts[contract_alias] = contract_instance_data

                if click.confirm('Add another contract?', default=False):
                    continue
                else:
                    break
    else:
        chain_definition = None

    raw_release_lock_data = {
        'lock_file_version': '1',
        'package_manifest': package_manifest_uri,
        'version': package_manifest['version'],
        'license': package_manifest['license'],
        'sources': source_file_uris,
        'chain': chain_definition,
        'contracts': release_contracts,
        'build_dependencies': {},  # TODO: pull from populus.lock
    }

    release_lock_data = {
        key: value
        for key, value
        in raw_release_lock_data.items()
        if value
    }

    # TODO: don't overwrite existing file
    outfile_path = os.path.join(
        project.project_dir,
        '{0}.json'.format(package_manifest['version']),
    )
    with open(outfile_path, 'w') as release_lock_file:
        json.dump(release_lock_data, release_lock_file, sort_keys=True, indent=2)

    click.echo("Wrote release lock file: {0}".format(outfile_path))


@package_cmd.command('install')
@click.argument('packages', nargs=-1)
@click.option('--save/--no-save', default=True, help="Save package into manifest dependencies")
@click.pass_context
def package_install(ctx, packages, save):
    """
    Install a package.

    1. Load package manifest.
    """
    project = ctx.obj['PROJECT']

    ipfs_api = ipfsapi.connect('https://ipfs.infura.io', 5001)

    for package_identifier in packages:
        if is_ipfs_uri(package_identifier):
            ipfs_path = extract_ipfs_path_from_uri(package_identifier)
            lockfile_contents = ipfs_api.cat(ipfs_path)
            release_lockfile = json.loads(lockfile_contents)
            # TODO: validate that it is in valid lockfile format.
            install_from_release_lock_file(project, release_lockfile)
