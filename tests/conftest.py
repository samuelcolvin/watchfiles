import os
from pathlib import Path
from typing import Dict

import pytest

PathDict = Dict[str, 'PathDict']


def mktree(root_dir: Path, path_dict: PathDict):
    """
    Create a tree of files from a dictionary of name > content lookups.
    """
    for name, content in path_dict.items():
        path = root_dir / name

        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            mktree(path, content)
        elif isinstance(content, str):
            path.write_text(content)
        else:
            assert isinstance(content, bytes), 'content must be a dict, str or bytes'
            path.write_bytes(content)


@pytest.fixture
def tmp_work_path(tmp_path: Path):
    """
    Create a temporary working directory.
    """
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)

    yield tmp_path

    os.chdir(previous_cwd)
