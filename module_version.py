__version__ = '{tag}'
__revision__ = ''

import os
import sys
import os.path as os_path
import re
import subprocess
from distutils.core import Command
from distutils.command.build_py import build_py as _build_py

RE_VERSION = re.compile(br'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', re.M)
RE_REVISION = re.compile(br'^__revision__\s*=\s*[\'"]([^\'"]*)[\'"]', re.M)


def get_version(fname):
    with open(fname, "rb") as f:
        content = f.read()
    g = RE_VERSION.search(content)
    if g is None:
        raise Exception("No version found in {}".format(fname))
    return g.group(1)
    

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
        """setuptools Command"""
        def run(self):
            _build_py.run(self)
            version_file = getattr(self.distribution.metadata, "version_file", None)
            if version_file is None:
                return
            version = self.distribution.metadata.version
            fname = os_path.join(self.build_lib, version_file)
            replace_info_file(fname, version, Version.revision)
            print "File {} updated with version {}".format(fname, version)
    
    return build_py


def subclassed_sdist(_sdist):
    class sdist(_sdist):
        def make_release_tree(self, base_dir, files):
            print files
            version_file = getattr(self.distribution.metadata, "version_file", None)
            _sdist.make_release_tree(self, base_dir, files)
            if version_file is None:
                return

            fname = os_path.join(base_dir, version_file)
            version = self.distribution.metadata.version
            replace_info_file(fname, version, Version.revision)
            print "File {} updated with version {}".format(fname, version)
    
    return sdist

class BuildIfChanged(Command):
    """setuptools Command"""
    description = "build only if version changed"
    user_options = []

    def initialize_options(self):
        self.build_lib = None
        self.set_undefined_options('build', ('build_lib', 'build_lib'))
        
    def finalize_options(self):
        pass

    def run(self):
        version_file = getattr(self.distribution.metadata, "version_file", None)
        if version_file is None:
            return
        version = self.distribution.metadata.version
        fname = os_path.join(self.build_lib, version_file)
        last_version = get_version(fname)
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

