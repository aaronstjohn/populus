from populus.utils.linking import (
    link_bytecode,
    find_link_references,
)

from .exceptions import (
    NoKnownAddress,
)


class BaseProviderBackend(object):
    """

    """
    chain = None

    def __init__(self, chain):
        self.chain = chain

    #
    # Provider API
    #
    def _get_contract_factory(self, *args, **kwargs):
        """
        Returns a contract factory instance with fully linked bytecode.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def _is_contract_available(self, *args, **kwargs):
        """
        Returns whether the contract is *known*.  This is a check that can be
        called prior to `get_contract` to see whether an address for the
        contract is known.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def _get_contract_address(self, *args, **kwargs):
        """
        Returns the known address of the requested contract.

        Note: This method should *always* be safe to call if
        `is_contract_available` returns True.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def _get_contract(self, *args, **kwargs):
        """
        Returns an instance of the contract.
        """
        ContractFactory = self._get_contract_factory(*args, **kwargs)
        address = self._get_contract_address(*args, **kwargs)
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

    def __init__(self, *provider_backends):
        self.provider_backends = provider_backends

    def get_contract_factory(self, *args, **kwargs):
        for provider in self.provider_backends:
            try:
                return provider._get_contract_factory(*args, **kwargs)
            except Exception as error:
                # TODO: catch the correct expections
                continue

        # TODO: raise the correct expections
        raise Exception("No known address for contract")

    def get_contract(self, *args, **kwargs):
        for provider in self.provider_backends:
            try:
                return provider._get_contract(*args, **kwargs)
            except Exception as error:
                # TODO: catch the correct expections
                continue

        # TODO: raise the correct expections
        raise Exception("No known address for contract")

    def get_contract_address(self, *args, **kwargs):
        for provider in self.provider_backends:
            try:
                return provider._get_contract_address(*args, **kwargs)
            except NoKnownAddress as error:
                continue

        raise NoKnownAddress("No known address for contract")

    def is_contract_available(self, *args, **kwargs):
        return any(
            provider._is_contract_available(*args, **kwargs)
            for provider
            in self.provider_backends
        )
