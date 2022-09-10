import sys

sys.stderr.write(
    """
===============================
Unsupported installation method
===============================
watchfiles no longer supports installation with `python setup.py install`.
Please use `python -m pip install .` instead.
"""
)
sys.exit(1)


# The below code will never execute, however GitHub is particularly
# picky about where it finds Python packaging metadata.
# See: https://github.com/github/feedback/discussions/6456
#
# To be removed once GitHub catches up.

setup(
    name='watchfiles',
    install_requires=[
        'anyio>=3.0.0,<4',
    ],
)
