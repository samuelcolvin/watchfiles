*watchfiles* also comes with a CLI for running and reloading python code.

Let's say you have `foobar.py` (this is a very simple web server using 
[aiohttp](https://aiohttp.readthedocs.io/en/stable/)) which gets details about recent file changes from the 
`WATCHFILES_CHANGES` environment variable and returns them as JSON.

```py
title="Code to be run via the CLI"
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

```bash title="CLI Usage"
watchfiles foobar.main
```

Run `watchfiles --help` for more options.

The CLI can also be used via `python -m watchfiles ...`.
