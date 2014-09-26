define
======

Retrieves word definitions from the command line. It includes a text
file containing a good portion of Webster's dictionary. The definitions
have also been converted to an SQLite database. This tool will use the
database if available, and then the plain text file.

I recommend creating a symlink in `/usr/bin`, `~/.local/bin`, or some other
place in your `$PATH` like this:

`ln -s /path/to/define.py ~/.local/bin/define`

Requirements:
-------------

* docopt - http://docopt.org (handles cmdline arg parsing)


Usage:
--------
**Example:** 

`define apple`

**Options**:

```help
    Usage:
        define -h | -v
        define WORD

    Options:
        WORD          : Word to search for.
        -h,--help     : Show this help message.
        -v,--version  : Show version.
```

spell.py
--------

This also includes a small spell-check utility that uses ASpell to provide
spelling suggestions.
When `/usr/bin/aspell` is available, you can use `spell.py` as a standalone
tool for checking your spelling.

 `define.py` will use this to provide spelling suggestions when available.

**Example:**

`spell pythin`

**Example Output:**

```
pythin:
    Python    python    pythons   Putin     thin      Pythias   Petain    
    within    Python's  plaything python's  thine     thing     PIN       
    patching  pin       pitching  patina    patine    potion    pain      
    path      pith      than      then      Scythian  scything  Parthia   
    pithier   pithy    
```

When you spell the word correctly, is it repeated back to you. If the word is unknown a warning is emitted:

```
spell supercalifragilistic

supercalifragilistic:
    <not found> 
```

**Options:**

```help
    Usage:
        spell -h | -v
        spell WORD... [-i] [-D]
        spell -s [-i] [-D]

    Options:
        WORD            : One or many words to spell check.
                          You can also just pass them as a single string.
        -D,--debug      : Shows more debugging info.
        -h,--help       : Show this help message.
        -i,--incorrect  : Only show the incorrect words.
        -s,--stdin      : Use stdin to read words from.
                          Ex: echo "test" | spell
        -v,--version    : Show version.
```
