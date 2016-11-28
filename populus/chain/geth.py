try:
    from contextlib import ExitStack
except ImportError:
    from contextlib2 import ExitStack

from geth import (
    DevGethProcess,
    LiveGethProcess,
    TestnetGethProcess,
    LoggingMixin,
)

from web3 import (
    Web3,
    RPCProvider,
    IPCProvider,
)
from web3.utils.types import is_string

from populus.migrations.registrar import (
    get_registrar,
)

from populus.utils.functional import (
    cached_property,
)
from populus.utils.geth import (
    get_geth_logfile_path,
)
from populus.utils.module_loading import (
    import_string,
)
from populus.utils.filesystem import (
    get_blockchains_dir,
    tempdir,
)

from .base import (
    Chain,
)


GETH_KWARGS = {
    'data_dir',
    'geth_executable',
    'max_peers',
    'network_id',
    'no_discover',
    'mine',
    'autodag',
    'miner_threads',
    'nice',
    'unlock',
    'password',
    'port',
    'verbosity',
    'ipc_disable',
    'ipc_path',
    'ipc_api',
    'ws_enabled',
    'ws_enabled',
    'ws_addr',
    'ws_origins',
    'ws_port',
    'ws_api',
    'rpc_enabled',
    'rpc_addr',
    'rpc_port',
    'rpc_api',
    'prefix_cmd',
    'suffix_args',
    'suffix_kwargs',
}


class LoggedDevGethProcess(LoggingMixin, DevGethProcess):
    def __init__(self, project_dir, blockchains_dir, chain_name, overrides):
        stdout_logfile_path = get_geth_logfile_path(
            project_dir,
            chain_name,
            'stdout'
        )
        stderr_logfile_path = get_geth_logfile_path(
            project_dir,
            chain_name,
            'stderr',
        )
        super(LoggedDevGethProcess, self).__init__(
            overrides=overrides,
            chain_name=chain_name,
            base_dir=blockchains_dir,
            stdout_logfile_path=stdout_logfile_path,
            stderr_logfile_path=stderr_logfile_path,
        )


class LoggedMordenGethProccess(LoggingMixin, TestnetGethProcess):
    def __init__(self, project_dir, geth_kwargs):
        super(LoggedMordenGethProccess, self).__init__(
            geth_kwargs=geth_kwargs,
        )


class LoggedMainnetGethProcess(LoggingMixin, LiveGethProcess):
    def __init__(self, project_dir, geth_kwargs):
        super(LoggedMainnetGethProcess, self).__init__(
            geth_kwargs=geth_kwargs,
            stdout_logfile_path=get_geth_logfile_path(
                project_dir,
                'mainnet',
                'stdout'
            ),
            stderr_logfile_path=get_geth_logfile_path(
                project_dir,
                'mainnet',
                'stderr',
            ),
        )


class BaseGethChain(Chain):
    geth = None
    provider_class = None

    def __init__(self, project, chain_name, provider=IPCProvider, **geth_kwargs):
        super(BaseGethChain, self).__init__(project, chain_name)

        if geth_kwargs is None:
            geth_kwargs = {}

        if is_string(provider):
            provider = import_string(provider)

        # context manager shenanigans
        self.stack = ExitStack()

        self.provider_class = provider
        self.extra_kwargs = {
            key: value
            for key, value in geth_kwargs.items() if key not in GETH_KWARGS
        }
        self.geth_kwargs = {
            key: value
            for key, value in geth_kwargs.items() if key in GETH_KWARGS
        }
        self.geth = self.get_geth_process_instance()

    _web3 = None

    @property
    def web3(self):
        if not self.geth.is_running:
            raise ValueError(
                "Underlying geth process doesn't appear to be running"
            )

        if self._web3 is None:
            if issubclass(self.provider_class, IPCProvider):
                provider = IPCProvider(self.geth.ipc_path)
            elif issubclass(self.provider_class, RPCProvider):
                provider = RPCProvider(port=self.geth.rpc_port)
            else:
                raise NotImplementedError(
                    "Unsupported provider class {0!r}.  Must be one of "
                    "IPCProvider or RPCProvider"
                )
            _web3 = Web3(provider)

            if 'default_account' in self.chain_config:
                _web3.eth.defaultAccount = self.chain_config['default_account']

            self._web3 = _web3
        return self._web3

    @property
    def chain_config(self):
        return self.project.config.chains[self.chain_name]

    @property
    def has_registrar(self):
        return 'registrar' in self.chain_config

    @cached_property
    def registrar(self):
        if not self.has_registrar:
            raise KeyError(
                "The configuration for the {0} chain does not include a "
                "registrar.  Please set this value to the address of the "
                "deployed registrar contract.".format(self.chain_name)
            )
        return get_registrar(
            self.web3,
            address=self.chain_config['registrar'],
        )

    def get_geth_process_instance(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def __enter__(self, *args, **kwargs):
        self.stack.enter_context(self.geth)

        if self.geth.is_mining:
            self.geth.wait_for_dag(600)
        if self.geth.ipc_enabled:
            self.geth.wait_for_ipc(60)
        if self.geth.rpc_enabled:
            self.geth.wait_for_rpc(60)

        return self

    def __exit__(self, *exc_info):
        self.stack.close()


class LocalGethChain(BaseGethChain):
    def get_geth_process_instance(self):
        return LoggedDevGethProcess(
            project_dir=self.project.project_dir,
            blockchains_dir=self.project.blockchains_dir,
            chain_name=self.chain_name,
            overrides=self.geth_kwargs,
        )


class TemporaryGethChain(BaseGethChain):
    def get_geth_process_instance(self):
        tmp_project_dir = self.stack.enter_context(tempdir())
        blockchains_dir = get_blockchains_dir(tmp_project_dir)

        return LoggedDevGethProcess(
            project_dir=self.project.project_dir,
            blockchains_dir=blockchains_dir,
            chain_name=self.chain_name,
            overrides=self.geth_kwargs,
        )

    has_registrar = True

    @cached_property
    def registrar(self):
        RegistrarFactory = get_registrar(self.web3)
        deploy_txn_hash = RegistrarFactory.deploy()
        registrar_address = self.wait.for_contract_address(deploy_txn_hash)
        registrar = RegistrarFactory(address=registrar_address)

        return registrar


class MordenChain(BaseGethChain):
    def get_geth_process_instance(self):
        return LoggedMordenGethProccess(
            project_dir=self.project.project_dir,
            geth_kwargs=self.geth_kwargs,
        )


class MainnetChain(BaseGethChain):
    def get_geth_process_instance(self):
        return LoggedMainnetGethProcess(
            project_dir=self.project.project_dir,
            geth_kwargs=self.geth_kwargs,
        )
