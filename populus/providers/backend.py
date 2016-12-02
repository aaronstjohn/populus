class BaseContractBackend(object):
    """
    Base class for contract backends
    """
    def get_contract_address(self, contract_name):
        """
        Returns the known address of the requested contract.
        """
        raise NotImplementedError("Must be implemented by subclasses")
