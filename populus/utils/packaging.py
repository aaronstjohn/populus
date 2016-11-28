import os
import re
import glob
import json
from urllib import parse

from web3.utils.types import (
    is_object,
)
from web3.utils.string import (
    force_text,
)
from web3.utils.formatting import (
    remove_0x_prefix,
)

from .ipfs import (
    is_ipfs_uri,
    extract_ipfs_path_from_uri,
    walk_ipfs_tree,
)
from .types import (
    is_integer,
)
from .filesystem import (
    recursive_find_files,
    ensure_path_exists,
)
from .functional import (
    cast_return_to_tuple,
)


PACKAGE_MANIFEST_FILENAME = 'epm.json'


def get_package_manifest_path(project_dir):
    return os.path.join(project_dir, PACKAGE_MANIFEST_FILENAME)


INSTALLED_PACKAGES_ROOT_DIRNAME = 'installed_packages'


def get_installed_packages_root_dir(project_dir):
    return os.path.join(project_dir, INSTALLED_PACKAGES_ROOT_DIRNAME)


def get_installed_packages_dir(project_dir, chain_name):
    installed_packages_root = get_installed_packages_root_dir(project_dir)
    return os.path.join(installed_packages_root, chain_name)


@cast_return_to_tuple
def find_installed_package_source_files(installed_packages_dir):
    # TODO: this should not recurse into nested `./installed_packages` directories.
    return (
        os.path.relpath(source_path)
        for source_path
        in recursive_find_files(installed_packages_dir, '*.sol')
    )


CHAIN_LOCKFILE_FILENAME = 'populus.lock'


def get_chain_lockfile_path(project_dir, chain_name):
    installed_contracts_dir = get_installed_packages_dir(project_dir, chain_name)
    return os.path.join(installed_contracts_dir, CHAIN_LOCKFILE_FILENAME)


def create_BIP122_uri(chain_id, resource_type, resource_identifier):
    """
    See: https://github.com/bitcoin/bips/blob/master/bip-0122.mediawiki
    """
    return parse.urlunsplit([
        'blockchain',
        remove_0x_prefix(chain_id),
        "{0}/{1}".format(resource_type, remove_0x_prefix(resource_identifier)),
        '',
        '',
    ])


def create_block_uri(chain_id, block_identifier):
    if is_integer(block_identifier):
        return create_BIP122_uri(chain_id, 'block', str(block_identifier))
    else:
        return create_BIP122_uri(chain_id, 'block', remove_0x_prefix(block_identifier))


def create_transaction_uri(chain_id, transaction_hash):
    return create_BIP122_uri(chain_id, 'transaction', transaction_hash)


def get_chain_id(web3):
    return web3.eth.getBlock(0)['hash']


def get_chain_definition(web3):
    """
    Return the blockchain URI that
    """
    chain_id = get_chain_id(web3)
    latest_block_hash = web3.eth.getBlock('latest')['hash']

    return create_block_uri(chain_id, latest_block_hash)


def parse_BIP122_uri(blockchain_uri):
    parse_result = parse.urlparse(blockchain_uri)

    if parse_result.netloc:
        if parse_result.path:
            return ''.join((parse_result.netloc, parse_result.path))
        else:
            return parse_result.netloc
    else:
        return parse_result.path.lstrip('/')


def check_if_chain_matches_chain_uris(web3, *chain_uris):
    pass


def enumerate_sources(source_paths_or_globs):
    """
    Given a list of strings that are expected be either filesystem paths or
    glob patterns generate all source files defined by these paths.

    1. If it exists on the filesystem.
        1A. If it's a file, return the file
        1B. If it's a directory, recursively search the directory for files.
    3. If it isn't on the filesystem assume it is a glob pattern and return all
       the matched files.
    """
    for path_or_glob in source_paths_or_globs:
        if os.path.exists(path_or_glob):
            if os.path.isdir(path_or_glob):
                for file_path in recursive_find_files(path_or_glob, '*.sol'):
                    yield file_path
            else:
                yield path_or_glob
        else:
            for file_path in glob.glob(path_or_glob):
                yield file_path


def create_contract_instance_object(contract_name,
                                    address=None,
                                    deploy_transaction=None,
                                    deploy_block=None,
                                    contract_data=None,
                                    link_dependencies=None):
    if contract_data is None:
        contract_data = {}

    contract_instance_data = {
        'contract_name': contract_name,
    }

    if 'bytecode' in contract_data:
        contract_instance_data['bytecode'] = contract_data['bytecode']
    if 'runtime_bytecode' in contract_data:
        contract_instance_data['runtime_bytecode'] = contract_data['runtime_bytecode']
    if 'abi' in contract_data:
        contract_instance_data['abi'] = contract_data['abi']
    if 'natspec' in contract_data:
        contract_instance_data['natspec'] = contract_data['natspec']

    if 'compiler' in contract_data:
        contract_instance_data['compiler'] = contract_data['compiler']
    elif 'bytecode' in contract_instance_data or 'runtime_bytecode' in contract_instance_data:
        raise ValueError(
            'Compiler information must be specified if either bytecode or '
            'runtime bytecode are included'
        )

    if link_dependencies:
        # TODO: this needs to be massaged into the correct format.
        contract_instance_data['link_dependencies'] = link_dependencies

    return contract_instance_data


CONTRACT_NAME_REGEX = '^[_a-zA-Z][_a-zA-Z0-9]*$'


def is_valid_contract_name(value):
    return bool(re.match(CONTRACT_NAME_REGEX, value))


def extract_package_manifest_from_lockfile(ipfs_client, release_lockfile):
    if is_object(release_lockfile['package_manifest']):
        return release_lockfile['package_manifest']
    elif is_ipfs_uri(release_lockfile['package_manifest']):
        package_manifest_ipfs_path = extract_ipfs_path_from_uri(
            release_lockfile['package_manifest'],
        )
        return json.loads(force_text(ipfs_client.cat(
            package_manifest_ipfs_path
        )))
    else:
        raise ValueError("Unsupported format: {0}".format(release_lockfile['package_manifest']))


def resolve_package_identifier(project, package_identifier):
    if is_ipfs_uri(package_identifier):
        ipfs_path = extract_ipfs_path_from_uri(package_identifier)
        lockfile_contents = project.ipfs_client.cat(ipfs_path)
        release_lockfile = json.loads(force_text(lockfile_contents))
        package_manifest = extract_package_manifest_from_lockfile(
            project.ipfs_client,
            release_lockfile,
        )
        package_name = package_manifest['package_name']
        return package_name, package_manifest, release_lockfile
    else:
        raise ValueError("Unsupported identifier: {0}".format(package_identifier))


def install_single_package(project, install_path, release_lockfile):
    """
    * Ensure `./installed_contracts` exists.
    * Extract `package_name` from `release_lockfile.package_manifest.package_name`
    * Ensure `./installed_contracts/<package_name>` exists
    * Something Something Dependencies....
    * Enumerate the contract source files.
    * Write the source file contents to the filesystem.
    """
    ensure_path_exists(project.installed_contracts_dir)
    ipfs_client = project.ipfs_client

    # TODO: what to do if this path already exists...
    if os.path.exists(install_path):
        raise ValueError("No support yet for installing over something that was previously there")
    package_source_tree = release_lockfile.get('sources', {})

    # TODO: ensure these paths are local and clean this nested insanity up.
    for source_path, source_value in package_source_tree.items():
        if not source_path.startswith('./'):
            raise ValueError('Unsupported key format: {0}'.format(source_path))

        source_base_path = os.path.join(install_path, source_path)

        if is_ipfs_uri(source_value):
            ipfs_path = extract_ipfs_path_from_uri(source_value)
            for file_path, ipfs_hash in walk_ipfs_tree(ipfs_client, ipfs_path, source_base_path):  # NOQA
                if os.path.exists(file_path):
                    raise ValueError('Not overwriting file @ {0}'.format(file_path))
                file_dir = os.path.dirname(file_path)
                ensure_path_exists(file_dir)

                with open(file_path, 'wb') as source_file:
                    source_file.write(ipfs_client.cat(ipfs_hash))
        else:
            if os.path.exists(source_base_path):
                raise ValueError('Not overwriting file @ {0}'.format(source_base_path))
            source_content = source_value
            with open(source_base_path, 'w') as source_file:
                source_file.write(source_content)
