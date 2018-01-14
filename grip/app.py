import os
import sys
from virtualenv import create_environment

class App:
    def __init__(self):
        self.interactive = False
        self.virtualenv = None
        self.site_packages = sys.path[-1]
        if 'VIRTUAL_ENV' in os.environ:
            self.set_virtualenv(os.environ['VIRTUAL_ENV'])

    def set_virtualenv(self, path):
        self.virtualenv = path
        self.site_packages = os.path.join(path, 'lib', f'python{sys.version[:3]}', 'site-packages')

    def create_virtualenv(self, path, interpreter):
        create_environment(
            path,
            site_packages=False,
            download=True,
            symlink=True,
        )

    def locate_virtualenv(self, path=None):
        candidates = ['env', 'venv', 'virtualenv']
        if not path:
            path = os.getcwd()

        for candidate in candidates + os.listdir(path):
            subpath = os.path.join(path, candidate)
            if os.path.exists(os.path.join(subpath, 'bin', 'activate')):
                return subpath
