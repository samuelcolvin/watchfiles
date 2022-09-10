This package was significantly rewritten and renamed from `watchgod` to `watchfiles`, these docs refer to the new
`watchfiles` package.

The main reason for this change was to avoid confusion with the similarly named "watchdog" package,
see [#102](https://github.com/samuelcolvin/watchfiles/issues/102) for more details.

The most significant code change was to switch from file scanning/polling to OS file system notifications
using the [Notify](https://github.com/notify-rs/notify) rust library.
This is much more performant than the old approach.

As a result, the external interface to the library has been changed somewhat.

The main methods:

* [`watch`][watchfiles.watch]
* [`awatch`][watchfiles.awatch]
* [`run_process`][watchfiles.run_process]
* [`arun_process`][watchfiles.arun_process]

All remain, the following changes affect them all:

* `watcher_cls` is removed and replaced by `watch_filter` which should be a simple callable,
  see [filter docs](./api/filters.md)
* all these methods allow multiple paths to be watched, as result, the `target` argument to `run_process`
  & `arun_process` is now keyword-only
* the other optional keyword arguments have changed somewhat, mostly as a result of cleanup, all public
  methods are now thoroughly documented

## The old `watchgod` package remains

The old `watchgod` [pypi package](https://pypi.org/project/watchgod/) remains, I'll add a notice about the new
package name, but otherwise It'll continue to work (in future, it might get deprecation warnings).

Documentation is available in [the old README](https://github.com/samuelcolvin/watchfiles/tree/watchgod).
