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


def make_link_regex(contract_name):
    """
    Returns a regex that will match embedded link references within a
    contract's bytecode.
    """
    return re.compile(
        contract_name[:36].ljust(38, "_").rjust(40, "_")
    )


def expand_shortened_reference_name(name, full_names):
    """
    If a contract dependency has a name longer than 36 characters then the name
    is truncated in the compiled but unlinked bytecode.  This maps a name to
    it's full name.
    """
    if name in full_names:
        return name

    candidates = [
        n for n in full_names if n.startswith(name)
    ]
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        raise ValueError(
            "Multiple candidates found trying to expand '{0}'.  Found '{1}'. "
            "Searched '{2}'".format(
                name,
                ','.join(candidates),
                ','.join(full_names),
            )
        )
    else:
        raise ValueError(
            "Unable to expand '{0}'. "
            "Searched '{1}'".format(
                name,
                ','.join(full_names),
            )
        )


def link_bytecode(bytecode, **dependencies):
    """
    Given the bytecode for a contract, and it's dependencies in the form of
    {contract_name: address} this functino returns the bytecode with all of the
    link references replaced with the dependency addresses.
    """
    linker_fn = compose(*(
        functools.partial(
            make_link_regex(name).sub,
            remove_0x_prefix(address),
        )
        for name, address in dependencies.items()
    ))
    linked_bytecode = linker_fn(bytecode)
    return linked_bytecode


def get_contract_library_dependencies(bytecode, full_contract_names=None):
    """
    Given a contract bytecode and an iterable of all of the known full names of
    contracts, returns a set of the contract names that this contract bytecode
    depends on.

    To get the full dependency graph use the `get_recursive_contract_dependencies`
    function.
    """
    expand_fn = functools.partial(
        expand_shortened_reference_name,
        full_names=full_contract_names,
    )
    return {
        expand_fn(name) for name in find_link_references(bytecode)
    }
