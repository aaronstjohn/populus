from flaky import flaky

from populus.chain import (
    ROPSTEN_BLOCK_0_HASH,
    MAINNET_BLOCK_0_HASH,
)
from populus.project import (
    Project,
)


@flaky
def test_project_tester_chain(project_dir):
    project = Project()

    chain = project.get_chain('testrpc')

    with chain as running_tester_chain:
        web3 = running_tester_chain.web3
        assert web3.version.node.startswith('TestRPC')


@flaky
def test_project_temp_chain(project_dir):
    project = Project()

    chain = project.get_chain('temp')

    with chain as running_temp_chain:
        web3 = running_temp_chain.web3
        assert hasattr(running_temp_chain, 'geth')
        assert web3.version.node.startswith('Geth')


@flaky
def test_project_morden_chain(project_dir):
    project = Project()

    chain = project.get_chain('ropsten')

    with chain as running_morden_chain:
        web3 = running_morden_chain.web3
        assert web3.version.node.startswith('Geth')

        running_morden_chain.wait.for_block(block_number=1, timeout=180)

        block_0 = web3.eth.getBlock(0)
        assert block_0['hash'] == ROPSTEN_BLOCK_0_HASH


@flaky
def test_project_local_chain_ipc(project_dir, write_project_file):
    write_project_file('populus.ini', '\n'.join((
        '[chain:custom-chain]',
        'provider=web3.providers.ipc.IPCProvider',
    )))
    project = Project()

    chain = project.get_chain('custom-chain')

    with chain as running_local_chain:
        web3 = running_local_chain.web3
        assert web3.version.node.startswith('Geth')

        running_local_chain.wait.for_block(block_number=1, timeout=180)

        block_0 = web3.eth.getBlock(0)
        assert block_0['hash'] != MAINNET_BLOCK_0_HASH
        assert block_0['hash'] != ROPSTEN_BLOCK_0_HASH
        assert block_0['miner'] == web3.eth.coinbase


@flaky
def test_project_local_chain_rpc(project_dir, write_project_file):
    write_project_file('populus.ini', '\n'.join((
        '[chain:custom-chain]',
        'provider=web3.providers.rpc.RPCProvider',
    )))
    project = Project()

    chain = project.get_chain('custom-chain')

    with chain as running_local_chain:
        web3 = running_local_chain.web3
        assert web3.version.node.startswith('Geth')

        running_local_chain.wait.for_block(block_number=1, timeout=180)

        block_0 = web3.eth.getBlock(0)
        assert block_0['hash'] != MAINNET_BLOCK_0_HASH
        assert block_0['hash'] != ROPSTEN_BLOCK_0_HASH
        assert block_0['miner'] == web3.eth.coinbase
