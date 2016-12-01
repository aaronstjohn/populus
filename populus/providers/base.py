class BaseContractBackend(object):
    """

    """
    chain = None

    def __init__(self, chain):
        self.chain = chain

    def get_contract_factory(self, *args, **kwargs):
        """
        Returns a contract factory instance with fully linked bytecode.
        """
        pass

    def get_contract(self, *args, **kwargs):
        """
        Returns an instance of the contract
        """
        pass

    def get_contract_address(self, *args, **kwargs):
        """
        Returns the known address of the requested contract.
        """
        pass

    def is_contract_available(self, *args, **kwargs):
        """
        Returns whether the contract is *known*.  This is a check that can be
        called prior to `get_contract` to see whether an address for the
        contract is known.
        """
        pass
