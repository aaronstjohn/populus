import os
import pytest

from populus.utils.filesystem import (
    remove_file_if_exists,
)
from populus.chain.exceptions import (
    NoKnownAddress,
    BytecodeMismatchError,
)
from populus.migrations import (
    Migration,
    DeployContract,
)
from populus.migrations.migration import (
    get_migration_classes_for_execution,
)
from populus.migrations.writer import (
    write_migration
)
from populus import Project


@pytest.yield_fixture()
def testrpc_chain(project_dir, write_project_file, MATH, LIBRARY_13, MULTIPLY_13):
    write_project_file('contracts/Math.sol', MATH['source'])
    write_project_file(
        'contracts/Multiply13.sol',
        '\n'.join((LIBRARY_13['source'], MULTIPLY_13['source'])),
    )

    project = Project()

    with project.get_chain('testrpc') as chain:
        assert 'Math' in chain.compiled_contracts
        assert 'Library13' in chain.compiled_contracts
        assert 'Multiply13' in chain.compiled_contracts

        yield chain


@pytest.fixture()
def with_math_v2(testrpc_chain, write_project_file, MATH_V2):
    chain = testrpc_chain

    prev_mtime = chain.get_source_modification_time()

    write_project_file('contracts/Math.sol', MATH_V2['source'])

    assert chain.get_source_modification_time() != prev_mtime
    assert 'Math' in chain.compiled_contracts


@pytest.fixture()
def library_13(testrpc_chain):
    chain= testrpc_chain
    web3 = chain.web3

    Library13 = chain.contract_factories.Library13

    library_deploy_txn_hash = Library13.deploy()
    library_deploy_txn = web3.eth.getTransaction(library_deploy_txn_hash)
    library_13_address = chain.wait.for_contract_address(library_deploy_txn_hash, timeout=30)

    assert library_deploy_txn['input'] == Library13.code
    assert web3.eth.getCode(library_13_address) == Library13.code_runtime

    return Library13(address=library_13_address)


@pytest.fixture()
def migration_0001(testrpc_chain, MATH):
    project = testrpc_chain.project
    migrations_dir = project.migrations_dir

    class Migration0001(Migration):
        migration_id = '0001_deploy_v1_math'
        dependencies = []
        operations = [
            DeployContract('Math'),
        ]
        compiled_contracts = {
            'Math': MATH,
        }
    migration_filename = os.path.join(migrations_dir, '0001_deploy_v1_math.py')

    with open(migration_filename, 'w') as migration_0001_file:
        write_migration(migration_0001_file, Migration0001)

    assert len(project.migrations) == 1

    migrations_to_execute = get_migration_classes_for_execution(
        project.migrations,
        testrpc_chain,
    )

    assert len(migrations_to_execute) == 1

    the_migration_instance = migrations_to_execute[0]
    the_migration_instance.execute()

    return Migration0001


@pytest.fixture()
def migration_0002(testrpc_chain, migration_0001, MATH_V2):
    project = testrpc_chain.project
    migrations_dir = project.migrations_dir

    class Migration0002(Migration):
        migration_id = '0002_deploy_v2_math'
        dependencies = ['0001_deploy_v1_math']
        operations = [
            DeployContract('Math'),
        ]
        compiled_contracts = {
            'Math': MATH_V2,
        }
    migration_filename = os.path.join(migrations_dir, '0002_deploy_v2_math.py')

    with open(migration_filename, 'w') as migration_0002_file:
        write_migration(migration_0002_file, Migration0002)

    assert len(project.migrations) == 2

    migrations_to_execute = get_migration_classes_for_execution(
        project.migrations,
        testrpc_chain,
    )

    assert len(migrations_to_execute) == 1

    the_migration_instance = migrations_to_execute[0]
    the_migration_instance.execute()

    return Migration0002


@pytest.fixture()
def migration_0003(testrpc_chain, migration_0002, MATH):
    project = testrpc_chain.project
    migrations_dir = project.migrations_dir

    class Migration0003(Migration):
        migration_id = '0003_deploy_alternate_math'
        dependencies = ['0002_deploy_v2_math']
        operations = [
            DeployContract('Math', contract_registrar_name='FancyMath'),
        ]
        compiled_contracts = {
            'Math': MATH,
        }
    migration_filename = os.path.join(migrations_dir, '0003_deploy_alternate_math.py')

    with open(migration_filename, 'w') as migration_0003_file:
        write_migration(migration_0003_file, Migration0003)

    assert len(project.migrations) == 3

    migrations_to_execute = get_migration_classes_for_execution(
        project.migrations,
        testrpc_chain,
    )

    assert len(migrations_to_execute) == 1

    the_migration_instance = migrations_to_execute[0]
    the_migration_instance.execute()

    return Migration0003


def test_get_contract_factory_with_no_dependencies(testrpc_chain):
    chain = testrpc_chain

    MATH = chain.compiled_contracts['Math']
    Math = chain.get_contract_factory('Math')

    assert Math.code == MATH['code']
    assert Math.code_runtime == MATH['code_runtime']


def test_get_contract_factory_with_missing_dependency(testrpc_chain):
    chain = testrpc_chain

    with pytest.raises(NoKnownAddress):
        Multiply13 = chain.get_contract_factory('Multiply13')



def test_get_contract_factory_with_declared_dependency(testrpc_chain):
    chain = testrpc_chain

    MULTIPLY_13 = chain.compiled_contracts['Multiply13']
    Multiply13 = chain.get_contract_factory(
        'Multiply13',
        link_dependencies={
            'Library13': '0xd3cda913deb6f67967b99d67acdfa1712c293601',
        },
    )

    expected_code = chain.link_bytecode(
        MULTIPLY_13['code'],
        static_link_values={'Library13': '0xd3cda913deb6f67967b99d67acdfa1712c293601'},
    )
    expected_runtime = chain.link_bytecode(
        MULTIPLY_13['code_runtime'],
        static_link_values={'Library13': '0xd3cda913deb6f67967b99d67acdfa1712c293601'},
    )

    assert Multiply13.code == expected_code
    assert Multiply13.code_runtime == expected_runtime


def test_get_contract_factory_with_registrar_dependency(testrpc_chain,
                                                        library_13):
    chain = testrpc_chain
    registrar = chain.registrar

    register_txn_hash = registrar.transact().setAddress(
        'contract/Library13', library_13.address,
    )

    chain.wait.for_receipt(register_txn_hash)

    MULTIPLY_13 = chain.compiled_contracts['Multiply13']
    Multiply13 = chain.get_contract_factory('Multiply13')

    expected_code = chain.link_bytecode(
        MULTIPLY_13['code'],
        static_link_values={'Library13': library_13.address},
    )
    expected_runtime = chain.link_bytecode(
        MULTIPLY_13['code_runtime'],
        static_link_values={'Library13': library_13.address},
    )

    assert Multiply13.code == expected_code
    assert Multiply13.code_runtime == expected_runtime


def test_with_bytecode_mismatch_in_registrar_dependency(testrpc_chain,
                                                        library_13):
    chain = testrpc_chain
    registrar = chain.registrar

    # this will not match the expected underlying bytecode for the Library13
    # contract so it will cause a failure.
    register_txn_hash = registrar.transact().setAddress(
        'contract/Library13', '0xd3cda913deb6f67967b99d67acdfa1712c293601'
    )

    chain.wait.for_receipt(register_txn_hash)

    with pytest.raises(BytecodeMismatchError):
        chain.get_contract_factory('Multiply13')


def test_bytecode_comes_from_project_if_no_migrations(testrpc_chain):
    project = Project()
    assert not project.migrations
    chain = testrpc_chain

    MATH = chain.compiled_contracts['Math']
    Math = chain.get_contract_factory('Math')

    assert Math.abi == MATH['abi']
    assert Math.code == MATH['code']
    assert Math.code_runtime == MATH['code_runtime']


def test_bytecode_comes_from_migrations_when_present(testrpc_chain, migration_0001):
    project = Project()
    chain = testrpc_chain

    remove_file_if_exists('contracts/Math.sol')

    assert 'Math' not in chain.compiled_contracts
    assert len(project.migrations) == 1

    MATH = migration_0001.compiled_contracts['Math']
    Math = chain.get_contract_factory('Math')

    assert Math.abi == MATH['abi']
    assert Math.code == MATH['code']
    assert Math.code_runtime == MATH['code_runtime']


def test_bytecode_comes_from_latest_migration(testrpc_chain, migration_0001, migration_0002):
    project = Project()
    chain = testrpc_chain

    remove_file_if_exists('contracts/Math.sol')

    assert 'Math' not in chain.compiled_contracts
    assert len(project.migrations) == 2

    MATH_V1 = migration_0001.compiled_contracts['Math']
    MATH_V2 = migration_0002.compiled_contracts['Math']
    Math = chain.get_contract_factory('Math')

    # sanity
    assert MATH_V1['code'] != MATH_V2['code']

    assert Math.abi == MATH_V2['abi']
    assert Math.code == MATH_V2['code']
    assert Math.code_runtime == MATH_V2['code_runtime']


def test_it_finds_contracts_with_alternate_registrar_names(testrpc_chain,
                                                           migration_0003):
    project = Project()
    chain = testrpc_chain

    assert len(project.migrations) == 3

    MATH = migration_0003.compiled_contracts['Math']
    Math = chain.get_contract_factory('FancyMath')

    assert Math.abi == MATH['abi']
    assert Math.code == MATH['code']
    assert Math.code_runtime == MATH['code_runtime']
