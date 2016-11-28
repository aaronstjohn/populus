from web3 import (
    Web3,
    RPCProvider,
    IPCProvider,
)

from populus.migrations.registrar import (
    get_registrar,
)

from populus.utils.module_loading import (
    import_string,
)
from populus.utils.functional import (
    cached_property,
)

from .base import (
    Chain,
)


class ExternalChain(Chain):
    """
    Chain class to represent an externally running blockchain that is not
    locally managed.  This class only houses a pre-configured web3 instance.
    """
    def __init__(self, project, chain_name, *args, **kwargs):
        super(ExternalChain, self).__init__(project, chain_name)

        provider_import_path = kwargs.pop(
            'provider',
            'web3.providers.ipc.IPCProvider',
        )
        provider_class = import_string(provider_import_path)

        if provider_class == RPCProvider:
            host = kwargs.pop('host', '127.0.0.1')
            # TODO: this integer casting needs to be done downstream in
            # web3.py.
            port = int(kwargs.pop('port', 8545))
            provider = provider_class(host=host, port=port)
        elif provider_class == IPCProvider:
            ipc_path = kwargs.pop('ipc_path', None)
            provider = provider_class(ipc_path=ipc_path)
        else:
            raise NotImplementedError(
                "Only the IPCProvider and RPCProvider provider classes are "
                "currently supported for external chains."
            )

        self._web3 = Web3(provider)

    @property
    def chain_config(self):
        return self.project.config.chains[self.chain_name]

    @property
    def web3(self):
        if 'default_account' in self.chain_config:
            self._web3.eth.defaultAccount = self.chain_config['default_account']
        return self._web3

    def __enter__(self):
        return self

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
