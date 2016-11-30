import itertools
import os
import json

import toposort

from web3.utils.types import (
    is_string,
)

from .filesystem import (
    get_compiled_contracts_file_path,
)
from .linking import (
    find_link_references,
)


def package_contracts(contract_classes):
    _dict = {
        '__len__': lambda s: len(contract_classes),
        '__iter__': lambda s: iter(contract_classes.items()),
        '__contains__': lambda s, k: contract_classes.__contains__(k),
        '__getitem__': lambda s, k: contract_classes.__getitem__(k),
        '__setitem__': lambda s, k, v: contract_classes.__setitem__(k, v),
        'keys': lambda s: contract_classes.keys(),
        'values': lambda s: contract_classes.values(),
    }
    _dict.update(contract_classes)

    return type('contracts', (object,), _dict)()


def construct_contract_factories(web3, contracts):
    constructor_kwargs = {
        contract_name: {
            'code': contract_data.get('code'),
            'code_runtime': contract_data.get('code_runtime'),
            'abi': contract_data.get('abi'),
            'source': contract_data.get('source'),
            'address': contract_data.get('address'),
        } for contract_name, contract_data in contracts.items()
    }
    contract_classes = {
        name: web3.eth.contract(**contract_data)
        for name, contract_data in constructor_kwargs.items()
    }
    return package_contracts(contract_classes)


def load_compiled_contract_json(project_dir):
    compiled_contracts_path = get_compiled_contracts_file_path(project_dir)

    if not os.path.exists(compiled_contracts_path):
        raise ValueError("No compiled contracts found")

    with open(compiled_contracts_path) as contracts_file:
        contracts = json.loads(contracts_file.read())

    return contracts


def get_shallow_dependency_graph(contracts):
    """
    Given a dictionary of compiled contract data, this returns a *shallow*
    dependency graph of each contracts explicit link dependencies.
    """
    link_dependencies = {
        contract_name: set(ref['full_name'] for ref in find_link_references(
            contract_data['code'],
            contracts.keys(),
        ))
        for contract_name, contract_data
        in contracts.items()
        if is_string(contract_data.get('code'))
    }
    return link_dependencies


def get_contract_deploy_order(dependency_graph):
    """
    Given a dictionary that maps contract names to their link dependencies,
    determine the overall dependency ordering for that set of contracts.
    """
    return toposort.toposort_flatten(dependency_graph)


def get_recursive_contract_dependencies(contract_name, dependency_graph):
    """
    Recursive computation of the linker dependencies for a specific contract
    within a contract dependency graph.
    """
    direct_dependencies = dependency_graph.get(contract_name, set())
    sub_dependencies = itertools.chain.from_iterable((
        get_recursive_contract_dependencies(dep, dependency_graph)
        for dep in direct_dependencies
    ))
    return set(itertools.chain(direct_dependencies, sub_dependencies))
