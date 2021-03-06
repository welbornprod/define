#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" define.py
    ...Searches a plain text file from Websters for word definitions.
    -Christopher Welborn 08-15-2014
"""

from collections import OrderedDict
from datetime import datetime
from docopt import docopt
import os
import platform
import re
import sqlite3
import sys


# Try importing the spell-check helper.
# This only works if ASpell is installed, and spell.py is available.
try:
    import spell
except ImportError:
    # Spell checking will not be available. :(
    spell = None
    spellchecker = None
else:
    try:
        spellchecker = spell.SpellChecker()
    except spell.SpellChecker.NotSupported:
        # ASpell is not available.
        spell = None
        spellchecker = None

NAME = 'Define'
VERSION = '0.0.3'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])
OS = platform.system().lower()
USAGESTR = """{versionstr}
    Usage:
        {script} -h | -v
        {script} -c OUTPUTFILE
        {script} WORD...

    Options:
        OUTPUTFILE    : File name for conversions.
        WORD          : Word or words to search for.
        -c,--convert  : Convert dictionary file to an sqlite3 database.
        -h,--help     : Show this help message.
        -v,--version  : Show version.
""".format(script=SCRIPT, versionstr=VERSIONSTR)

DICTFILE = os.path.join(SCRIPTDIR, 'websters_dict_plain.txt')
DICTDB = os.path.join(SCRIPTDIR, 'websters_dict_plain.sqlite3')


def main(argd):
    """ Main entry point, expects docopt arg dict as argd """

    if argd['--convert']:
        print('Converting file: {}'.format(DICTFILE))
        outfile = argd['OUTPUTFILE']
        if outfile == '-':
            outfile = DICTDB
        if not confirm_file(outfile):
            print('\nUser cancelled.\n')
            return 1

        convert_sqlite(outfile)
        print('\nFinished with the conversion: {}'.format(outfile))
        return 1

    ret = 0
    for word in argd['WORD']:
        print_status('Searching for:', value=word)
        lastret = find_definition(word)
        # Exit code shows how many errors there were.
        ret += lastret
    return ret


# Color-coding for definitions.
if OS.startswith('win'):
    # No support for Windows, yet.
    colorword = colordef = colorlist = lambda s: s
else:
    colorword = lambda s: color(s, fore='green', style='bold')
    colordef = lambda s: color(s, fore='blue')
    colorlist = lambda s: color(s, fore='grey')


def confirm(question):
    """ Confirm an action by asking the user a question. """
    question = '\n{} (y/N): '.format(question)
    answer = input(question).lower().strip()
    return answer and answer[0] == 'y'


def confirm_file(filename):
    """ Confirm the user wants to overwrite a file.
        If the file doesn't exist, True is returned.
        Returns False if the user doesn't want to overwrite the file.
    """
    if not os.path.exists(filename):
        return True
    return confirm('This file exists: {}\n\nOverwrite it?'.format(filename))


def convert_pickle(outputfile):
    """ Convert the dictionary to an OrderedDict, and then pickle it. """
    import pickle
    with open(DICTFILE, 'r') as fin:
        with open(outputfile, 'wb') as fout:
            fout.write(pickle.dumps(dict_words(fin)))


def convert_sqlite(outputfile):
    """ Convert the dictionary to an SQLite database. """
    con = create_sqlite_db(outputfile)
    cursor = con.cursor()
    with open(DICTFILE, 'r') as fin:
        for word, defs in dict_words(fin).items():
            insert_into_sqlite_db(cursor, word, defs)
    con.commit()
    con.close()


def create_sqlite_db(outputfile):
    """ Create an empty database to work with, and returns the connection. """
    try:
        os.remove(outputfile)
    except EnvironmentError:
        pass

    con = sqlite3.connect(outputfile)
    cur = con.cursor()

    cur.execute(''.join((
        'CREATE TABLE words (',
        'id INTEGER PRIMARY KEY,'
        'word TEXT',
        ');'
    )))
    con.commit()
    cur.execute(''.join((
        'CREATE TABLE definitions (',
        'word_id REFERENCES words(id),'
        'text TEXT',
        ');'
    )))
    con.commit()

    return con


def dict_words(fileobj):
    """ Iterate over the entire file, and produce a dict of {word: [defs,]} """
    defs = OrderedDict()
    for word, definition in iter_definitions(fileobj):
        if defs.get(word, None):
            defs[word].append(definition)
        else:
            defs[word] = [definition]
    return defs


def find_definition(word, _attempts=0, _starttime=None, _origword=None):
    """ Trys to find the definition for a word. If it can't find it, it will
        check for misspelled words.
    """
    if _starttime is None:
        _starttime = datetime.now()
    if _origword is None:
        _origword = word
    definition = find_word(word)
    duration = (datetime.now() - _starttime)
    if definition:
        print(''.join(('\n', definition)))
        timestr = '{:.3f}'.format(duration.total_seconds())
        print_status('\nTime:', value=timestr)
        return 0

    # See if the word is misspelled.
    if _attempts == 0:
        otherwords = get_suggestions(word)
        if otherwords:
            # The word may have been misspelled.
            print_status('Can\'t find:', value=word)
            # suggestvals = ' '.join(otherwords)
            print_status('Did you mean one of these?:')
            spell.print_corrections(otherwords)
            return 1

    # Can't find alternative spellings,
    # Try the root word, like 'slay' instead of 'slayed' where applicable.
    # This is setup to try only one more time after the initial attempt.
    if _attempts < 2:
        tryword = None
        if word.endswith(('ed', 'er', 'es')):
            tryword = word[:-2]
        elif word.endswith(('ing', 'ify', 'ize')):
            tryword = word[:-3]
        if tryword:
            print_status('Trying', tryword, 'instead...')
            return find_definition(
                tryword,
                _attempts=_attempts + 1,
                _starttime=_starttime,
                _origword=_origword)
    else:
        print_status('Too many attempts,', 'giving up.')
    print_status('Can\'t find:', value=_origword)
    return 1


def find_word(word):
    """ Opens the plain text dictionary file and searches for a word
        and definition.
        If no word is found, '' is returned.
        If the word is found, the definition is returned as str.
    """
    # Try the database first.
    if os.path.exists(DICTDB):
        try:
            con = sqlite3.connect(DICTDB)
        except EnvironmentError as exsqlite:
            print_error(
                'Unable to open the database: {}'.format(DICTDB, exc=exsqlite))
            print('\nFalling back to the plain text file.')
        else:
            try:
                results = find_word_indb(con.cursor(), word)
            except sqlite3.OperationalError:
                print('\nFalling back to the plain text file.')
            else:
                return results
    else:
        print('\nNo database file present, falling back to text.')

    # DB Failed, try the old fashioned method.
    try:
        with open(DICTFILE, 'r') as f:
            return find_word_infile(f, word)
    except EnvironmentError as ex:
        print_fail('Error opening dict file: {}'.format(DICTFILE), exc=ex)


def find_word_indb(cursor, word):
    """ Make SQLite3 do the actual finding.
        Given a connection cursor to the DICTDB database, and a string (word),
        execute a joined select to find a word in the database and the
        definition that references that word.

        Arguments:
            cursor  : sqlite3 connection cursor (sqlite3.connect(DICTDB)).
            word    : word to find ('myword').

        Returns a color-formatted string on success, empty str on failure.
    """

    rows = cursor.execute(''.join((
        'SELECT text FROM definitions JOIN words ',
        'WHERE words.word=? and words.id == definitions.word_id;'
    )), (word.upper(),)).fetchall()
    return format_db_results(word, [r[0] for r in rows])


def find_word_infile(f, word):
    """ Does the actual work of searching for a word in an open file object.
        If no word is found, '' is returned.
        If the word is found, the definition is returned as str.
    """
    # This is what the words look like in the file.
    wordpat = re.compile('^[A-Z\-]+$')
    # This is what the numbered list of defs look like.
    listpat = re.compile('^[1-9]{1,3}\.')
    # Start of a definition
    defstart = 'Defn: '
    defstartlen = len(defstart)
    trimdefstart = lambda s: s[defstartlen:]
    formatdefstart = lambda s: ''.join(('\n', trimdefstart(s)))
    # This will be our result.
    deflines = []
    formatted_defs = lambda: '\n'.join(deflines).strip()

    # Words in the file are uppercase.
    word = word.upper()
    for line in f:
        l = line.strip()
        if not l:
            # Blank line
            continue
        if l.startswith(('*** END', 'End of Project')):
            # End of definitions.
            return formatted_defs()
        if wordpat.match(l):
            if deflines:
                # This is the next word.
                # If it's another definition of our word, continue.
                # Otherwise return what we have.
                if l == word:
                    deflines.append(''.join(('\n', colorword(l))))
                else:
                    return formatted_defs()
            else:
                # We haven't found the word yet.
                # See if this one matches.
                if l == word:
                    # This is the word, add it to the output.
                    deflines.append(colorword(l))
        else:
            if not deflines:
                continue
            # This is part of a definition.
            # If we have already added some lines,
            # this is part of OUR definition.
            if listpat.match(l):
                deflines.append(''.join(('\n', colorlist(l))))
            else:
                if l.startswith(defstart):
                    # Beginning of definition.
                    deflines.append(colordef(formatdefstart(l)))
                else:
                    # Rest of the def.
                    deflines.append(colordef(l))
    # We haven't found anything,
    # or possibly the last word in the file.
    return formatted_defs()


def format_db_results(word, results):
    """ Colors a definition list retrieved from the database. """
    listpat = re.compile('^[1-9]{1,3}\.')
    formatted = []
    for deftext in results:
        # Putting the word here matches plain text results.
        formatted.append('\n{}'.format(colorword(word.upper())))
        for line in deftext.split('\n'):
            if listpat.match(line):
                formatted.append(colorlist(line))
            else:
                formatted.append(colordef(line))
    return '\n'.join(formatted)


def get_suggestions(word):
    """ Get spelling suggestions for a word,
        only if SpellChecker is properly initialized.

        Warning:
            This sometimes suggests words that aren't in the definitions file.

        Returns a list of suggestions, or None  on failure.
    """
    if spellchecker:
        try:
            results = spellchecker.check_word(word)
        except spell.SpellChecker.ASpellError:
            return None
        else:
            if results:
                return results[word]
    return None


def insert_into_sqlite_db(cursor, word, definitions):
    """ Inserts a word and definitions into an sqlite3 database.
        Arguments:
            cursor      : SQLite cursor, with tables set up already.
                          see: create_sqlite_db()
            word        : Word to insert.
            definitions : Iterable of definitions for the word.
    """
    cursor.execute('INSERT INTO words(word) values (?);', (word,))
    rowid = cursor.execute('SELECT max(id) from words;').fetchone()[0]
    if not rowid:
        print('Error! Rowid not set properly!: {}'.format(rowid))
        sys.exit(1)

    for definition in definitions:
        cursor.execute(''.join((
            'INSERT INTO definitions(word_id, text) ',
            'values (?, ?);'
        )), (rowid, definition))
        print('Set def for word_id: {}'.format(rowid))


def iter_definitions(f):
    """ Iterate over the entire file, yielding ('word', 'definition').
        This is not for searching.
        Arguments:
            f  : An open file object, for the dictionary file.
    """
    # This is what the words look like in the file.
    wordpat = re.compile('^[A-Z\-]+$')
    # This is what the numbered list of defs look like.
    listpat = re.compile('^[1-9]{1,3}\.')
    # Start of a definition
    defstart = 'Defn: '
    defstartlen = len(defstart)
    trimdefstart = lambda s: s[defstartlen:]
    formatdefstart = lambda s: ''.join(('\n', trimdefstart(s)))
    # Place holder for results.
    currentword = None
    deflines = None

    formatted_defs = lambda: '\n'.join(deflines).strip()

    for line in f:
        l = line.strip()
        if not l:
            # Blank line
            continue
        if l.startswith(('*** END', 'End of Project')):
            # End of definitions.
            return

        if wordpat.match(l):
            if deflines and (deflines is not None):
                # This is the next word.
                yield currentword, formatted_defs()
            # Start of a word.
            currentword = l
            deflines = []
        else:
            if deflines is None:
                # Skip the header
                continue
            # This is part of a definition.
            # If we have already added some lines,
            # this is part of the current word's definition.
            if listpat.match(l):
                deflines.append('\n{}'.format(l))
            else:
                if l.startswith(defstart):
                    # Beginning of definition.
                    deflines.append(formatdefstart(l))
                else:
                    # Rest of the def.
                    deflines.append(l)
    # The last word in the file.
    if deflines:
        yield currentword, formatted_defs()


def print_error(msg):
    """ Print a red error message. """
    errmsg = color(msg, fore='red')
    print('\n{}\n'.format(errmsg))


def print_fail(msg, exc=None, retcode=1):
    """ Print an error message and exit.
        If 'exc' is passed, print it also.
        if 'retcode' is passed, use it as the return code. (default: 1)
    """
    print_error(msg)
    if exc is not None:
        excmsg = color(str(exc), fore='red', style='bold')
        print('{}\n'.format(excmsg))

    sys.exit(retcode)


def print_status(lblormsg, value=None, endmsg=None):
    """ Print a colored status message.
        If no 'value' is passed, print a simple colored message.
        If 'value' is passed, print a label: value type message with colors.
    """

    msg = color(str(lblormsg), fore='green')
    if value:
        msg = ' '.join((msg, color(str(value), fore='blue', style='bold')))
    if endmsg:
        msg = ' '.join((msg, color(str(endmsg), fore='green')))
    print(msg)


class ColorCodes(object):

    """ This class colorizes text for an ansi terminal.
        Inspired by Colorama (though very different)
    """
    # TODO: Update to colorize.ColorCodes 1.0.2 (with windows support)
    __version__ = '1.0.1-0'

    class Invalid256Color(ValueError):

        """ Just provides a better name than ValueError for bad 256 codes. """
        pass

    def __init__(self):
        # Names and corresponding code number
        namemap = (
            ('black', 0),
            ('red', 1),
            ('green', 2),
            ('yellow', 3),
            ('blue', 4),
            ('magenta', 5),
            ('cyan', 6),
            ('white', 7)
        )
        self.codes = {'fore': {}, 'back': {}, 'style': {}}
        # Set codes for forecolors (30-37) and backcolors (40-47)
        for name, number in namemap:
            self.codes['fore'][name] = str(30 + number)
            self.codes['back'][name] = str(40 + number)
            lightname = 'light{}'.format(name)
            self.codes['fore'][lightname] = str(90 + number)
            self.codes['back'][lightname] = str(100 + number)

        # Set reset codes for fore/back.
        self.codes['fore']['reset'] = '39'
        self.codes['back']['reset'] = '49'

        # Map of code -> style name/alias.
        stylemap = (
            ('0', ['r', 'reset', 'reset_all']),
            ('1', ['b', 'bright', 'bold']),
            ('2', ['d', 'dim']),
            ('3', ['i', 'italic']),
            ('4', ['u', 'underline', 'underlined']),
            ('5', ['f', 'flash']),
            ('7', ['h', 'highlight', 'hilight', 'hilite', 'reverse']),
            ('22', ['n', 'normal', 'none'])
        )
        # Set style codes.
        for code, names in stylemap:
            for alias in names:
                self.codes['style'][alias] = code

        # Format string for full color code.
        self.codeformat = '\033[{}m'
        self.codefmt = lambda s: self.codeformat.format(s)
        self.closing = '\033[m'
        # Extended (256 color codes)
        self.extforeformat = '\033[38;5;{}m'
        self.extforefmt = lambda s: self.extforeformat.format(s)
        self.extbackformat = '\033[48;5;{}m'
        self.extbackfmt = lambda s: self.extbackformat.format(s)

        # Shortcuts to most used functions.
        self.word = self.colorword
        self.ljust = self.wordljust
        self.rjust = self.wordrjust

    def color_code(self, fore=None, back=None, style=None):
        """ Return the code for this style/color
        """

        codes = []
        userstyles = {'style': style, 'back': back, 'fore': fore}
        for stype in userstyles:
            style = userstyles[stype].lower() if userstyles[stype] else None
            # Get code number for this style.
            code = self.codes[stype].get(style, None)
            if code:
                # Reset codes come first (or they will override other styles)
                codes.append(code)

        return self.codefmt(';'.join(codes))

    def color256(self, text=None, fore=None, back=None, style=None):
        """ Return a colored word using the extended 256 colors.
        """
        text = text or ''
        codes = []
        if style is not None:
            userstyle = self.codes['style'].get(style, None)
            if userstyle:
                codes.append(self.codefmt(userstyle))
        if back is not None:
            codes.append(self.make_256color('back', back))
        if fore is not None:
            codes.append(self.make_256color('fore', fore))

        codes.extend([
            text,
            self.codes['style']['reset_all'],
            self.closing
        ])
        return ''.join(codes)

    def colorize(self, text=None, fore=None, back=None, style=None):
        """ Return text colorized.
            fore,back,style  : Name of fore or back color, or style name.
        """
        text = text or ''

        return ''.join((
            self.color_code(style=style, back=back, fore=fore),
            text,
            self.closing))

    def colorword(self, text=None, fore=None, back=None, style=None):
        """ Same as colorize, but adds a style->reset_all after it. """
        text = text or ''
        colorized = self.colorize(text=text, style=style, back=back, fore=fore)
        s = ''.join((
            colorized,
            self.color_code(style='reset_all'),
            self.closing))
        return s

    def make_256color(self, colortype, val):
        """ Create a 256 color code based on type ('fore' or 'back')
            out of a number (can be string).
            Raises ColorCodes.Invalid256Color() on error.
            Returns the raw color code on success.
        """
        try:
            ival = int(val)
        except (TypeError, ValueError) as ex:
            raise self.make_256error(colortype, val) from ex
        else:
            if (ival < 0) or (ival > 255):
                raise self.make_256error(colortype, val)
        if colortype == 'fore':
            return self.extforefmt(str(ival))
        elif colortype == 'back':
            return self.extbackfmt(str(ival))

        # Should not make it here. Developer error.
        errmsg = 'Invalid colortype: {}'.format(colortype)
        raise ColorCodes.Invalid256Color(errmsg)

    def make_256error(self, colortype, val):
        """ Create a new "invalid 256 color number" error based on
            'fore' or 'back'.
            Returns the error, does not raise it.
        """
        errmsg = ' '.join((
            'Invalid number for {}: {}'.format(colortype, val),
            'Must be in range 0-255'))
        return ColorCodes.Invalid256Color(errmsg)

    def wordljust(self, text=None, length=0, char=' ', **kwargs):
        """ Color a word and left justify it.
            Regular str.ljust won't work properly on a str with color codes.
            You can do colorword(s.ljust(length), fore='red') though.
            This adds the space before the color codes.
            Arguments:
                text    : text to colorize.
                length  : overall length after justification.
                char    : character to use for padding. Default: ' '

            Keyword Arguments:
                fore, back, style : same as colorizepart() and word()
        """
        text = text or ''
        spacing = char * (length - len(text))
        colored = self.colorword(text=text, **kwargs)
        return '{}{}'.format(colored, spacing)

    def wordrjust(self, text=None, length=0, char=' ', **kwargs):
        """ Color a word and right justify it.
            Regular str.rjust won't work properly on a str with color codes.
            You can do colorword(s.rjust(length), fore='red') though.
            This adds the space before the color codes.
            Arguments:
                text    : text to colorize.
                length  : overall length after justification.
                char    : character to use for padding. Default: ' '

            Keyword Arguments:
                fore, back, style : same as colorizepart() and word()
        """
        text = text or ''
        spacing = char * (length - len(text))
        colored = self.word(text=text, **kwargs)
        return '{}{}'.format(spacing, colored)

# Colorizer aliases (if supported)
if OS.startswith('win'):
    # No windows color support, yet.
    colorize = None

    def color(text=None, fore=None, back=None, style=None):
        return text
else:
    # Alias, convenience function for ColorCodes().
    colorize = ColorCodes()
    color = colorize.colorword

if __name__ == '__main__':
    mainret = main(docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)
