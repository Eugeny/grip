setup_py = '''#!/usr/bin/env python
from setuptools import setup, find_packages

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='{name}',
    version='{version}',
    description='{description}',
    long_description=long_description,
    url='{url}',

    author='{author}',
    author_email='{author_email}',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[],

    entry_points={{
        'console_scripts': [
            '{package}={package}:main',
        ],
    }}
)
'''

setup_cfg = '''[bdist_wheel]
universal=1
'''

gitignore = '''
build/
dist/
*.egg-info/
*.egg
*.py[cod]
__pycache__/
*.so
*~
'''

package_init = '''def main():
    print('Hello world')
'''
