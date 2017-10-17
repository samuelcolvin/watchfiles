watchgod
========

|BuildStatus| |Coverage| |pypi|

Simple, modern file watching and code reload in python.

Usage
-----

To watch for changes in a directory:

.. code:: python

   from watchgod import watch

   for changes in watch('./path/to/dir'):
       print(changes)


To run a function and restart it when code changes:

.. code:: python

   from watchgod import run_process

   def foobar(a, b, c):
       ...

   run_process('./path/to/dir', foobar, process_args=(1, 2, 3))


*watchgod* comes with an "async" equivalents of ``watch``: ``awatch`` which uses
a ``ThreadPoolExecutor`` to iterate over files.

.. code:: python

   import asyncio
   from watchgod import awatch

   async def main():
       async for changes in awatch('/path/to/dir'):
           print(changes)

   loop = asyncio.get_event_loop()
   loop.run_until_complete(main())


Why no inotify / kqueue / fsevent / winapi
------------------------------------------

*watchgod* (for now) uses file polling rather than the OS's built in file change notifications.

This is not an oversight, it's a decision with the following rationale:

1. Polling is "fast enough", particularly since PEP 471 introduced fast ``scandir``.

   With a reasonably large project like the TutorCruncher code base with 850 files and 300k lines
   of code *watchdog* can scan the entire tree in 24ms. With a scan interval of 400ms that's roughly
   5% of one CPU - perfectly acceptable load during development.

2. The clue is in the title, there are at least 4 different file notification systems to integrate
   with, most of them not trivial. And that's before we get to changes between different OS versions.

3. Polling works well when you want to group or "debounce" changes.

   Let's say you're running a dev server and you change branch in git, 100 files change.
   Do you want to reload the dev server 100 times or once? Right.

   Polling periodically will likely group these changes into one event. If you're receiving a
   stream of events you need to delay execution of the reload when you receive the first event
   to see if it's part of a whole bunch of file changes, this is not completely trivial.


All that said, I might still implement ``inotify`` support. I don't use anything other
than Linux so I definitely won't be working on dedicated support for any other OS.


.. |BuildStatus| image:: https://travis-ci.org/samuelcolvin/watchgod.svg?branch=master
   :target: https://travis-ci.org/samuelcolvin/watchgod
.. |Coverage| image:: https://codecov.io/gh/samuelcolvin/watchgod/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/samuelcolvin/watchgod
.. |pypi| image:: https://img.shields.io/pypi/v/watchgod.svg
   :target: https://pypi.python.org/pypi/watchgod
