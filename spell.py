#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" spell.py
    ...A quick spell checker using the 'aspell' command.
    This module also provides a SpellChecker() class to use in other
    projects.
    -Christopher Welborn 08-15-2014
"""

from docopt import docopt
from subprocess import Popen, PIPE
from tempfile import SpooledTemporaryFile
import os
import subprocess
import sys

NAME = 'Spell'
VERSION = '0.0.3'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPTDIR, SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))

USAGESTR = """{versionstr}
    Usage:
        {script} -h | -v
        {script} WORD... [-i] [-D]
        {script} -s [-i] [-D]

    Options:
        WORD            : One or many words to spell check.
                          You can also just pass them as a single string.
        -D,--debug      : Shows more debugging info.
        -h,--help       : Show this help message.
        -i,--incorrect  : Only show the incorrect words.
        -s,--stdin      : Use stdin to read words from.
                          Ex: echo "test" | {script}
        -v,--version    : Show version.

    The return code is the number of misspelled words overall.
    Aspell has a large vocabulary, but it isn't perfect.
    This script will tell you if the word you are checking can't be found.
""".format(script=SCRIPT, versionstr=VERSIONSTR)

# Global debug flag, set with -D,--debug
DEBUG = False


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """
    global DEBUG
    DEBUG = argd['--debug']

    try:
        spellcheck = SpellChecker()
    except SpellChecker.NotSupported as ex:
        print('\nError:\n{}\n'.format(ex))
        return 1

    if argd['WORD']:
        words = argd['WORD']
    elif argd['--stdin']:
        words = sys.stdin.read().split()

    allresults = {}
    hidecorrect = argd['--incorrect']
    for res in spellcheck.check_words_iter(words, include_empty=hidecorrect):
        print_wordresults(res)
        allresults.update(res)

    # Filter out the correct words, leaving only words that errored.
    errorcount = [w for w in filter(lambda k:allresults[k], allresults)]
    # Return code is the number of misspelled words.
    return len(errorcount)


def format_group(grp, longest):
    """ Format a group of corrections for printing.
        This also adds indention.
    """
    formatted = (color(s.ljust(longest), fore='blue') for s in grp)
    return '    {}'.format(''.join(formatted))


def print_wordresults(parsed, hidecorrect=False):
    """ Print color-coded word corrections. """
    for word, corrected in parsed.items():
        if corrected:
            wordcolor = color(word, fore='red', style='bold')
            print(''.join(('\n', wordcolor, ':')))
            # Get longest correction, for formatting. (with room for a space)
            longest = len(max(corrected, key=len)) + 1
            # Make the rows fit within 80 chars (with a 4 space indent.)
            rowcnt = 76 // longest
            for i in range(0, len(corrected), rowcnt):
                correctgrp = (s for s in corrected[i:i + rowcnt])
                print(format_group(correctgrp, longest))
        elif not hidecorrect:
            print(color(word, fore='green'))


def printdebug(s):
    """ Print a debug message, only if DEBUG is truthy. """
    if DEBUG:
        debuglbl = color('DEBUG: ', fore='green')
        print('{}{}'.format(debuglbl, s))


class SpellChecker(object):

    """ A class that uses ASpell to check the spelling of words,
        and suggest possible fixes.
    """
    class ASpellError(Exception):

        """ Raised when aspell produces an error, or has zero output. """
        pass

    class NotSupported(Exception):

        """ Raised when aspell can't be found. """
        pass

    def __init__(self):
        """ Initializes the spell checker, raises SpellChecker.NotSupported()
            if ASpell can't be found.
        """
        self.aspell_exe = self.which_aspell()

    def check_word(self, s):
        """ Check a string/word for correctness.
            Return a dict of {misspelled: possible_corrections}
            If the word is correct, return {}
            If there is no output from aspell, ASpellError is raised.
        """
        aspellexe = self.aspell_exe or self.which_aspell()
        aspellcmd = [aspellexe, '-a']
        with TempInput(s) as stdin:
            proc = Popen(aspellcmd, stdin=stdin, stdout=PIPE, stderr=PIPE)
            stdout, stderr = self.proc_output(proc)
        if stderr:
            # This is fatal.
            errmsg = 'Aspell returned an error:\n{}'.format(stderr)
            raise SpellChecker.ASpellError(errmsg)

        if stdout:
            return self.parse_aspell(s, stdout)

        # This is fatal.
        raise SpellChecker.ASpellError('\nASpell had no output.')

    def check_words_iter(self, words, include_empty=True):
        """ Checks an iterable of words using check_word() and yields each
            result as it is encountered.

            Arguments:
                words         : An iterable of words to check.
                include_empty : If True, yield words with empty results.
                                Default: True

            Raises SpellChecker.ASpellError.
        """
        for word in words:
            results = self.check_word(word)
            if (not include_empty) and (not results):
                continue
            yield results

    def check_words(self, words):
        """ Checks an iterable of words using check_word() and merges
            the results.
            Raises SpellChecker.ASpellError.
            Returns a dict of results.
        """
        allresults = {}
        for results in self.check_words_iter(words, include_empty=True):
            allresults.update(results)
        return allresults

    @staticmethod
    def parse_aspell(original, s):
        """ Parse aspell output.
            Returns a dict of {mispelled: possible_corrections}
            If all words were correct, returns {}
        """
        corrections = {}
        for line in s.split('\n'):
            if line.startswith('&'):
                # This is a correction.
                wordinfo, correctioninfo = line.strip().split(':')
                word = wordinfo.split(' ')[1]
                correctwords = correctioninfo.strip().split(', ')
                corrections[word] = correctwords
            elif line.startswith('#'):
                # This word was not found.
                word = line.split(' ')[1]
                corrections[word] = ['<not found>']

        for word in original.split(' '):
            if word not in corrections:
                corrections[word] = None
        return corrections

    @staticmethod
    def proc_output(proc):
        """ Get process output, whether its on stdout or stderr.
            Arguments:
                proc  : a POpen() process to get output from.
        """
        # Get stdout
        outlines = []
        for line in iter(proc.stdout.readline, b''):
            if line:
                line = line.decode('utf-8')
                outlines.append(line.strip('\n'))

        # Get stderr
        errlines = []
        for line in iter(proc.stderr.readline, b''):
            if line:
                line = line.decode('utf-8')
                errlines.append(line.strip('\n'))

        return ('\n'.join(outlines).strip(), '\n'.join(errlines).strip())

    @staticmethod
    def which_aspell():
        """ Retrieve command locations using 'which' command.
            If the command isn't found, return None.
        """
        loc = subprocess.getoutput('which aspell')
        if 'not found' in loc:
            # The which command is unavailable.
            defaultaspell = '/usr/bin/aspell'
            if os.path.exists(defaultaspell):
                # Default location was good.
                return defaultaspell

            # Don't know if aspell is installed or not.
            errmsg = '\n'.join((
                '\'which\' command unavailable,',
                'unable to determine location of aspell!'))
            raise SpellChecker.NotSupported(errmsg)

        # Which command worked, still may not be an aspell though.
        if os.path.exists(loc):
            return loc

        # No aspell command available.
        raise SpellChecker.NotSupported('Can\'t find the aspell executable.')


class TempInput(object):

    """ Acts as STDIN for a Popen process.
        Initialize with the string you want to send on startup.
        Enoding can be set with the optional 'encoding' arg.
    """

    def __init__(self, inputstr, encoding=None):
        self.encoding = encoding or 'utf-8'
        self.inputstr = inputstr.encode(self.encoding)

    def __enter__(self):
        self.tempfile = SpooledTemporaryFile()
        self.tempfile.write(self.inputstr)
        self.tempfile.seek(0)
        return self.tempfile

    def __exit__(self, type_, value, traceback):
        self.tempfile.close()
        return False


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
