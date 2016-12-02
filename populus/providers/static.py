from .base import BaseContractBackend
from .exceptions import (
    NoKnownAddress,
)


class StaticContractBackend(BaseContractBackend):
    """
    A Contract backend that can only resolve the addresses that it was provided with.
    """
    static_link_values = None

    def __init__(self, provider, static_link_values=None):
        self.static_link_values = static_link_values or {}
        super(StaticContractBackend, self).__init__(provider)

    def _get_contract_address(self, contract_name):
        try:
            return self.static_link_values[contract_name]
        except KeyError:
            raise NoKnownAddress("Contract address not in static link values.")
