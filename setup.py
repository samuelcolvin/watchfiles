import os
from importlib.machinery import SourceFileLoader
from pathlib import Path

from setuptools import setup

description = 'Simple, modern and high performance file watching and code reload in python.'
THIS_DIR = Path(__file__).resolve().parent
try:
    long_description = (THIS_DIR / 'README.md').read_text()
except FileNotFoundError:
    long_description = description

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'watchfiles/version.py').load_module()

extra = {}
if not os.getenv('SKIP_RUST_EXTENSION'):
    from setuptools_rust import Binding, RustExtension

    extra['rust_extensions'] = [RustExtension('watchfiles._rust_notify', binding=Binding.PyO3)]

setup(
    name='watchfiles',
    version=str(version.VERSION),
    description=description,
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',
        'Environment :: MacOS X',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Filesystems',
        'Framework :: AnyIO',
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/watchfiles',
    entry_points="""
        [console_scripts]
        watchfiles=watchfiles.cli:cli
    """,
    license='MIT',
    packages=['watchfiles'],
    package_data={'watchfiles': ['py.typed', '*.pyi']},
    install_requires=['anyio>=3.0.0,<4'],
    python_requires='>=3.7',
    zip_safe=False,
    project_urls={
        'Documentation': 'https://watchfiles.helpmanual.io',
        'Funding': 'https://github.com/sponsors/samuelcolvin',
        'Source': 'https://github.com/samuelcolvin/watchfiles',
        'Changelog': 'https://github.com/samuelcolvin/watchfiles/releases',
    },
    **extra,
)
