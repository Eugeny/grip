#!/usr/bin/env python3
from setuptools import setup

setup(
    name='python-grip',
    version='0.1',
    py_modules=['grip'],
    install_requires=[
        'click',
    ],
    entry_points='''
        [console_scripts]
        grip=grip.main:cli
    ''',
)
