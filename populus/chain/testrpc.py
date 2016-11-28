from web3 import (
    Web3,
)
from web3.providers.rpc import TestRPCProvider

from populus.utils.networking import (
    get_open_port,
    wait_for_connection,
)
from populus.utils.functional import (
    cached_property,
)

from .base import (
    Chain,
)
from .exceptions import (
    UnknownContract,
)


def testrpc_fn_proxy(fn_name):
    @staticmethod
    def inner(*args, **kwargs):
        from testrpc import testrpc
        fn = getattr(testrpc, fn_name)
        return fn(*args, **kwargs)
    inner.__func__.__name__ = fn_name
    return inner


class TestRPCChain(Chain):
    provider = None
    port = None

    @cached_property
    def web3(self):
        if self.provider is None or not self._running:
            raise ValueError(
                "TesterChain instances must be running to access the web3 "
                "object."
            )
        _web3 = Web3(self.provider)

        if 'default_account' in self.chain_config:
            _web3.eth.defaultAccount = self.chain_config['default_account']

        return _web3

    @property
    def chain_config(self):
        config = self.project.config.chains[self.chain_name]
        # TODO: how to do this without causing a circular dependency between these properties.
        # config.update({
        #     'registrar': self.registrar.address,
        # })
        return config

    has_registrar = True

    @cached_property
    def registrar(self):
        # deploy the registrar
        deploy_txn_hash = self.RegistrarFactory.deploy()
        registrar_address = self.wait.for_contract_address(deploy_txn_hash)

        return self.RegistrarFactory(address=registrar_address)

    full_reset = testrpc_fn_proxy('full_reset')
    reset = testrpc_fn_proxy('evm_reset')

    @staticmethod
    def snapshot(*args, **kwargs):
        from testrpc import testrpc
        return int(testrpc.evm_snapshot(*args, **kwargs), 16)

    revert = testrpc_fn_proxy('evm_revert')
    mine = testrpc_fn_proxy('evm_mine')

    _running = False

    def __enter__(self):
        from testrpc import testrpc
        if self._running:
            raise ValueError("The TesterChain is already running")

        if self.port is None:
            self.port = get_open_port()

        self.provider = TestRPCProvider(port=self.port)

        testrpc.full_reset()
        testrpc.rpc_configure('eth_mining', False)
        testrpc.rpc_configure('eth_protocolVersion', '0x3f')
        testrpc.rpc_configure('net_version', 1)
        testrpc.evm_mine()

        wait_for_connection('127.0.0.1', self.port)
        self._running = True
        return self

    def __exit__(self, *exc_info):
        if not self._running:
            raise ValueError("The TesterChain is not running")
        try:
            self.provider.server.stop()
            self.provider.server.close()
            self.provider.thread.kill()
        finally:
            self._running = False

    def get_contract(self,
                     contract_name,
                     link_dependencies=None,
                     deploy_transaction=None,
                     deploy_args=None,
                     deploy_kwargs=None,
                     *args,
                     **kwargs):
        if contract_name not in self.contract_factories:
            raise UnknownContract(
                "No contract found with the name '{0}'.\n\n"
                "Available contracts are: {1}".format(
                    contract_name,
                    ', '.join((name for name in self.contract_factories.keys())),
                )
            )

        registrar = self.registrar
        contract_key = "contract/{name}".format(name=contract_name)
        if not registrar.call().exists(contract_key):
            # First dig down into the dependency tree to make the library
            # dependencies available.
            contract_bytecode = self.contract_factories[contract_name].code
            contract_dependencies = self._extract_library_dependencies(
                contract_bytecode, link_dependencies,
            )
            for dependency in contract_dependencies:
                self.get_contract(
                    dependency,
                    link_dependencies=link_dependencies,
                    *args,
                    **kwargs
                )

            # Then get the factory and deploy it.
            contract_factory = self.get_contract_factory(
                contract_name,
                link_dependencies=kwargs.get('link_dependencies'),
            )
            deploy_txn_hash = contract_factory.deploy(
                transaction=deploy_transaction,
                args=deploy_args,
                kwargs=deploy_kwargs,
            )
            contract_address = self.wait.for_contract_address(deploy_txn_hash)

            # Then register the address with the registrar so that the super
            # method will be able to get and return it.
            register_txn_hash = registrar.transact().setAddress(
                contract_key,
                contract_address,
            )
            self.wait.for_receipt(register_txn_hash)
        return super(TestRPCChain, self).get_contract(
            contract_name,
            link_dependencies=link_dependencies,
            *args,
            **kwargs
        )
