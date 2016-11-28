import re
import functools

from web3.utils.formatting import (
    remove_0x_prefix,
)
from web3.utils.string import (
    coerce_args_to_text,
)

from .functional import (
    cast_return_to_tuple,
    compose,
)


DEPENDENCY_RE = (
    '__'  # Prefixed by double underscore
    '[a-zA-Z_]'  # First letter must be alpha or underscore
    '[a-zA-Z0-9_]{0,59}?'  # Intermediate letters
    '_{0,59}'
    '__'  # End with a double underscore
)


@cast_return_to_tuple
@coerce_args_to_text
def find_link_references(bytecode):
    """
    Given bytecode, this will return all of the linked references from within
    the bytecode.
    """
    unprefixed_bytecode = remove_0x_prefix(bytecode)

    link_references = tuple((
        {
            'name': match.group().strip('_'),
            'offset': match.start(),
            'length': match.end() - match.start(),
        } for match in re.finditer(DEPENDENCY_RE, unprefixed_bytecode)
    ))

    return link_references


def expand_shortened_reference_name(short_name, all_full_names):
    """
    Link references whos names are longer than their bytecode representations
    will get truncated to 4 characters short of their full name because of the
    double underscore prefix and suffix.

    This expands `short_name` to it's full name or raise a value error if it is
    unable to find an appropriate expansion.
    """
    if short_name in all_full_names:
        return short_name

    candidates = [
        full_name for full_name in all_full_names if full_name.startswith(short_name)
    ]
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        raise ValueError(
            "Multiple candidates found trying to expand '{0}'.  Found '{1}'. "
            "Searched '{2}'".format(
                short_name,
                ','.join(candidates),
                ','.join(all_full_names),
            )
        )
    else:
        raise ValueError(
            "Unable to expand '{0}'. "
            "Searched '{1}'".format(
                short_name,
                ','.join(all_full_names),
            )
        )


def make_link_regex(contract_name, length=40):
    """
    Returns a regex that will match embedded link references within a
    contract's bytecode.
    """
    name_trunc = length - 4
    left_justify = length - 2

    link_regex = re.compile(
        contract_name[:name_trunc].ljust(left_justify, "_").rjust(length, "_")
    )
    return link_regex


def link_bytecode(bytecode, **link_values):
    """
    Given the bytecode for a contract, and it's dependencies in the form of
    {contract_name: address} this functino returns the bytecode with all of the
    link references replaced with the dependency addresses.
    """
    linker_fn = compose(*(
        functools.partial(
            make_link_regex(name).sub,
            remove_0x_prefix(value),
        )
        for name, value in link_values.items()
    ))
    linked_bytecode = linker_fn(bytecode)
    return linked_bytecode


def extract_link_reference_names(bytecode, full_contract_names=None):
    """
    Given a contract bytecode and an iterable of all of the known full names of
    contracts, returns a set of the contract names that this contract bytecode
    depends on.

    To get the full dependency graph use the `get_recursive_contract_dependencies`
    function.
    """
    expand_fn = functools.partial(
        expand_shortened_reference_name,
        all_full_names=full_contract_names,
    )
    return {
        expand_fn(name) for name in find_link_references(bytecode)
    }
