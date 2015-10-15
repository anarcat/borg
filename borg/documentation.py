import argparse
import datetime
from distutils.core import Command
from distutils.errors import DistutilsOptionError
import os
import time

class build_usage(Command):
    description = "generate usage for each command"

    user_options = [
        ('output=', 'O', 'output directory'),
    ]
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print('generating usage docs')
        # allows us to build docs without the C modules fully loaded during help generation
        if 'BORG_CYTHON_DISABLE' not in os.environ:
            os.environ['BORG_CYTHON_DISABLE'] = self.__class__.__name__
        from borg.archiver import Archiver
        parser = Archiver().build_parser(prog='borg')
        choices = {}
        for action in parser._actions:
            if action.choices is not None:
                choices.update(action.choices)
        print('found commands: %s' % list(choices.keys()))
        if not os.path.exists('docs/usage'):
            os.mkdir('docs/usage')
        for command, parser in choices.items():
            if command is 'help':
                continue
            with open('docs/usage/%s.rst.inc' % command, 'w') as doc:
                print('generating help for %s' % command)
                params = {"command": command,
                          "underline": '-' * len('borg ' + command)}
                doc.write(".. _borg_{command}:\n\n".format(**params))
                doc.write("borg {command}\n{underline}\n::\n\n".format(**params))
                epilog = parser.epilog
                parser.epilog = None
                doc.write(re.sub("^", "    ", parser.format_help(), flags=re.M))
                doc.write("\nDescription\n~~~~~~~~~~~\n")
                doc.write(epilog)
        # return to regular Cython configuration, if we changed it
        if os.environ.get('BORG_CYTHON_DISABLE') == self.__class__.__name__:
            del os.environ['BORG_CYTHON_DISABLE']


class build_api(Command):
    description = "generate a basic api.rst file based on the modules available"

    user_options = [
        ('output=', 'O', 'output directory'),
    ]
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print("auto-generating API documentation")
        with open("docs/api.rst", "w") as doc:
            doc.write("""
Borg Backup API documentation
=============================
""")
            for mod in glob('borg/*.py') + glob('borg/*.pyx'):
                print("examining module %s" % mod)
                mod = mod.replace('.pyx', '').replace('.py', '').replace('/', '.')
                if "._" not in mod:
                    doc.write("""
.. automodule:: %s
    :members:
    :undoc-members:
""" % mod)


class build_manpage(Command):

    description = 'Generate man page from setup().'

    user_options = [
        ('output=', 'O', 'output directory'),
        ('parsers=', None, 'module path to argparser (e.g. command:mymod:func)'),
        ]

    def initialize_options(self):
        self.output = 'man'
        self.parsers = None

    def finalize_options(self):
        if self.output is None:
            raise DistutilsOptionError('\'output\' option is required')
        if self.parsers is None:
            raise DistutilsOptionError('\'parser\' option is required')
        self._today = datetime.date.fromtimestamp(float(os.getenv('BUILD_TIMESTAMP', time.time())))
        self._parsers = []
        for parser in self.parsers.split():
            scriptname, mod_name, func_name = parser.split(':')
            fromlist = mod_name.split('.')
            try:
                class_name, func_name = func_name.split('.')
            except ValueError:
                class_name = None
            mod = __import__(mod_name, fromlist=fromlist)
            if class_name is not None:
                cls = getattr(mod, class_name)
                try:
                    parser = getattr(cls, func_name)()
                except TypeError:
                    # e.g. "TypeError: build_parser() missing 1 required positional argument: 'self'"
                    # that is, it's not class or static method, so instanciate an object
                    parser = getattr(cls(), func_name)()
            else:
                parser = getattr(mod, func_name)()
            parser.formatter = ManPageFormatter(scriptname)
            #parser.formatter.set_parser(parser)
            parser.prog = scriptname
            self._parsers.append(parser)

    def _markup(self, txt):
        return txt.replace('-', '\\-')

    def _write_header(self, parser):
        appname = parser.prog
        ret = []
        ret.append('.TH %s 1 %s\n' % (self._markup(appname),
                                      self._today.strftime('%Y\\-%m\\-%d')))
        description = parser.description
        if description:
            name = self._markup('%s - %s' % (self._markup(appname),
                                             description.splitlines()[0]))
        else:
            name = self._markup(appname)
        ret.append('.SH NAME\n%s\n' % name)
        # override argv, we need to format it later
        prog_bak = parser.prog
        parser.prog = ''
        epilog = parser.epilog
        parser.epilog = None
        synopsis = parser.format_help().lstrip(' ')
        parser.epilog = epilog
        parser.prog = prog_bak
        if synopsis:
            ret.append('.SH SYNOPSIS\n.B %s\n%s\n' % (self._markup(appname),
                                                      synopsis))
        long_desc = parser.epilog
        if long_desc:
            ret.append('.SH DESCRIPTION\n%s\n' % self._markup("\n".join(long_desc.splitlines()[1:])))
        return ''.join(ret)

    def _write_options(self, parser):
        ret = ['.SH OPTIONS\n']
        #ret.append(parser.format_option_help())
        return ''.join(ret)

    def _write_footer(self, parser):
        ret = []
        appname = self.distribution.get_name()
        author = '%s <%s>' % (self.distribution.get_author(),
                              self.distribution.get_author_email())
        ret.append(('.SH AUTHORS\n.B %s\nwas written by %s.\n'
                    % (self._markup(appname), self._markup(author))))
        homepage = self.distribution.get_url()
        ret.append(('.SH DISTRIBUTION\nThe latest version of %s may '
                    'be downloaded from\n'
                    '.UR %s\n.UE\n'
                    % (self._markup(appname), self._markup(homepage),)))
        return ''.join(ret)

    def run(self):
        for parser in self._parsers:
            manpage = []
            manpage.append(self._write_header(parser))
            manpage.append(self._write_options(parser))
            manpage.append(self._write_footer(parser))
            try:
                os.mkdir(self.output)
            except OSError:
                # ignore already existing directory
                pass
            path = os.path.join(self.output, parser.prog + '.1')
            self.announce('writing man page to %s' % path, 2)
            stream = open(path, 'w')
            stream.write(''.join(manpage))
            stream.close()


class ManPageFormatter(argparse.HelpFormatter):

    def __init__(self, prog,
                 indent_increment=2,
                 max_help_position=24,
                 width=None):
        argparse.HelpFormatter.__init__(self, prog,
                                        indent_increment=indent_increment,
                                        max_help_position=max_help_position,
                                        width=width)

    def _markup(self, txt):
        return txt.replace('-', '\\-')

    def format_usage(self, usage):
        return self._markup(usage)

    def format_heading(self, heading):
        if self.level == 0:
            return ''
        return '.TP\n%s\n' % self._markup(heading.upper())

    def format_option(self, option):
        result = []
        opts = self.option_strings[option]
        result.append('.TP\n.B %s\n' % self._markup(opts))
        if option.help:
            help_text = '%s\n' % self._markup(self.expand_default(option))
            result.append(help_text)
        return ''.join(result)
