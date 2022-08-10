import importlib.util
import re
import sys
from collections import namedtuple
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from _pytest.assertion.rewrite import AssertionRewritingHook

from watchfiles.cli import cli

if TYPE_CHECKING:
    from conftest import MockRustType

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='some tests fail on windows')
ROOT_DIR = Path(__file__).parent.parent


@pytest.fixture
def import_execute(request, tmp_work_path: Path):
    def _import_execute(module_name: str, source: str, rewrite_assertions: bool = False):
        if rewrite_assertions:
            loader = AssertionRewritingHook(config=request.config)
            loader.mark_rewrite(module_name)
        else:
            loader = None

        example_bash_file = tmp_work_path / 'example.sh'
        example_bash_file.write_text('#!/bin/sh\necho testing')
        example_bash_file.chmod(0o755)
        (tmp_work_path / 'first/path').mkdir(parents=True, exist_ok=True)
        (tmp_work_path / 'second/path').mkdir(parents=True, exist_ok=True)

        module_path = tmp_work_path / f'{module_name}.py'
        module_path.write_text(source)
        spec = importlib.util.spec_from_file_location('__main__', str(module_path), loader=loader)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')

    return _import_execute


def extract_code_chunks(path: Path, text: str, offset: int):
    rel_path = path.relative_to(ROOT_DIR)
    for m_code in re.finditer(r'^```(.*?)$\n(.*?)^```', text, flags=re.M | re.S):
        prefix = m_code.group(1).lower()
        if not prefix.startswith(('py', '{.py')):
            continue

        start_line = offset + text[: m_code.start()].count('\n') + 1
        code = m_code.group(2)
        end_line = start_line + code.count('\n') + 1
        source = '\n' * start_line + code
        if 'test="skip"' in prefix:
            source = '__skip__'
        yield pytest.param(f'{path.stem}_{start_line}_{end_line}', source, id=f'{rel_path}:{start_line}-{end_line}')


def generate_code_chunks(*directories: str):
    for d in directories:
        for path in (ROOT_DIR / d).glob('**/*'):
            if path.suffix == '.py':
                code = path.read_text()
                for m_docstring in re.finditer(r'(^\s*)r?"""$(.*?)\1"""', code, flags=re.M | re.S):
                    start_line = code[: m_docstring.start()].count('\n')
                    docstring = dedent(m_docstring.group(2))
                    yield from extract_code_chunks(path, docstring, start_line)
            elif path.suffix == '.md':
                code = path.read_text()
                yield from extract_code_chunks(path, code, 0)


# with pypy we sometimes (???) get a "The loop argument is deprecated since Python 3.8" warning, see
# https://github.com/samuelcolvin/watchfiles/runs/7764187741
@pytest.mark.filterwarnings('ignore:The loop argument is deprecated:DeprecationWarning')
@pytest.mark.parametrize('module_name,source_code', generate_code_chunks('watchfiles', 'docs'))
def test_docs_examples(module_name, source_code, import_execute, mocker, mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'foo.txt'), (2, 'bar.py')}])
    mocker.patch('watchfiles.run.spawn_context.Process')
    mocker.patch('watchfiles.run.os.kill')

    if source_code == '__skip__':
        pytest.skip('test="skip" on code snippet')

    async def dont_sleep(t):
        pass

    mocker.patch('asyncio.sleep', new=dont_sleep)
    # avoid installing aiohttp by mocking it
    sys.modules['aiohttp'] = type('aiohttp', (), {'web': MagicMock()})

    try:
        import_execute(module_name, source_code, True)
    except Exception:
        sys.modules.pop('aiohttp', None)
        raise


@pytest.mark.skipif(sys.version_info[:2] != (3, 10), reason='output varies between versions')
def test_cli_help(mocker, capsys):
    mocker.patch('watchfiles.cli.argparse.ArgumentParser.exit', side_effect=RuntimeError('custom exit'))
    TerminalSize = namedtuple('TerminalSize', ['columns', 'lines'])
    mocker.patch('shutil.get_terminal_size', return_value=TerminalSize(80, 24))

    with pytest.raises(RuntimeError, match='custom exit'):
        cli('--help')

    out, err = capsys.readouterr()
    assert err == ''

    cli_help_path = ROOT_DIR / 'docs' / 'cli_help.txt'
    try:
        assert out == cli_help_path.read_text(), f'cli help output differs from {cli_help_path}, file updated'
    except AssertionError:
        cli_help_path.write_text(out)
        raise
