import pkg_resources
import os
import sys
import grip.ui as ui
from pip.commands import InstallCommand

from virtualenv import create_environment


def sanitize_name(name):
    return pkg_resources.safe_name(name).lower()


class PackageDep:
    def __init__(self, req):
        self.req = req
        self.name = sanitize_name(req.name)
        self.resolved_to = None

    def __str__(self):
        return str(self.req)


class Package:
    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.deps = []

    def __str__(self):
        return f'{self.name}@{self.version}'

    def prnt(self):
        print(self)
        for dep in self.deps:
            print(' ', dep, end=' ')
            if dep.resolved_to:
                print('->', dep.resolved_to)
            else:
                print()
        print()




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

    def load_dependency_graph(self):
        pkgs = []
        for dir in os.listdir(self.site_packages):
            if dir.endswith('.dist-info'):
                dist_info = os.path.join(self.site_packages, dir)
                dists = pkg_resources.distributions_from_metadata(dist_info)
                for dist in dists:
                    pkg = Package(sanitize_name(dist.project_name), dist.version)
                    pkg.deps = sorted((PackageDep(x) for x in dist.requires()), key=lambda x: str(x))
                    pkgs.append(pkg)

        # resolve deps
        for pkg in pkgs:
            for dep in pkg.deps:
                dep.resolved_to = None
                for candidate in pkgs:
                    if candidate.name == dep.name:
                        if list(dep.req.specifier.filter([candidate.version])):
                            dep.resolved_to = candidate
                            break

        return sorted(pkgs, key=lambda x: x.name)

    def perform_install(self, spec):
        command = InstallCommand()
        command.main(['--no-deps', '--target', self.site_packages, '--ignore-installed', '--upgrade', spec])

    def _pkg_str(self, pkg):
        return ui.bold(pkg.name) + ui.cyan('@' + pkg.version)


    def perform_list(self):
        pkgs = self.load_dependency_graph()
        ui.info(ui.bold(str(len(pkgs))), 'packages installed')
        for pkg in pkgs:
            print(' -', self._pkg_str(pkg))
            for index, dep in enumerate(pkg.deps):
                print('  ', '├──' if (index < len(pkg.deps) - 1) else '└──', end='')
                print(dep.name + ui.cyan(str(dep.req.specifier)), end=' ')
                if dep.resolved_to:
                    print(ui.green('→'), self._pkg_str(dep.resolved_to))
                else:
                    print(ui.red('→ none'))
