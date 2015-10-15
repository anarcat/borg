from distutils.core import Command
from distutils.errors import DistutilsOptionError

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
