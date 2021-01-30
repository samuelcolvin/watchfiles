from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

THIS_DIR = Path(__file__).resolve().parent
long_description = THIS_DIR.joinpath('README.md').read_text()

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'watchgod/version.py').load_module()

setup(
    name='watchgod',
    version=str(version.VERSION),
    description='Simple, modern file watching and code reload in python.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
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
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/watchgod',
    entry_points="""
        [console_scripts]
        watchgod=watchgod.cli:cli
    """,
    license='MIT',
    packages=['watchgod'],
    package_data={'watchgod': ['py.typed']},
    python_requires='>=3.5',
    zip_safe=True,
)
