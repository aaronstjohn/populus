import os
import glob
from urllib import parse

from web3.utils.formatting import (
    remove_0x_prefix,
)

from .types import (
    is_integer,
)
from .filesystem import (
    recursive_find_files,
)


PACKAGE_MANIFEST_FILENAME = 'epm.json'


def get_package_manifest_path(project_dir):
    return os.path.join(project_dir, PACKAGE_MANIFEST_FILENAME)


def create_BIP122_uri(chain_id, resource_type, resource_identifier):
    """
    See: https://github.com/bitcoin/bips/blob/master/bip-0122.mediawiki
    """
    return parse.urlunsplit([
        'blockchain',
        chain_id,
        "{0}/{1}".format(resource_type, resource_identifier),
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


def install_from_release_lock_file(project, release_lockfile):
    """
    * Ensure `./installed_contracts` exists.
    * Extract `package_name` from `release_lockfile.package_manifest.package_name`
    * Ensure `./installed_contracts/<package_name>` exists
    * Enumerate the contract source files.
    * Write the source file contents to the filesystem.
    """
