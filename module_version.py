__version__ = '{tag}'
__revision__ = ''

import os
import sys
import os.path as os_path
import re
import subprocess
from distutils.core import Command
from distutils.command.build_py import build_py as _build_py
from distutils.errors import DistutilsOptionError

RE_VERSION = re.compile(br'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', re.M)
RE_REVISION = re.compile(br'^__revision__\s*=\s*[\'"][\'"]', re.M)
RE_SETUP = re.compile(br'([(,]\s*version\s*=\s*)([(].*?[)]|[^,)]+)', re.M + re.S)


def get_version(fname):
    with open(fname, "rb") as f:
        content = f.read()
    g = RE_VERSION.search(content)
    if g is None:
        raise Exception("No version found in {}".format(fname))
    return g.group(1)


def replace_setup_file(fname, version):
    with open(fname, "rb") as f:
        content = f.read()
    content = RE_SETUP.sub(b"\\1'{}'".format(version), content, count=1)
    os.unlink(fname)
    with open(fname, "wb") as f:
        f.write(content)


def replace_info_file(fname, version, revision):
    with open(fname, "rb") as f:
        content = f.read()
    content = RE_VERSION.sub(b"__version__ = '{}'".format(version), content, count=1)
    def rev(arg):
        return b"__revision__ = '{}'".format(revision(), count=1)
    content = RE_REVISION.sub(rev, content)
    os.unlink(fname)
    with open(fname, "wb") as f:
        f.write(content)

def write_version(fname, version):
    with open(fname, "wb") as f:
        f.write(version)

class LazyFormat(object):
    def __init__(self, method):
        self.method = method
    
    def __format__(self, cls_format):
        return self.method()


class Version(object):
    @staticmethod
    def jenkins():
        return os.environ['BUILD_NUMBER']
    
    @staticmethod
    def version_from_parts(major=None, minor=None, dirty=None):
        parts = []
        if major:
            parts.append(major)
        if minor or dirty:
            parts.append("{}{}".format(minor if minor else "0", "dev" if dirty else ""))
        return ".".join(parts)
    
    @classmethod
    def tag(cls):
        version = subprocess.check_output("git describe --tags --dirty --always", shell=True).strip()
        parts = version.split("-")
        dirty = minor = None 
        if parts[-1] == "dirty":
            parts = parts[:-1]
            dirty = True  

        major = parts[0].lstrip("v")
        if len(parts) > 1:
            minor = parts[1]
    
        return cls.version_from_parts(major=major, minor=minor, dirty=dirty)

    @staticmethod
    def revision():
        revision = subprocess.check_output("git rev-parse --short `git rev-list -1 HEAD -- .`", shell=True).strip()
        return revision
    
    @classmethod
    def commits(cls):
        minor = subprocess.check_output("git rev-list HEAD --count .", shell=True).strip()
        dirty = subprocess.call("git diff-index --quiet HEAD .", shell=True) != 0
        return cls.version_from_parts(minor=minor, dirty=dirty)
        
    @classmethod
    def format(cls, version):
        attribs = ('jenkins', 'tag', 'commits')
        attribs = { attrib: LazyFormat(getattr(cls, attrib)) for attrib in attribs}
        return version.format(**attribs)


def subclassed_build_py(_build_py):
    class build_py(_build_py):
        def initialize_options(self):
            _build_py.initialize_options(self)
            self.last_version_file = None
            self.set_undefined_options('if_changed', ('last_version_file', 'last_version_file'))
        
        def run(self):
            _build_py.run(self)
            version_file = getattr(self.distribution.metadata, "version_file", None)
            if version_file is None:
                return
            version = self.distribution.metadata.version
            fname = os_path.join(self.build_lib, version_file)
            replace_info_file(fname, version, Version.revision)
            if self.last_version_file:
                write_version(self.last_version_file, version)
            print "File {} updated with version {}".format(fname, version)
    
    return build_py


def subclassed_sdist(_sdist):
    class sdist(_sdist):
        def initialize_options(self):
            _sdist.initialize_options(self)
            self.last_version_file = None
            self.set_undefined_options('if_changed', ('last_version_file', 'last_version_file'))

        def make_release_tree(self, base_dir, files):
            print files
            version_file = getattr(self.distribution.metadata, "version_file", None)
            _sdist.make_release_tree(self, base_dir, files)
            if version_file is None:
                return

            fname = os_path.join(base_dir, version_file)
            version = self.distribution.metadata.version
            replace_info_file(fname, version, Version.revision)
            replace_setup_file(os_path.join(base_dir, "setup.py"), version)
            if self.last_version_file:
                write_version(self.last_version_file, version)
            print "File {} updated with version {}".format(fname, version)
    
    return sdist


class BuildIfChanged(Command):
    """setuptools Command"""
    description = "build only if version changed"
    user_options = [("last-version-file=", None, "Cache file to store last built version")]

    def initialize_options(self):
        self.last_version_file = None
        
    def finalize_options(self):
        if self.last_version_file is None:
            raise DistutilsOptionError("Parameter 'last_version_file' is required for command 'is_changed'")

    def run(self):
        print self.last_version_file
        version = self.distribution.metadata.version
        if self.last_version_file and os_path.isfile(self.last_version_file):
            with open(self.last_version_file, "r") as f:
                last_version = f.read().strip()
    
            if last_version == version:
                print "Version {} not changed. Build stopped, remove 'if_changed' to force.".format(last_version)
                sys.exit()
            print "Version changed from {} to {}".format(last_version, version)

def version_file(version, source=True):
    if isinstance(version, tuple):
        return version[0] if source else version[1]
    return version

def validate_version(dist, attr, value):
    original_version = dist.metadata.version
    if original_version is None:
        return
    src_version_file = version_file(original_version)
    if not src_version_file.endswith(".py"):
        return
    dist.metadata.version_file = version_file(original_version, source=False)
    original_version = get_version(src_version_file)
    dist.metadata.version = Version.format(original_version)
    
    if "setuptools" in sys.modules:
        from setuptools.command.sdist import sdist as _sdist
    else:
        from distutils.command.sdist import sdist as _sdist
        
    dist.cmdclass["sdist"] = subclassed_sdist(dist.cmdclass.get("sdist", _sdist))
    dist.cmdclass["build_py"] = subclassed_build_py(dist.cmdclass.get("build_py", _build_py))

