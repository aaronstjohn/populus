import os


CHAIN_METADATA_ROOT_DIR = "./chain-meta"


def get_chain_metadata_root_dir(project_dir):
    return os.path.join(project_dir, CHAIN_METADATA_ROOT_DIR)


def get_chain_metadata_dir(project_dir, chain_name):
    chain_metadata_root_dir = get_chain_metadata_root_dir(project_dir)
    return os.path.join(chain_metadata_root_dir, chain_name)
