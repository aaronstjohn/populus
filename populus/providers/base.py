from pylru import lrucache

from populus.utils.linking import (
    link_bytecode,
    find_link_references,
)

from .exceptions import (
    NoKnownAddress,
)


class BaseContractBackend(object):
    """

    """
    chain = None

    def __init__(self, chain):
        self.chain = chain

    #
    # Provider API
    #
    def _get_contract_factory(self, contract_name):
        """
        Returns a contract factory instance with fully linked bytecode.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def _is_contract_available(self, contract_name):
        """
        Returns whether the contract is *known*.  This is a check that can be
        called prior to `get_contract` to see whether an address for the
        contract is known.
        """
        try:
            contract_address = self._get_contract_address(contract_name)
        except NoKnownAddress:
            return False

        # TODO: this call needs to be made at the `ProviderWrapper` level
        if not self._are_contract_dependencies_available(contract_name):
            return False

        try:
            ContractFactory = self._get_contract_factory(contract_name)
        except ProviderError:
            return False

        chain_bytecode = self.web3.eth.getCode(contract_address)

        is_bytecode_match = chain_bytecode == ContractFactory.code_runtime

        if not is_bytecode_match:
            return False
        return True

    def _are_contract_dependencies_available(self, contract_name):
        """
        Returns whether all of a contracts
        """
        BaseContractFactory = self.chain.contract_factories[contract_name]
        # TODO: the call to `is_contract_available` needs to be done at the `ProviderWrapper` level.
        return all(
            self._is_contract_available(link_reference.full_name)
            for link_reference
            in find_link_references(
                BaseContractFactory.code,
                self.chain.all_contract_names,
            )
        )

    # Different for each provider
    def _get_contract_address(self, contract_name):
        """
        Returns the known address of the requested contract.

        Note: This method should *always* be safe to call if
        `is_contract_available` returns True.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    # Same for each provider
    def _get_contract(self, contract_name):
        """
        Returns an instance of the contract.
        """
        ContractFactory = self._get_contract_factory(contract_name)
        address = self._get_contract_address(contract_name)
        return ContractFactory(address=address)

    #
    # Utility
    #
    def link_bytecode(self, bytecode):
        """
        Return the fully linked contract bytecode.
        """
        resolved_link_references = {
            link_reference.offset: self._get_contract_address(link_reference.full_name)
            for link_reference
            in find_link_references(bytecode, self.chain.all_contract_names)
        }

        linked_bytecode = link_bytecode(bytecode, **resolved_link_references)
        return linked_bytecode


class Provider(object):
    provider_backends = None

    def __init__(self, chain, provider_backend_classes, static_link_values):
        self.chain = chain
        self.provider_backends = tuple(
            ProviderBackend(self)
            for ProviderBackend
            in provider_backend_classes,
        )
        self._factory_cache = lrucache(128)

    def get_contract_factory(self, contract_name):
        if contract_name in self._factory_cache:
            return self._factory_cache[contract_name]
        for provider in self.provider_backends:
            try:
                ContractFactory = provider._get_contract_factory(contract_name)
                self._factory_cache[contract_name] = ContractFactory
                return ContractFactory
            except Exception as error:
                # TODO: catch the correct expections
                continue

        # TODO: raise the correct expections
        raise Exception("No known address for contract")

    def is_contract_available(self, contract_name):
        return any(
            provider._is_contract_available(contract_name)
            for provider
            in self.provider_backends
        )

    def are_contract_dependencies_available(self, contract_name):
        # TODO: this is wrong
        BaseContractFactory = self.chain.contract_factories[contract_name]
        return all(
            self.is_contract_available(link_reference.full_name)
            for link_reference
            in find_link_references(
                BaseContractFactory.code,
                self.chain.all_contract_names,
            )
        )

    def get_contract(self, contract_name):
        for provider in self.provider_backends:
            try:
                return provider._get_contract(contract_name)
            except Exception as error:
                # TODO: catch the correct expections
                continue

        # TODO: raise the correct expections
        raise Exception("No known address for contract")

    def get_contract_address(self, contract_name):
        for provider in self.provider_backends:
            try:
                return provider._get_contract_address(contract_name)
            except NoKnownAddress as error:
                continue

        raise NoKnownAddress("No known address for contract")
