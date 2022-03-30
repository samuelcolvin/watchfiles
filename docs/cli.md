*watchfiles* comes with a CLI for running and reloading code, the CLI uses
[watchfiles.run_process][watchfiles.run_process] to run the code and like `run_process` can either run a python
function or a shell-like command.

The CLI can be used either via `watchfiles ...` or `python -m watchfiles ...`.

## Running and restarting a python function

Let's say you have `foobar.py` (in this case a very simple web server using
[aiohttp](https://aiohttp.readthedocs.io/en/stable/)) which gets details about recent file changes from the
`WATCHFILES_CHANGES` environment variable (see [`run_process` docs](./api/run_process.md#watchfiles.run_process))
and returns them as JSON.

```py
title="foobar.py"
import os, json
from aiohttp import web

async def handle(request):
    # get the most recent file changes and return them
    changes = os.getenv('WATCHFILES_CHANGES')
    changes = json.loads(changes)
    return web.json_response(dict(changes=changes))

app = web.Application()
app.router.add_get('/', handle)

def main():
    web.run_app(app, port=8000)
```

You could run this and reload it when any file in the current directory changes with:

```bash title="Running a python function"
watchfiles foobar.main
```

## Running and restarting a command

Let's say you want to re-run failing tests whenever files change. You could do this with **watchfiles** using

```bash title="Running a command"
watchfiles 'pytest --lf'
```

(pytest's `--lf` option is a shortcut for `--last-failed`,
see [pytest docs](https://docs.pytest.org/en/latest/how-to/cache.html))

By default the CLI will watch the current directory and all subdirectories, but the directory/directories watched
can be changed.

In this example, we might want to watch only the `src` and `tests` directories, and only react to changes in python
files:

```bash title="Watching custom directories and files"
watchfiles --filter python 'pytest --lf' src tests
```

## Help

Run `watchfiles --help` for more options.

```{title="watchfiles --help"}
{! docs/cli_help.txt !}
```
