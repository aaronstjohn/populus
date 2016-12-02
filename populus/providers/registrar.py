from .backend import BaseContractBackend
from .exceptions import (
    NoKnownAddress,
)


class RegistrarContractBackend(BaseContractBackend):
    def get_contract_address(self, contract_name):
        contract_key = 'contract/{name}'.format(name=contract_name)

        if not self.registrar.call().exists(contract_key):
            raise NoKnownAddress("No known address for contract '{0}'".format(contract_name))

        contract_address = self.registrar.call().getAddress(contract_key)
        return contract_address
