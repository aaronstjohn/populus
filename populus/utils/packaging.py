import os
from urllib import parse

from web3.utils.formatting import (
    remove_0x_prefix,
)

from .types import (
    is_integer,
)


PACKAGE_MANIFEST_FILENAME = 'epm.json'


def get_package_manifest_path(project_dir):
    return os.path.join(project_dir, PACKAGE_MANIFEST_FILENAME)


def create_block_uri(chain_id, block_identifier):
    """
    See: https://github.com/bitcoin/bips/blob/master/bip-0122.mediawiki
    """
    if is_integer(block_identifier):
        path_part = 'block/{0}'.format(str(block_identifier))
    else:
        path_part = 'block/{0}'.format(remove_0x_prefix(block_identifier))

    return parse.urlunsplit([
        'blockchain',
        chain_id,
        path_part,
        '',
        '',
    ])


def get_chain_definition(web3):
    chain_id = web3.eth.getBlock(0)['hash']
    latest_block_hash = web3.eth.getBlock('latest')['hash']

    return create_block_uri(chain_id, latest_block_hash)
