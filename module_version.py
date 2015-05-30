__version__ = "{tag}"
__revision__ = ""

import os
import sys
import os.path as os_path
import re
import subprocess
import setuptools
from distutils.command.build import build

RE_VERSION = re.compile(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', re.M)
RE_REVISION = re.compile(r'^__revision__\s*=\s*[\'"]([^\'"]*)[\'"]', re.M)


def get_version(fname):
    with open(fname, "r") as f:
        content = f.read()
    g = RE_VERSION.search(content)
    if g is None:
        raise Exception("No version found in {}".format(fname))
    return g.group(1)
    

def replace_info_file(fname, version, revision):
    with open(fname, "r") as f:
        content = f.read()
    content = RE_VERSION.sub("__version__ = '{}'".format(version), content, count=1)
    def rev(arg):
        return "__revision__ = '{}'".format(revision(), count=1)
    content = RE_REVISION.sub(rev, content)
    with open(fname, "w") as f:
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
    def tag():
        version = subprocess.check_output("git describe --tags --dirty --always", shell=True).strip()
        parts = version.split("-")
        if parts[-1] == "dirty":
            parts = parts[:-1]
            dirty = True  
        else:
            dirty = False      
        major = parts[0].lstrip("v")
        if len(parts) > 1:
            minor = parts[1]
        else:
            minor = "0"
        return "{}.{}{}".format(major, minor, "dev" if dirty else "")
    
    @staticmethod
    def revision():
        revision = subprocess.check_output("git rev-parse --short `git rev-list -1 HEAD -- .`", shell=True).strip()
        return revision
    
    @staticmethod
    def commits():
        minor = subprocess.check_output("git rev-list HEAD --count .", shell=True).strip()
        dirty = subprocess.call("git diff-index --quiet HEAD .", shell=True) != 0
        return "{}{}".format(minor, "dev" if dirty else "")
        
    @classmethod
    def format(cls, version):
        attribs = ('jenkins', 'tag', 'commits')
        attribs = { attrib: LazyFormat(getattr(cls, attrib)) for attrib in attribs}
        return version.format(**attribs)


class Versioned(setuptools.Command):
    """setuptools Command"""
    description = "Update file version in the build folder"
    user_options = [
        ('version-file=', None, "file where the version is stored"),
    ]

    def initialize_options(self):
        self.version_file = None
        self.build_lib = None
        self.set_undefined_options('build', ('build_lib', 'build_lib'))
        
    def finalize_options(self):
        pass

    def run(self):
        if self.version_file is None:
            return
        version = self.distribution.metadata.version
        fname = os_path.join(self.build_lib, self.version_file)
        replace_info_file(fname, version, Version.revision)
        print "File {} updated with version {}".format(fname, version)


class BuildIfChanged(setuptools.Command):
    """setuptools Command"""
    description = "build only if version changed"
    user_options = []

    def initialize_options(self):
        self.version_file = None
        self.build_lib = None
        self.set_undefined_options('versioned', ('version_file', 'version_file'))
        self.set_undefined_options('build', ('build_lib', 'build_lib'))
        
    def finalize_options(self):
        pass

    def run(self):
        if self.version_file is None:
            return
        version = self.distribution.metadata.version
        fname = os_path.join(self.build_lib, self.version_file)
        last_version = get_version(fname)
        if last_version == version:
            print "Version {} not changed. Build stopped, remove 'if_changed' to force.".format(last_version)
            sys.exit()
        print "Version changed from {} to {}".format(last_version, version)


def validate_version(dist, attr, value):
    old_version = dist.metadata.version
    dist.metadata.version = Version.format(dist.metadata.version)
    sub_command = ("versioned", None)
    if sub_command not in build.sub_commands:
        build.sub_commands.append(sub_command)

