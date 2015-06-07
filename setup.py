from setuptools import setup

setup(name='module_version',
    version='module_version.py',
    author='Giuseppe Tribulato',
    author_email='gtsystem@gmail.com',
    url='https://github.com/gtsystem/module_version',
    description='A python module for set automatic versions in built modules',
    py_modules=['module_version'],
    entry_points = {
        'distutils.setup_keywords': 'version = module_version:validate_version',
        'distutils.commands': [
            'if_changed = module_version:BuildIfChanged'
        ]
    }
)
