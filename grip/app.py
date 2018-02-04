import pkg_resources
import os
import sys
import grip.ui as ui
from pip.commands import InstallCommand, UninstallCommand
from pip.download import PipSession
from pip.index import PackageFinder
from pip.locations import USER_CACHE_DIR
import pip.utils.logging
import multiprocessing.pool
from pip._vendor.packaging.version import Version
from pip._vendor.packaging.requirements import Requirement
from pip.req.req_file import parse_requirements

from virtualenv import create_environment


def sanitize_name(name):
    return pkg_resources.safe_name(name).lower()


class PackageDep:
    def __init__(self, req):
        self.req = req
        self.resolved_to = None

    @property
    def name(self):
        return sanitize_name(self.req.name)

    def matches_version(self, version):
        return len(list(self.req.specifier.filter([str(version)]))) > 0

    def __str__(self):
        return str(self.req)


class Package:
    def __init__(self, name, version, metadata=None):
        self.name = name
        self.metadata = metadata
        if type(version) == str:
            self.version = Version(version)
        else:
            self.version = version
        self.deps = []

    def __str__(self):
        return f'{self.name}@{self.version}'

    def __gt__(self, other):
        return self.name > other.name

    def prnt(self):
        print(self)
        for dep in self.deps:
            print(' ', dep, end=' ')
            if dep.resolved_to:
                print('->', dep.resolved_to)
            else:
                print()
        print()


class PackageGraph(list):
    def find(self, name):
        name = sanitize_name(name)
        for pkg in self:
            if sanitize_name(pkg.name) == name:
                return pkg

    def match(self, req):
        dep = PackageDep(req)
        for pkg in self:
            if pkg.name == dep.name and dep.matches_version(pkg.version):
                return pkg


class App:
    def __init__(self):
        self.interactive = False
        self.virtualenv = None
        self.site_packages = sys.path[-1]
        if 'VIRTUAL_ENV' in os.environ:
            self.set_virtualenv(os.environ['VIRTUAL_ENV'])

        self.session = PipSession(cache=os.path.join(USER_CACHE_DIR, 'http'))
        self.finder = PackageFinder(
            [],
            ['https://pypi.org/simple/'],
            session=self.session
        )

    def set_virtualenv(self, path):
        self.virtualenv = path
        self.site_packages = os.path.join(
            path, 'lib', f'python{sys.version[:3]}', 'site-packages'
        )

    def create_virtualenv(self, path, interpreter):
        ui.info('Setting up a virtualenv in', ui.bold(path))
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
                    pkg = Package(sanitize_name(dist.project_name), dist.version, metadata=dist)
                    pkg.deps = sorted((PackageDep(x) for x in dist.requires()), key=lambda x: str(x))
                    pkgs.append(pkg)

        # resolve deps
        for pkg in pkgs:
            for dep in pkg.deps:
                dep.resolved_to = None
                for candidate in pkgs:
                    if candidate.name == dep.name:
                        if dep.matches_version(candidate.version):
                            dep.resolved_to = candidate
                            break

        return PackageGraph(sorted(pkgs, key=lambda x: x.name))

    def perform_install(self, spec):
        install_queue = [Requirement(spec)]
        pkgs = self.load_dependency_graph()
        while len(install_queue):
            req = install_queue.pop(0)
            pkg = pkgs.find(req.name)
            if pkg:
                if PackageDep(req).matches_version(pkg.version):
                    ui.info(self._req_str(req), 'is already installed as', self._pkg_str(pkg))
                    continue
                else:
                    ui.info('Removing', self._pkg_str(pkg))
                    self._uninstall_single_pkg(pkg)
            ui.info('Installing', self._req_str(req))
            command = InstallCommand()
            command.main(['--no-deps', '--target', self.site_packages, '--ignore-installed', '--upgrade', str(req)])
            pkgs = self.load_dependency_graph()
            pkg = pkgs.match(req)
            for dep in pkg.deps:
                if not dep.resolved_to:
                    install_queue.append(dep.req)

    def _uninstall_single_pkg(self, pkg):
        entries = pkg.metadata.get_metadata('RECORD').splitlines()
        for line in entries:
            path = line.split(',')[0]
            path = os.path.join(self.site_packages, path)
            if os.path.exists(path):
                os.unlink(path)
                if len(os.listdir(os.path.split(path)[0])) == 0:
                    os.rmdir(os.path.split(path)[0])

    def _req_str(self, req):
        return ui.bold(req.name) + ui.cyan(str(req.specifier) or '(any)')

    def _pkg_str(self, pkg):
        return ui.bold(pkg.name) + ui.cyan('@' + str(pkg.version))

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

    def perform_outdated(self):
        pkgs = self.load_dependency_graph()
        reqs = list(parse_requirements('requirements.txt', session=self.session))

        def process_single(req):
            # TODO
            pip.utils.logging._log_state.indentation = 0

            installed = pkgs.find(req.name)

            if not installed:
                return

            all_candidates = self.finder.find_all_candidates(req.name)
            compatible_versions = set(
                req.req.specifier.filter(
                    [str(c.version) for c in all_candidates],
                    prereleases=False
                )
            )

            applicable_candidates = [
                c for c in all_candidates if str(c.version) in compatible_versions
            ]

            best_candidate = None
            best_release = None
            if applicable_candidates:
                best_candidate = max(applicable_candidates, key=self.finder._candidate_sort_key)
            if all_candidates:
                best_release = max(all_candidates, key=self.finder._candidate_sort_key)

            if best_release and (not installed or best_release.version > installed.version):
                return (
                    installed,
                    best_candidate.version if best_candidate else None,
                    best_release.version if best_release else None,
                )

        import click
        with multiprocessing.pool.ThreadPool(processes=16) as pool:
            with click.progressbar(pool.imap_unordered(process_single, reqs), length=len(reqs), label='Checking latest versions') as bar:
                results = [x for x in bar if x]

        rows = []
        for installed, best_candidate, best_release in sorted(results, key=lambda x: x[0]):
            rows.append((
                self._pkg_str(installed),
                ui.cyan(best_candidate) if best_candidate and best_candidate > installed.version else ui.darkwhite(best_candidate),
                ui.green(best_release) if best_release and best_release > installed.version else ui.darkwhite(best_release),
            ))

        ui.table(['Installed', 'Available', 'Latest'], rows)
        ui.info(ui.bold(str(len(results))), 'outdated packages')
