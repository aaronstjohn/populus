import pytest

from populus.project import Project


def test_project_compiled_contracts_with_no_default_env(project_dir,
                                                        write_project_file,
                                                        MATH):
    write_project_file('contracts/Math.sol', MATH['source'])

    project = Project()
    chain = project.get_chain('testrpc')

    assert 'Math' in chain.compiled_contracts
    assert 'code' in chain.compiled_contracts['Math']
    assert 'code_runtime' in chain.compiled_contracts['Math']
    assert 'abi' in chain.compiled_contracts['Math']

    compiled_contracts_object_id = id(chain.compiled_contracts)

    assert id(chain.compiled_contracts) == compiled_contracts_object_id


def test_project_fill_contracts_cache(write_project_file,
                                      MATH):
    write_project_file('contracts/Math.sol', MATH['source'])

    project = Project()
    chain = project.get_chain('testrpc')
    source_mtime = chain.get_source_modification_time()

    compiled_contracts_object_id = id(chain.compiled_contracts)

    # fill with code from the future -> no recompilation
    chain.fill_contracts_cache(chain.compiled_contracts, source_mtime + 10)
    assert id(chain.compiled_contracts) == compiled_contracts_object_id

    # fill with code from the past -> recompilation
    chain.fill_contracts_cache(chain.compiled_contracts, source_mtime - 10)
    assert not id(chain.compiled_contracts) == compiled_contracts_object_id
