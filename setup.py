#!usr/bin/env python

try:
    import distribute_setup
    distribute_setup.use_setuptools()
except ImportError:
    # For documentation we load setup.py to get version
    # so it does not matter if importing fails
    pass

import  imp, os, subprocess
from setuptools import setup

# Has to be last import as it seems something is changing it somewhere

NAME = 'Orange'

VERSION = '3.0'
ISRELEASED = False

DESCRIPTION = 'Orange, a component-based data mining framework.'
LONG_DESCRIPTION = open(os.path.join(os.path.dirname(__file__), 'README.txt')).read()
AUTHOR = 'Bioinformatics Laboratory, FRI UL'
AUTHOR_EMAIL = 'contact@orange.biolab.si'
URL = 'http://orange.biolab.si/'
DOWNLOAD_URL = 'https://bitbucket.org/biolab/orange/downloads'
LICENSE = 'GPLv3'

KEYWORDS = (
    'data mining',
    'machine learning',
    'artificial intelligence',
)

CLASSIFIERS = (
    'Development Status :: 4 - Beta',
    'Environment :: X11 Applications :: Qt',
    'Environment :: Console',
    'Environment :: Plugins',
    'Programming Language :: Python',
    'Framework :: Orange',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: POSIX',
    'Operating System :: Microsoft :: Windows',
    'Topic :: Scientific/Engineering :: Artificial Intelligence',
    'Topic :: Scientific/Engineering :: Visualization',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Intended Audience :: Education',
    'Intended Audience :: Science/Research',
    'Intended Audience :: Developers',
)

def hg_revision():
    # Copied from numpy setup.py and modified to work with hg
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout = subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['hg', 'ide', '-i'])
        HG_REVISION = str(out.strip().decode('ascii'))
    except OSError:
        HG_REVISION = "Unknown"

    return HG_REVISION

def write_version_py(filename='Orange/version.py'):
    # Copied from numpy setup.py
    cnt = """
# THIS FILE IS GENERATED FROM ORANGE SETUP.PY
short_version = '%(version)s'
version = '%(version)s'
full_version = '%(full_version)s'
hg_revision = '%(hg_revision)s'
release = %(isrelease)s

if not release:
    version = full_version
"""
    FULLVERSION = VERSION
    if os.path.exists('.hg'):
        HG_REVISION = hg_revision()
    elif os.path.exists('Orange/version.py'):
        # must be a source distribution, use existing version file
        version = imp.load_source("Orange.version", "Orange/version.py")
        HG_REVISION = version.hg_revision
    else:
        HG_REVISION = "Unknown"

    if not ISRELEASED:
        FULLVERSION += '.dev-' + HG_REVISION[:7]

    a = open(filename, 'w')
    try:
        a.write(cnt % {'version': VERSION,
                       'full_version' : FULLVERSION,
                       'hg_revision' : HG_REVISION,
                       'isrelease': str(ISRELEASED)})
    finally:
        a.close()

INSTALL_REQUIRES = (
    'setuptools',
    'numpy',
    'scipy',
    'bottleneck'
)

# TODO: Use entry points for automatic script creation
# http://packages.python.org/distribute/setuptools.html#automatic-script-creation
ENTRY_POINTS = {
}

def setup_package():
    write_version_py()
    setup(
        name = NAME,
        version = VERSION,
        description = DESCRIPTION,
        long_description = LONG_DESCRIPTION,
        author = AUTHOR,
        author_email = AUTHOR_EMAIL,
        url = URL,
        download_url = DOWNLOAD_URL,
        license = LICENSE,
        keywords = KEYWORDS,
        classifiers = CLASSIFIERS,
        packages = ["Orange", "Orange.classification", "Orange.data", "Orange.misc", "Orange.testing", "Orange.tests"],
        install_requires = INSTALL_REQUIRES,
        entry_points = ENTRY_POINTS,
        zip_safe = False,
    )

if __name__ == '__main__':
    setup_package()
