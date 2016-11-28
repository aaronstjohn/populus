import os
import json
import itertools

from solc import (
    compile_files,
)
from solc.exceptions import (
    ContractsNotFound,
)

from populus.utils.packaging import (
    find_installed_package_source_files,
)
from populus.utils.functional import (
    cast_return_to_tuple,
)
from populus.utils.filesystem import (
    get_compiled_contracts_file_path,
    recursive_find_files,
    DEFAULT_CONTRACTS_DIR
)


def find_project_contracts(project_dir, contracts_rel_dir=DEFAULT_CONTRACTS_DIR):
    contracts_dir = os.path.join(project_dir, contracts_rel_dir)

    return tuple(
        os.path.relpath(p) for p in recursive_find_files(contracts_dir, "*.sol")
    )


@cast_return_to_tuple
def compute_import_remappings(source_paths, installed_packages):
    source_and_remapping_pairs = itertools.product(
        sorted(source_paths),
        sorted(installed_packages.items()),
    )
    for import_path, (package_name, package_source_dir) in source_and_remapping_pairs:
        yield "{import_path}:{package_name}={package_source_dir}".format(
            import_path=import_path,
            package_name=package_name,
            package_source_dir=package_source_dir,
        )


def write_compiled_sources(project_dir, compiled_sources):
    compiled_contract_path = get_compiled_contracts_file_path(project_dir)

    with open(compiled_contract_path, 'w') as outfile:
        outfile.write(
            json.dumps(compiled_sources,
                       sort_keys=True,
                       indent=4,
                       separators=(',', ': '))
        )
    return compiled_contract_path


DEFAULT_OUTPUT_VALUES = ['bin', 'bin-runtime', 'abi', 'devdoc', 'userdoc']


def compile_project_contracts(project_dir,
                              contracts_dir,
                              installed_packages,
                              **compiler_kwargs):
    compiler_kwargs.setdefault('output_values', DEFAULT_OUTPUT_VALUES)

    project_source_paths = find_project_contracts(project_dir, contracts_dir)
    installed_package_source_paths = find_installed_package_source_files(project_dir)

    import_remappings = compute_import_remappings(project_source_paths, installed_packages)

    all_source_paths = tuple(itertools.chain(
        project_source_paths,
        installed_package_source_paths,
    ))

    try:
        compiled_sources = compile_files(
            all_source_paths,
            import_remappings=import_remappings,
            **compiler_kwargs
        )
    except ContractsNotFound:
        return all_source_paths, {}

    return project_source_paths, compiled_sources


def compile_and_write_contracts(project_dir,
                                contracts_dir,
                                installed_packages,
                                **compiler_kwargs):
    contract_source_paths, compiled_sources = compile_project_contracts(
        project_dir,
        contracts_dir,
        installed_packages,
        **compiler_kwargs
    )

    output_file_path = write_compiled_sources(project_dir, compiled_sources)
    return contract_source_paths, compiled_sources, output_file_path
