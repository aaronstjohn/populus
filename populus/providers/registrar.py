"""
TODO: A chain based registrar
"""
from .base import BaseContractBackend
from .exceptions import (
    NoKnownAddress,
)


class RegistrarProviderBackend(BaseContractBackend):
    def get_contract_factory(self, contract_name):
        # TODO: this caching needs to happen at the `ProviderWrapper` level
        #cache_key = (contract_name,) + tuple(sorted((static_link_values or {}).items()))
        #if cache_key in self._factory_cache:
        #    return self._factory_cache[cache_key]

        # TODO: this check needs to happen at the `ProviderWrapper` level
        #if contract_name not in self.contract_factories:
        #    raise UnknownContract(
        #        "No contract found with the name '{0}'.\n\n"
        #        "Available contracts are: {1}".format(
        #            contract_name,
        #            ', '.join((name for name in self.contract_factories.keys())),
        #        )
        #    )

        base_contract_factory = self.contract_factories[contract_name]

        # TODO: this bytecode linking needs to be done at the `ProviderWrapper` level.
        code = self.link_bytecode(base_contract_factory.code)
        code_runtime = self.link_bytecode(base_contract_factory.code_runtime)

        contract_factory = self.chain.web3.eth.contract(
            code=code,
            code_runtime=code_runtime,
            abi=base_contract_factory.abi,
            source=base_contract_factory.source,
        )

        # TODO: this caching needs to happen at the `ProviderWrapper` level
        #self._factory_cache[cache_key] = contract_factory
        return contract_factory

    def _get_contract_address(self, contract_name):
        contract_key = 'contract/{name}'.format(name=contract_name)

        if not self.registrar.call().exists(contract_key):
            raise NoKnownAddress("No known address for contract '{0}'".format(contract_name))

        contract_address = self.registrar.call().getAddress(contract_key)
        return contract_address

    @property
    def deployed_contracts(self):
        contract_classes = {
            contract_name: self.get_contract(contract_name)
            for contract_name in self.contract_factories.keys()
            if self.is_contract_available(contract_name)
        }
        return package_contracts(contract_classes)
