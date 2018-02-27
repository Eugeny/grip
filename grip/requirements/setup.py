from importlib import util
import os
import setuptools
import sys

from .base import Requirements
# expand_env_variables
from ..model import Dependency


class SetupPyRequirements(Requirements):
    def __init__(self, path):
        self.path = path

    def read(self):
        deps = []
        def fake_setup(install_requires=[], tests_require=[], **kwargs):
            for x in install_requires + tests_require:
                deps.append(Dependency(x))

        setuptools.setup = fake_setup

        sys.path.insert(0, os.path.dirname(self.path))
        spec = util.spec_from_file_location('__setup', self.path)
        mod = util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.path.pop(0)
        return deps

    def __str__(self):
        return '<setup.py>'
