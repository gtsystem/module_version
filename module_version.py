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
RE_SETUP = re.compile(br'([(,]\s*version\s*=\s*)[^,)]+', re.M + re.S)


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
    content = RE_SETUP.sub("\\1'{}'".format(version).encode("ascii"), content, count=1)
    os.unlink(fname)
    with open(fname, "wb") as f:
        f.write(content)


def replace_info_file(fname, version, revision):
    with open(fname, "rb") as f:
        content = f.read()
    content = RE_VERSION.sub("__version__ = '{}'".format(version).encode("ascii"), content, count=1)
    def rev(arg):
        return "__revision__ = '{}'".format(revision(), count=1).encode("ascii")
    content = RE_REVISION.sub(rev, content)
    os.unlink(fname)
    with open(fname, "wb") as f:
        f.write(content)

def write_version(fname, version):
    with open(fname, "wb") as f:
        f.write(version.encode("ascii"))


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
            parts.append(major.decode("ascii"))
        if minor or dirty:
            parts.append("{}{}".format(minor if minor else "0", "dev" if dirty else ""))
        return ".".join(parts)
    
    @classmethod
    def tag(cls):
        version = subprocess.check_output("git describe --tags --dirty --always", shell=True).strip()
        parts = version.split(b"-")
        dirty = minor = None 
        if parts[-1] == b"dirty":
            parts = parts[:-1]
            dirty = True  

        major = parts[0].lstrip(b"v")
        if len(parts) > 1:
            minor = parts[1]
    
        return cls.version_from_parts(major=major, minor=minor, dirty=dirty)

    @staticmethod
    def revision():
        revision = subprocess.check_output("git rev-parse --short `git rev-list -1 HEAD -- .`", shell=True).strip()
        return revision.decode("ascii")
    
    @classmethod
    def commits(cls):
        minor = subprocess.check_output("git rev-list HEAD --count .", shell=True).strip()
        dirty = subprocess.call("git diff-index --quiet HEAD .", shell=True) != 0
        return cls.version_from_parts(minor=minor, dirty=dirty)
        
    @classmethod
    def format(cls, version):
        attribs = ('jenkins', 'tag', 'commits')
        attribs = { attrib: LazyFormat(getattr(cls, attrib)) for attrib in attribs}
        return version.decode("ascii").format(**attribs)


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
            for (package, module, source) in self.find_all_modules():
                if source == version_file:
                    parts = package.split(".")
                    parts.append("{}.py".format(module))
                    version_file = os_path.join(*parts)
                    break
                
            version = self.distribution.metadata.version
            fname = os_path.join(self.build_lib, version_file)
            replace_info_file(fname, version, Version.revision)
            if self.last_version_file:
                write_version(self.last_version_file, version)
            print("File {} updated with version {}".format(fname, version))
    
    return build_py


def subclassed_sdist(_sdist):
    class sdist(_sdist):
        def initialize_options(self):
            _sdist.initialize_options(self)
            self.last_version_file = None
            self.set_undefined_options('if_changed', ('last_version_file', 'last_version_file'))

        def make_release_tree(self, base_dir, files):
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
            print("File {} updated with version {}".format(fname, version))
    
    return sdist


class BuildIfChanged(Command):
    """setuptools Command"""
    description = "build only if version changed"
    user_options = [("last-version-file=", None, "Cache file to store last built version")]

    def initialize_options(self):
        self.last_version_file = None
        
    def finalize_options(self):
        pass
        
    def run(self):
        if self.last_version_file is None:
            raise DistutilsOptionError("Parameter 'last_version_file' is required for command 'is_changed'")
        version = self.distribution.metadata.version
        if self.last_version_file and os_path.isfile(self.last_version_file):
            with open(self.last_version_file, "r") as f:
                last_version = f.read().strip()
    
            if last_version == version:
                print("Version {} not changed. Build stopped, remove 'if_changed' to force.".format(last_version))
                sys.exit()
            print("Version changed from {} to {}".format(last_version, version))


def validate_version(dist, attr, value):
    original_version = dist.metadata.version
    if original_version is None:
        return
    if not original_version.endswith(".py"):
        return
    dist.metadata.version_file = original_version
    original_version = get_version(original_version)
    dist.metadata.version = Version.format(original_version)
    
    if "setuptools" in sys.modules:
        from setuptools.command.sdist import sdist as _sdist
    else:
        from distutils.command.sdist import sdist as _sdist
        
    dist.cmdclass["sdist"] = subclassed_sdist(dist.cmdclass.get("sdist", _sdist))
    dist.cmdclass["build_py"] = subclassed_build_py(dist.cmdclass.get("build_py", _build_py))

