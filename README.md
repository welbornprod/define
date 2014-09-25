define
======

Retrieves word definitions from the command line. It includes a text
file containing a good portion of Webster's dictionary. The definitions
have also been converted to an SQLite database. This tool will use the
database if available, and then the plain text file.

Requirements:
-------------

* docopt - http://docopt.org


Usage:
--------

```
    Usage:
        define -h | -v
        define WORD

    Options:
        WORD          : Word to search for.
        -h,--help     : Show this help message.
        -v,--version  : Show version.
```

spell.py
---------

This also includes a small spell-check utility that uses ASpell to provide
spelling suggestions.
When `/usr/bin/aspell` is available, you can use `spell.py` as a standalone
tool for checking your spelling.

 `define.py` will use this to provide spelling suggestions when available.
