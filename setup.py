from distutils.core import setup, Command
from distutils import dir_util, file_util
try:
    from distutils.util import Mixin2to3
except ImportError:
    class Mixin2to3:
        pass
from distutils.command.install_data import install_data
from distutils.command.install import INSTALL_SCHEMES
from distutils.command import build
import os
import sys

if sys.version_info < (3,):
    u = unicode
else:
    u = str

try:
    from distutils.command.build_py import build_py_2to3 as build_py
    from lib2to3 import fixes
    from lib2to3 import refactor
    # Drop fixers in 3.0 that do more harm than good
    from lib2to3.fixes import fix_imports, fix_dict
    del fix_imports.MAPPING['commands']
    fix_imports.FixImports.PATTERN="|".join(fix_imports.build_pattern())
    class FixDict(fix_dict.FixDict):
        def transform(self, node, results):
            # .values() is used in Django's ORM; the fixer assumes it's the dict method
            if results["method"][0].value == 'values':
                return
            return super().transform(node, results)
    fix_dict.FixDict = FixDict
except ImportError:
    from distutils.command.build_py import build_py

class osx_install_data(install_data):
    # On MacOS, the platform-specific lib dir is /System/Library/Framework/Python/.../
    # which is wrong. Python 2.5 supplied with MacOS 10.5 has an Apple-specific fix
    # for this in distutils.command.install_data#306. It fixes install_lib but not
    # install_data, which is why we roll our own install_data class.

    def finalize_options(self):
        # By the time finalize_options is called, install.install_lib is set to the
        # fixed directory, so we set the installdir to install_lib. The
        # install_data class uses ('install_data', 'install_dir') instead.
        self.set_undefined_options('install', ('install_lib', 'install_dir'))
        install_data.finalize_options(self)

class build_tests(Command, Mixin2to3):
    # Create mirror copy of tests, convert all .py files using 2to3
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    
    def doctest_2to3(self, filenames):
        from distutils import log
        if filenames:
            log.info("Converting doctests")
        # get all the fixer names
        requested = set(refactor.get_fixers_from_package("lib2to3.fixes"))
        rt_opts = {'print_function': None}
        explicit = set([])
        # Create RefactoringTool subclass, to avoid breaking on errors
        class RefactoringTool(refactor.RefactoringTool):
            def log_error(self, msg, *args, **kw):
                log.error(msg, *args)            
        rt = RefactoringTool(requested, rt_opts, sorted(explicit))
        # XXX 3.1 bug: refactor_doctest looks at rt.log
        rt.log = rt.logger
        rt.refactor(filenames, True, True) # convert with -d flag
    
    def run(self):
        build_base = self.distribution.get_command_obj('build').build_base
        modified = []
        for srcdir, dirnames, filenames in os.walk('tests'):
            destdir = os.path.join(build_base, srcdir)
            dir_util.mkpath(destdir)
            for fn in filenames:
                if fn.startswith("."):
                    continue # skip .svn folders and such
                dstfile, copied = file_util.copy_file(os.path.join(srcdir, fn),
                                                      os.path.join(destdir, fn),
                                                      update=1)
                if fn.endswith('.py') and copied:
                    modified.append(dstfile)
        self.doctest_2to3(modified)
        self.run_2to3(modified)

class build_py3(build.build):
    # New version of build command for Python 3.
    def build_tests(self):
        return sys.version_info >= (3,0)
    sub_commands = build.build.sub_commands + [('build_tests', build_tests)]

if sys.platform == "darwin": 
    cmdclasses = {'install_data': osx_install_data} 
else: 
    cmdclasses = {'install_data': install_data} 

cmdclasses['build_py'] = build_py
cmdclasses['build_tests'] = build_tests
cmdclasses['build'] = build_py3

def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

# Tell distutils to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

# For 2.7 and 3.2, also patch the sysconfig module
try:
    import sysconfig
except ImportError:
    pass
else:
    for name in sysconfig.get_scheme_names():
        scheme = sysconfig.get_paths(name, expand=False)
        scheme['data'] = scheme['purelib']

# Compile the list of packages available, because distutils doesn't have
# an easy way to do this.
packages, data_files = [], []
root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)
django_dir = 'django'

for dirpath, dirnames, filenames in os.walk(django_dir):
    # Ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.'): del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

# Small hack for working with bdist_wininst.
# See http://mail.python.org/pipermail/distutils-sig/2004-August/004134.html
if len(sys.argv) > 1 and sys.argv[1] == 'bdist_wininst':
    for file_info in data_files:
        file_info[0] = '\\PURELIB\\%s' % file_info[0]

# Dynamically calculate the version based on django.VERSION.
version = __import__('django').get_version()
if u('SVN') in version:
    version = ' '.join(version.split(' ')[:-1])

setup(
    name = "Django",
    version = version.replace(' ', '-'),
    url = 'http://www.djangoproject.com/',
    author = 'Django Software Foundation',
    author_email = 'foundation@djangoproject.com',
    description = 'A high-level Python Web framework that encourages rapid development and clean, pragmatic design.',
    download_url = 'http://media.djangoproject.com/releases/1.3/Django-1.3.tar.gz',
    packages = packages,
    cmdclass = cmdclasses,
    data_files = data_files,
    scripts = ['django/bin/django-admin.py'],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
   ],
)
