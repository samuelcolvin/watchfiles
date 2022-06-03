#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path


def main(version_path_env_var='VERSION_PATH', version_env_vars=('VERSION', 'GITHUB_REF')) -> int:
    version_path = os.getenv(version_path_env_var, 'Cargo.toml')
    if not version_path:
        print(f'✖ "{version_path_env_var}" env variable not found')
        return 1
    version_path = Path(version_path)
    if not version_path.parent.is_dir():
        print(f'✖ path "{version_path.parent}" does not exist')
        return 1

    version = None
    for var in version_env_vars:
        version_ref = os.getenv(var)
        if version_ref:
            version = re.sub('^refs/tags/v*', '', version_ref.lower())
            break
    if not version:
        print(f'✖ "{version_env_vars}" env variables not found')
        return 1

    print(f'writing version "{version}", to {version_path}')
    with open(version_path) as f:
        origin_content = f.read()
    
    new_content = origin_content.replace('version = "0.0.0"', f'version = "{version}"')
    version_path.write_text(new_content)
    return 0


if __name__ == '__main__':
    sys.exit(main())