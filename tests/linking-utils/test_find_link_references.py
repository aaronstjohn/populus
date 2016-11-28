import pytest

from populus.utils.linking import find_link_references


@pytest.mark.parametrize(
    'bytecode,expected',
    (
        ('0x', tuple()),
        ('', tuple()),
        (
            '0x__NothingButLink__',
            (
                {
                    'name': 'NothingButLink',
                    'offset': 0,
                    'length': 18,
                },
            ),
        ),
        (
            '0xabcdef__MathLib_______________________________12345',
            (
                {
                    'name': 'MathLib',
                    'offset': 6,
                    'length': 40,
                },
            ),
        ),
        (
            '0xabcdef__Some32ByteValue_______________________________________________12345',
            (
                {
                    'name': 'Some32ByteValue',
                    'offset': 6,
                    'length': 64,
                },
            )
        ),
        (
            '0xabcdef__Close__12345__Together__abcdef',
            (
                {
                    'name': 'Close',
                    'offset': 6,
                    'length': 9,
                },
                {
                    'name': 'Together',
                    'offset': 20,
                    'length': 12,
                },
            )
        ),
    ),
)
def test_find_link_references(bytecode, expected):
    actual = find_link_references(bytecode)
    assert actual == expected
