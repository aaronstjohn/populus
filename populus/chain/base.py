import os
import itertools
import json

from pylru import lrucache

from populus.utils.packaging import (
    get_installed_packages_dir,
    get_chain_lockfile_path,
)
from populus.utils.functional import (
    cached_property,
    cast_return_to_dict,
)
from populus.utils.wait import (
    Wait,
)
from populus.utils.filesystem import (
    relpath,
)
from populus.utils.contracts import (
    construct_contract_factories,
    package_contracts,
)
from populus.utils.linking import (
    link_bytecode,
    extract_link_reference_names,
)

from populus.migrations.migration import (
    get_compiled_contracts_from_migrations,
)
from populus.migrations.registrar import (
    get_registrar,
)

from .exceptions import (
    NoKnownAddress,
    BytecodeMismatchError,
    UnknownContract,
)


class Chain(object):
    """
    Base class for how populus interacts with the blockchain.

    :param project: Instance of :class:`populus.project.Project`
    """
    project = None
    chain_name = None
    _factory_cache = None

    def __init__(self, project, chain_name):
        self.project = project
        self.chain_name = chain_name
        self._factory_cache = lrucache(128)

    #
    # Meta Data API
    #
    @property
    def has_datadir(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def datadir_path(self):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Chain Interaction API
    #
    @property
    def web3(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def wait(self):
        return Wait(self.web3)

    @property
    def chain_config(self):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Packaging
    #
    @property
    def has_lockfile(self):
        return os.path.exists(self.lockfile_path)

    @property
    def lockfile_path(self):
        return get_chain_lockfile_path(self.project_dir, self.chain_name)

    @property
    def lockfile_data(self):
        if self.has_lockfile:
            with open(self.lockfile_path) as lockfile_file:
                return json.load(lockfile_file)
        else:
            return {}

    @property
    @relpath
    def installed_packages_dir(self):
        return get_installed_packages_dir(self.project.project_dir, self.chain_name)

    @property
    @cast_return_to_dict
    def installed_packages(self):
        installed_contracts_dir = self.installed_contracts_dir

        for package_name, _ in self.project_lockfile.items():
            package_source_dir = os.path.relpath(
                os.path.join(installed_contracts_dir, package_name),
                self.project_dir,
            )
            yield (package_name, package_source_dir)

    @cached_property
    def contract_factories(self):
        if self.project.migrations:
            compiled_contracts = get_compiled_contracts_from_migrations(
                self.project.migrations,
                self,
            )
        else:
            compiled_contracts = self.project.compiled_contracts

        return construct_contract_factories(
            self.web3,
            compiled_contracts,
        )

    @property
    def RegistrarFactory(self):
        return get_registrar(self.web3)

    @property
    def has_registrar(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def registrar(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def __enter__(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    #
    # Utility
    #
    @property
    def all_contract_names(self):
        return set(self.contract_factories.keys())

    def _link_code(self, bytecodes,
                   link_value_overrides=None,
                   validate_bytecode=True,
                   raise_on_error=False):
        if link_value_overrides is None:
            link_value_overrides = {}

        all_full_names = set(link_value_overrides.keys()).union(self.all_contract_names)

        library_dependencies = set(itertools.chain.from_iterable(
            extract_link_reference_names(bytecode, all_full_names)
            for bytecode in bytecodes
        ))

        # Determine which dependencies would need to be present in the
        # registrar since they were not explicitely declared via the
        # `link_dependencies`.
        registrar_dependencies = set(library_dependencies).difference(
            link_value_overrides.keys()
        )
        if registrar_dependencies and not self.has_registrar:
            raise NoKnownAddress(
                "Unable to link bytecode.  Addresses for the following link "
                "dependencies were not provided and this chain does not have a "
                "registrar.\n\n{0}".format(
                    ', '.join(registrar_dependencies),
                )
            )

        # Loop over all of the dependencies and ensure that they are available,
        # raising an exception if they are not.
        for library_name in registrar_dependencies:
            self.is_contract_available(
                library_name,
                link_dependencies=link_value_overrides,
                validate_bytecode=validate_bytecode,
                raise_on_error=True,
            )

        registrar_link_dependencies = {
            library_name: self.get_contract(
                library_name,
                link_dependencies=link_value_overrides,
                validate_bytecode=validate_bytecode,
            ).address for library_name in registrar_dependencies
        }

        all_link_dependencies = {
            library_name: library_address
            for library_name, library_address
            in itertools.chain(
                link_value_overrides.items(),
                registrar_link_dependencies.items(),
            )
        }

        linked_bytecodes = [
            link_bytecode(bytecode, **all_link_dependencies)
            for bytecode in bytecodes
        ]
        return linked_bytecodes

    #
    # Contract API
    #
    def is_contract_available(self,
                              contract_name,
                              link_dependencies=None,
                              validate_bytecode=True,
                              raise_on_error=False):
        if not self.has_registrar:
            raise NoKnownAddress(
                'The `is_contract_available` API is only usable on chains that '
                'have a registrar contract'
            )
        contract_key = 'contract/{name}'.format(name=contract_name)

        if not self.registrar.call().exists(contract_key):
            if raise_on_error:
                raise NoKnownAddress(
                    "Address for contract '{name}' not found in registrar".format(
                        name=contract_name,
                    )
                )
            return False

        if not validate_bytecode:
            return True

        try:
            contract_factory = self.get_contract_factory(
                contract_name,
                link_dependencies=link_dependencies,
            )
        except (NoKnownAddress, BytecodeMismatchError):
            if raise_on_error:
                raise
            return False

        contract_address = self.registrar.call().getAddress(contract_key)

        chain_bytecode = self.web3.eth.getCode(contract_address)

        is_bytecode_match = chain_bytecode == contract_factory.code_runtime
        if not is_bytecode_match and raise_on_error:
            raise BytecodeMismatchError(
                "Bytecode @ {0} does not match expected contract bytecode.\n\n"
                "expected : '{1}'\n"
                "actual   : '{2}'\n".format(
                    contract_address,
                    contract_factory.code_runtime,
                    chain_bytecode,
                ),
            )
        return is_bytecode_match

    def get_contract(self,
                     contract_name,
                     link_dependencies=None,
                     validate_bytecode=True):
        if contract_name not in self.contract_factories:
            raise UnknownContract(
                "No contract found with the name '{0}'.\n\n"
                "Available contracts are: {1}".format(
                    contract_name,
                    ', '.join((name for name in self.contract_factories.keys())),
                )
            )
        self.is_contract_available(
            contract_name,
            link_dependencies=link_dependencies,
            validate_bytecode=validate_bytecode,
            raise_on_error=True,
        )

        contract_factory = self.get_contract_factory(
            contract_name,
            link_dependencies=link_dependencies,
        )
        contract_key = 'contract/{name}'.format(name=contract_name)
        contract_address = self.registrar.call().getAddress(contract_key)
        contract = contract_factory(address=contract_address)
        return contract

    def get_contract_factory(self,
                             contract_name,
                             link_dependencies=None):
        cache_key = (contract_name,) + tuple(sorted((link_dependencies or {}).items()))
        if cache_key in self._factory_cache:
            return self._factory_cache[cache_key]
        if contract_name not in self.contract_factories:
            raise UnknownContract(
                "No contract found with the name '{0}'.\n\n"
                "Available contracts are: {1}".format(
                    contract_name,
                    ', '.join((name for name in self.contract_factories.keys())),
                )
            )

        base_contract_factory = self.contract_factories[contract_name]

        if link_dependencies is not False:
            code, code_runtime = self._link_code(
                bytecodes=[
                    base_contract_factory.code,
                    base_contract_factory.code_runtime,
                ],
                link_dependencies=link_dependencies,
            )
        else:
            code, code_runtime = (
                base_contract_factory.code,
                base_contract_factory.code_runtime,
            )

        contract_factory = self.web3.eth.contract(
            code=code,
            code_runtime=code_runtime,
            abi=base_contract_factory.abi,
            source=base_contract_factory.source,
        )
        self._factory_cache[cache_key] = contract_factory
        return contract_factory

    @property
    def deployed_contracts(self):
        contract_classes = {
            contract_name: self.get_contract(contract_name)
            for contract_name in self.contract_factories.keys()
            if self.is_contract_available(contract_name)
        }
        return package_contracts(contract_classes)
