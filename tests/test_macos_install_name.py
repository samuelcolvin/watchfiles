import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from watchfiles import _rust_notify


@pytest.mark.skipif(sys.platform != 'darwin', reason='Mach-O install names are specific to macOS')
def test_extension_install_name_can_be_relocated(tmp_path: Path) -> None:
    install_name_tool = shutil.which('install_name_tool')
    otool = shutil.which('otool')
    if install_name_tool is None or otool is None:
        pytest.skip('Xcode command-line tools are not available')

    extension = Path(_rust_notify.__file__)
    relocated = tmp_path / extension.name
    shutil.copyfile(extension, relocated)
    install_name = str(tmp_path / 'Cellar' / 'watchfiles' / 'lib' / 'python3.14' / 'site-packages' / extension.name)

    result = subprocess.run(
        [install_name_tool, '-id', install_name, str(relocated)], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert install_name in subprocess.check_output([otool, '-D', str(relocated)], text=True).splitlines()
