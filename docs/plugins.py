import logging
import os
import re

from mkdocs.config import Config
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

try:
    import pytest
except ImportError:
    pytest = None

logger = logging.getLogger('mkdocs.test_examples')


def on_pre_build(config: Config):
    test_examples()


def test_examples():
    """
    Run the examples tests.
    """
    if not pytest:
        logger.info('pytest not installed, skipping examples tests')
    else:
        logger.info('running examples tests...')
        try:
            pytest.main(['--version'])
        except AttributeError:
            # happens if pytest is not properly installed
            logger.info('pytest not installed correctly, skipping examples tests')
        else:
            return_code = pytest.main(['-q', '-p', 'no:sugar', 'tests/test_docs.py'])
            if return_code != 0:
                logger.warning('examples tests failed')


def on_files(files: Files, config: Config) -> Files:
    return remove_files(files)


def remove_files(files: Files) -> Files:
    to_remove = []
    for file in files:
        if file.src_path in {'plugins.py', 'cli_help.txt'}:
            to_remove.append(file)
        elif file.src_path.startswith('__pycache__/'):
            to_remove.append(file)

    logger.debug('removing files: %s', [f.src_path for f in to_remove])
    for f in to_remove:
        files.remove(f)

    return files


def on_page_markdown(markdown: str, page: Page, config: Config, files: Files) -> str:
    markdown = reinstate_code_titles(markdown)
    return add_version(markdown, page)


def reinstate_code_titles(markdown: str) -> str:
    """
    Fix titles in code blocks, see https://youtrack.jetbrains.com/issue/PY-53246.
    """
    return re.sub(r'^(```py)\s*\ntitle=', r'\1 title=', markdown, flags=re.M)


def add_version(markdown: str, page: Page) -> str:
    if page.abs_url == '/':
        version_ref = os.getenv('GITHUB_REF')
        if version_ref:
            version = re.sub('^refs/tags/', '', version_ref.lower())
            version_str = f'Documentation for version: **{version}**'
        else:
            version_str = 'Documentation for development version'
        markdown = re.sub(r'{{ *version *}}', version_str, markdown)
    return markdown
