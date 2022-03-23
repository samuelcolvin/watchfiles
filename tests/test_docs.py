import importlib.util
import re
from collections import namedtuple
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from _pytest.assertion.rewrite import AssertionRewritingHook

from watchfiles.cli import cli

if TYPE_CHECKING:
    from conftest import MockRustType

ROOT_DIR = Path(__file__).parent.parent


@pytest.fixture
def import_execute(request, tmp_path: Path):
    def _import_execute(module_name: str, source: str, rewrite_assertions: bool = False):
        if rewrite_assertions:
            loader = AssertionRewritingHook(config=request.config)
            loader.mark_rewrite(module_name)
        else:
            loader = None

        module_path = tmp_path / f'{module_name}.py'
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
        if not prefix.startswith(('py', '{.py')) or 'test="false"' in prefix:
            continue

        start_line = offset + text[: m_code.start()].count('\n') + 1
        code = m_code.group(2)
        end_line = start_line + code.count('\n') + 1
        source = '\n' * start_line + code
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


@pytest.mark.parametrize('module_name,source_code', generate_code_chunks('watchfiles', 'docs'))
def test_docs_examples(module_name, source_code, import_execute, mocker, mock_rust_notify: 'MockRustType'):
    mock_rust_notify([{(1, 'foo.txt'), (2, 'bar.py')}])
    mocker.patch('watchfiles.main.spawn_context.Process')
    mocker.patch('watchfiles.main.os.kill')

    async def dont_sleep(t):
        pass

    mocker.patch('asyncio.sleep', new=dont_sleep)

    import_execute(module_name, source_code, True)


def test_cli_help(mocker, capsys):
    mocker.patch('watchfiles.cli.argparse.ArgumentParser.exit', side_effect=RuntimeError('custom exit'))
    TerminalSize = namedtuple('TerminalSize', ['columns', 'lines'])
    mocker.patch('shutil.get_terminal_size', return_value=TerminalSize(80, 24))

    with pytest.raises(RuntimeError, match='custom exit'):
        cli('--help')

    out, err = capsys.readouterr()
    assert err == ''

    cli_help_path = (ROOT_DIR / 'docs' / 'cli_help.txt')
    if out != cli_help_path.read_text():
        cli_help_path.write_text(out)
        raise AssertionError(f'cli help output differs from {cli_help_path}, file updated')
