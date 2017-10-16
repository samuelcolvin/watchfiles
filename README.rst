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


.. |BuildStatus| image:: https://travis-ci.org/samuelcolvin/watchgod.svg?branch=master
   :target: https://travis-ci.org/samuelcolvin/watchgod
.. |Coverage| image:: https://codecov.io/gh/samuelcolvin/watchgod/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/samuelcolvin/watchgod
.. |pypi| image:: https://img.shields.io/pypi/v/watchgod.svg
   :target: https://pypi.python.org/pypi/watchgod
