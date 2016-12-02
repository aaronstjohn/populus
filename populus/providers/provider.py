from pylru import lrucache

from populus.utils.linking import (
    link_bytecode,
    find_link_references,
)

from .static import StaticContractBackend
from .exceptions import (
    UnknownContract,
    NoKnownAddress,
)


class Provider(object):
    provider_backends = None

    def __init__(self, chain, provider_backend_classes, static_link_values):
        self.chain = chain
        self.provider_backends = (StaticContractBackend(static_link_values),) + tuple(
            ProviderBackend(self)
            for ProviderBackend
            in provider_backend_classes,
        )
        self._factory_cache = lrucache(128)

    def get_contract_factory(self, contract_name):
        if contract_name in self._factory_cache:
            return self._factory_cache[contract_name]

        if contract_name not in self.chain.contract_factories:
            raise UnknownContract(
                "No contract found with the name '{0}'.\n\n"
                "Available contracts are: {1}".format(
                    contract_name,
                    ', '.join((name for name in self.contract_factories.keys())),
                )
            )

        base_contract_factory = self.contract_factories[contract_name]

        code = self.link_bytecode(base_contract_factory.code)
        code_runtime = self.link_bytecode(base_contract_factory.code_runtime)

        contract_factory = self.chain.web3.eth.contract(
            code=code,
            code_runtime=code_runtime,
            abi=base_contract_factory.abi,
            source=base_contract_factory.source,
        )

        self._factory_cache[contract_name] = contract_factory
        return contract_factory

    def is_contract_available(self, contract_name):
        try:
            contract_address = self.get_contract_address(contract_name)
        except NoKnownAddress:
            return False

        BaseContractFactory = self.chain.contract_factories[contract_name]

        all_dependencies_are_available = all(
            self.is_contract_available(link_reference.full_name)
            for link_reference
            in find_link_references(
                BaseContractFactory.code,
                self.chain.all_contract_names,
            )
        )
        if not all_dependencies_are_available:
            return False

        ContractFactory = self.get_contract_factory(contract_name)

        chain_bytecode = self.chain.web3.eth.getCode(contract_address)

        is_bytecode_match = chain_bytecode == ContractFactory.code_runtime

        if not is_bytecode_match:
            return False
        return True

    def get_contract(self, contract_name):
        ContractFactory = self.get_contract_factory(contract_name)
        address = self.get_contract_address(contract_name)
        return ContractFactory(address=address)

    def get_contract_address(self, contract_name):
        for provider in self.provider_backends:
            try:
                return provider.get_contract_address(contract_name)
            except NoKnownAddress as error:
                continue

        raise NoKnownAddress("No known address for contract")

    def link_bytecode(self, bytecode):
        """
        Return the fully linked contract bytecode.
        """
        resolved_link_references = {
            link_reference.offset: self.get_contract_address(link_reference.full_name)
            for link_reference
            in find_link_references(bytecode, self.chain.all_contract_names)
        }

        linked_bytecode = link_bytecode(bytecode, **resolved_link_references)
        return linked_bytecode


class AutoProvider(Provider):
    """
    A provider that automatically *tries* to deploy any contracts that aren't
    available for use with testing.

    TODO: implement from TestRPCChain
    """
    pass
