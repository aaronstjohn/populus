import pytest

from populus.utils.packaging import create_block_uri


@pytest.mark.parametrize(
    'chain_id,block_identifier,expected_uri',
    (
        ('deadbeef', 0, 'blockchain://deadbeef/block/0'),
        ('deadbeef', 1, 'blockchain://deadbeef/block/1'),
        ('deadbeef', '1234567890abcdef', 'blockchain://deadbeef/block/1234567890abcdef'),
    )
)
def test_create_block_uri(chain_id, block_identifier, expected_uri):
    actual_uri = create_block_uri(chain_id, block_identifier)
    assert actual_uri == expected_uri
