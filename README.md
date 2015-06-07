# module-version
A simple python module to set automatically the version of your modules/packages.


Module version is inspired by [Versioneer](https://github.com/warner/python-versioneer) but have a different set of features and is designed to be easy to use. Note that most of the functionality of this module require that your project is hosted in a git repository.

### Features

- Remove the need for hacks to import the version in the setup script.
- Freedom to keep the `__version__` variable in any of the package files.
- Easy setup.py configuration.
- Support for three version modes:
	- Git Tag mode: Create a version from the last tag plus the number of commits after it.
	- Git version: Use only the number of commits on the module directory.
	- Jenkins version: Take the version from the environment variable `BUILD_NUMBER`.
- Keep track of the relationship between git commit and version in the `__revision__` variable.
- Build only if version changed functionality.

## Installation and configuration

	pip install module_version

### Before module-version

Let's say you want to handle the versioning for a module called `my_module.py` and that you prepared your `setup.py` script.

Normally you host the version at the beginning of the module as follow:

	__version__ = "1.2"
	...

And then you use this version inside the setup script:

```python
from setuptools import setup
from my_module import __version__
	
setup(name='module_version',
   	version = __version__,
   	... 
)
```

Sometime this operation is complicated because it require the execution of the module at build time and it's possible that some of the dependencies are not available in your build chain. For this reason you will find that many distributed packages use to read the module as text and extract the version from it, adding many lines of code for this operation.

### Configure your setup script

`module-version` solve the described problem for you: Just set the version to point to the python file where the version is located; In this example `my_module.py`:

```python
from setuptools import setup
	
setup(
	name='my_module',
   	version = 'my_module.py',
   	... 
)
```

if you execute `python setup.py --version` you will see it will return `1.2` as expected.

In the previous example the version was hardcoded in your script which means, every time you commit something you need to remeber to increase the version. This is an error prone task that can be avoided with one of the methods described in the next chapter.

### Using last git tag as version

If you use to tag your major release with the version number, `module-version` can pick this up automatically for you. What you need to do is replace the hardcoded version in your module as follow:

	__version__ = "{tag}"
	...

If you now commit your changes and set a new tag to **v1.3** you can see `module-version` reconizing this change:

```bash
# python setup.py --version
1.3
```

If your tag is not in the last commit, a minor version is appended to the tag value. This number is equal to the number of commits from the last tag as follow: `tag_version[.commit_count]`. For example you will get `1.3.2` if we have two commits on top of last tagged commit.

If you have uncommitted changes you will get a suffix "dev" following the version number: `1.3.2dev`.

### Using commits count as version

If you host multiple projects on the same repository in different directories or you don't use tags you can use as a version number just the number of changes in the current project directory. To do so you can setup your module as follow:

	__version__ = "{commits}"	# Example: 32

The version create with this method will include only one incremental number, so you may want to add a major version as well in your source code:

	__version__ = "2.{commits}"  # Example 2.32

Notice that also in this case the `dev` suffix is added if your source tree is dirty.

### Using jenkins build number

If you don't host your files in git or you prefer to use as version the build number you can do so as follow:

	__version__ = "2.{jenkins}"
	
If your setup.py is running inside a jenkins job and the build is `43` your final version will be `2.43`.

### Build and release

When is time to build a distribution package, the correct version will be automatically used for the package name and included in the distributed module source code. In case of a source code distribution (sdist) also the setup.py script will be fixed with the correct version.

### Automatic revision

Indipendently of the versioning method you choose, if your code is under git you can have the revision automatically added for you inside the module. All you need to do is add an extra line in your module:

	__version__ = "{commits}"
	__revision__ = ""

and then build your release:

```bash
# python setup.py build
running build
running build_py
copying module_version.py -> build/lib
File build/lib/my_module.py updated with version 2.32.

# grep "^__" build/lib/my_module.py
__version__ = "2.32"
__revision__ = "3ca9bd6"
```

### Conditional build

If your repository host multiple modules a build job may get triggered by your CI every time a change to the repo happens. This will produce the same build artifact every time. To solve this problem, this module include a new setup command `if_changed` that will prevent the execution of the build if the version didn't actually change. 

**Please note** this command is not useful if you decide to adopt the jenkins build number method, since every build will appear as having a different version number.

To use this functionality you first need to add the following section in your `setup.cfg`:

	[if_changed]
	last_version_file = .version

This instruct the module to save the last build number in the specified file (in this case `.version`) every time you perform a build. After this configuration is in place you can try to build adding the command `if_changed` before your build command as in this example:

```bash
$ python setup.py if_changed bdist	# first time build succeed
running if_changed
running bdist
..
Creating tar archive

$ python setup.py if_changed bdist # second time build skipped
running if_changed
Version 0.2.8dev not changed. Build stopped, remove 'if_changed' to force.
```
