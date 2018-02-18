#!/usr/bin/env python3
from setuptools import setup

setup(
    name='pygrip',
    version='0.1',
    author='Eugene Pankov',
    author_email='e@ajenti.org',
    url='https://eugeny.github.io/grip',
    py_modules=['grip'],
    install_requires=[
        'termcolor>=1.1.0',
        'click>=6.7',
        'virtualenv>=15.1.0',
    ],
    entry_points='''
        [console_scripts]
        grip=grip.main:cli
    ''',
)
