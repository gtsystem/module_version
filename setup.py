from setuptools import setup
from module_version import get_version

setup(name='module_version',
    version=get_version("module_version.py"),
    description='A python module for set automatic versions in built modules',
    py_modules=['module_version'],
    entry_points = {
        'distutils.setup_keywords': 'version = module_version:validate_version',
        'distutils.commands': [
            'versioned = module_version:Versioned',
            'if_changed = module_version:BuildIfChanged',
        ]
    }
)
