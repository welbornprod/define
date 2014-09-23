#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" define.py
    ...Searches a plain text file from Websters for word definitions.
    -Christopher Welborn 08-15-2014
"""

from datetime import datetime
from docopt import docopt
import os
import re
import sys

# Try importing the spell-check helper.
# This only works if ASpell is installed, and the spell.py module is available.
try:
    from spell import SpellChecker
except ImportError:
    # Spell checking will not be available. :(
    spellchecker = None
else:
    try:
        spellchecker = SpellChecker()
    except SpellChecker.NotSupported:
        # ASpell is not available.
        spellchecker = None

NAME = 'Define'
VERSION = '0.0.2'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])

USAGESTR = """{versionstr}
    Usage:
        {script} -h | -v
        {script} WORD

    Options:
        WORD          : Word to search for.
        -h,--help     : Show this help message.
        -v,--version  : Show version.
""".format(script=SCRIPT, versionstr=VERSIONSTR)

DICTFILE = os.path.join(SCRIPTDIR, 'websters_dict_plain.txt')


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """
    if not os.path.exists(DICTFILE):
        print_fail('Missing dictionary file: {}'.format(DICTFILE))

    word = argd['WORD']
    print_status('Searching for:', value=word)
    starttime = datetime.now()
    definition = find_word(word)
    duration = (datetime.now() - starttime)
    if definition:
        print(''.join(('\n', definition)))
        timestr = '{:.3f}'.format(duration.total_seconds())
        print_status('\nTime:', value=timestr)
    else:
        otherwords = get_suggestions(word)
        if otherwords:
            print_status('Can\'t find:', value=word)
            suggestvals = ' '.join(otherwords)
            print_status('Did you mean one of these?:', value=suggestvals)
            return 1
        else:
            print_fail('Can\'t find: {}'.format(word))

    return 0

# Color-coding for definitions.
colorword = lambda s: color(s, fore='green', style='bold')
colordef = lambda s: color(s, fore='blue')
colorlist = lambda s: color(s, fore='grey')


def find_word(word):
    """ Opens the plain text dictionary file and searches for a word
        and definition.
        If no word is found, '' is returned.
        If the word is found, the definition is returned as str.
    """
    try:
        with open(DICTFILE, 'r') as f:
            return find_word_infile(f, word)
    except EnvironmentError as ex:
        print_fail('Error opening dict file: {}'.format(FILENAME), exc=ex)


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


def get_suggestions(word):
    """ Get spelling suggestions for a word,
        only if SpellChecker is properly initialized.

        Returns a list of suggestions, or None  on failure.
    """
    if spellchecker:
        try:
            results = spellchecker.check_word(word)
        except SpellChecker.ASpellError:
            return None
        else:
            if results:
                return results[word]
    return None


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


def print_status(lblormsg, value=None):
    """ Print a colored status message.
        If no 'value' is passed, print a simple colored message.
        If 'value' is passed, print a label: value type message with colors.
    """

    msg = color(str(lblormsg), fore='green')
    if value:
        msg = ' '.join((msg, color(str(value), fore='blue', style='bold')))
    print(msg)


class ColorCodes(object):

    """ This class colorizes text for an ansi terminal.
        Inspired by Colorama (though very different)
    """
    class Invalid256Color(ValueError):
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

# Alias, convenience function for ColorCodes().
colorize = ColorCodes()
color = colorize.colorword

if __name__ == '__main__':
    mainret = main(docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)
