import os


EPM_JSON_FILENAME = 'epm.json'


def get_epm_json_path(project_dir):
    return os.path.join(project_dir, EPM_JSON_FILENAME)
