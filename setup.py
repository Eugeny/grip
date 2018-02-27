#!/usr/bin/env python3
from setuptools import setup, find_packages

from setuptools.command.test import test as TestCommand


class Test(TestCommand):
    def run_tests(self):
        from green.cmdline import main
        main(argv=['-r', '-vv'])
        import coverage
        cov = coverage.Coverage()
        cov.load()
        cov.html_report()


setup(
    name='pygrip',
    version='1.0.0a1',
    author='Eugene Pankov',
    author_email='e@ajenti.org',
    description='Better package management for Python',
    long_description=open('README.rst').read(),
    license='MIT',
    url='https://eugeny.github.io/grip',
    packages=find_packages('.'),
    install_requires=[
        'pip>=9.0.1,<9.1.0',
        'virtualenv>=15.1.0',
        'termcolor>=1.1.0',
        'click>=6.7',
    ],
    entry_points='''
        [console_scripts]
        grip=grip.main:cli
    ''',
    cmdclass = {'test': Test},
)
