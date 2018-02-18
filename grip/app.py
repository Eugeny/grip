import os
import sys
import grip.ui as ui
from pip.commands import InstallCommand
from pip.download import PipSession
from pip.index import PackageFinder
from pip.locations import USER_CACHE_DIR
import pip.utils.logging
import multiprocessing.pool
from pip._vendor.packaging.requirements import Requirement
from pip.req.req_file import parse_requirements
from virtualenv import create_environment

from .model import Dependency, Package, PackageGraph




class App:
    def __init__(self):
        self.interactive = False
        self.virtualenv = None
        self.requirements = None
        self.site_packages = sys.path[-1]
        if 'VIRTUAL_ENV' in os.environ:
            self.set_virtualenv(os.environ['VIRTUAL_ENV'])

        self.session = PipSession(cache=os.path.join(USER_CACHE_DIR, 'http'))
        self.index_url = 'https://pypi.org/simple/'

        self.finder = PackageFinder(
            [],
            [self.index_url],
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

    def locate_requirements(self, path=None):
        candidates = ['requirements.txt', 'REQUIREMENTS']
        if not path:
            path = os.getcwd()

        for candidate in candidates:
            subpath = os.path.join(path, candidate)
            if os.path.exists(subpath):
                return subpath

    def set_requirements(self, path):
        self.requirements = path

    def load_dependency_graph(self):
        graph = PackageGraph.from_directory(self.site_packages)

        if self.requirements:
            graph.set_requirements(Dependency(x, graph.requirements) for x in parse_requirements(self.requirements, session=self.session))

        graph.resolve_dependencies()
        return graph

    def perform_check(self, silent=False):
        pkgs = self.load_dependency_graph()
        problem_counter = 0

        for pkg in pkgs:
            if pkg.name in PackageGraph.SYSTEM_PKGS:
                continue

            if len(pkg.incoming_mismatched) > 0:
                if not silent:
                    print(' -', self._pkg_str(pkg), '(installed)')
                    for index, dep in enumerate(pkg.incoming + pkg.incoming_mismatched):
                        print('  ', '├──' if (index < len(pkg.incoming + pkg.incoming_mismatched) - 1) else '└──', end='')
                        print(
                            ui.bold(ui.green('[ok]') if dep in pkg.incoming else ui.yellow('[mismatch]')),
                            self._req_str(dep, name=False),
                            'required by',
                            self._pkg_str(dep.parent, version=False)
                        )
                    print()
                problem_counter += 1

            if len(pkg.incoming + pkg.incoming_mismatched) == 0:
                if not silent:
                    print(' -', self._pkg_str(pkg), '(installed)')
                    print('   └──', ui.bold(ui.red('extraneous')))
                    print()
                problem_counter += 1

        if problem_counter:
            ui.warn(problem_counter, 'dependency problems found')
            if silent:
                ui.warn('Run', ui.bold('grip check'), 'for more information')
        elif not silent:
            ui.info('No problems found')

    def perform_prune(self):
        pkgs = self.load_dependency_graph()

        for pkg in pkgs:
            if pkg.name in PackageGraph.SYSTEM_PKGS:
                continue

            if len(pkg.incoming + pkg.incoming_mismatched) == 0:
                ui.info('Removing', self._pkg_str(pkg))
                self._uninstall_single_pkg(pkg)

    def perform_freeze(self):
        pkgs = self.load_dependency_graph()
        for pkg in pkgs:
            print(ui.bold(pkg.name) + ui.cyan('==' + str(pkg.version)))

    def perform_install_requirements(self):
        pkgs = self.load_dependency_graph()
        self.perform_install(pkgs.requirements.deps)

    def perform_install(self, deps):
        install_queue = deps[:]
        graph = self.load_dependency_graph()
        while len(install_queue):
            dep = install_queue.pop(0)
            install_spec = self._get_single_dep_install_spec(dep, graph=graph, downgrade=(dep in deps))
            if install_spec:
                command = InstallCommand()
                command.main(['--no-deps', '--index-url', self.index_url, '--target', self.site_packages, '--ignore-installed', '--upgrade', install_spec])
            else:
                continue

            pkgs = self.load_dependency_graph()
            pkg = pkgs.match(dep)
            if pkg:
                for sub_dep in pkg.deps:
                    if not sub_dep.resolved_to:
                        install_queue.append(sub_dep)

    def _get_single_dep_install_spec(self, dep, graph=None, downgrade=False):
        if not graph:
            graph = self.load_dependency_graph()

        installed_pkg = graph.find(dep.name)
        if installed_pkg and dep.matches_version(installed_pkg.version):
            ui.info(self._req_str(dep), 'is already installed as', self._pkg_str(installed_pkg))
            return

        if dep.url:
            install_spec = dep.to_pip_spec()
            install_version = None
        else:
            candidates = self._candidates_for(dep)
            best_candidate = self._best_candidate_of(dep, candidates)
            if not best_candidate:
                ui.error('No packages available for', self._req_str(dep))
                latest = self._best_candidate_of(None, candidates)
                if latest:
                    ui.error('latest:', latest.version)
                ui.error(f'all: https://pypi.org/project/{dep.name}/#history')
                sys.exit(1)

            install_spec = f'{dep.name}=={str(best_candidate.version)}'
            install_version = best_candidate.version

        if not dep.url and installed_pkg and not dep.matches_version(installed_pkg.version):
            ui.warn('Dependency mismatch')
            print(' -', self._pkg_str(installed_pkg), '(installed)')
            if len(installed_pkg.incoming):
                print('   └ required by', self._pkg_str(installed_pkg.incoming[0].parent, version=False))
            print(' -', self._req_str(dep), '(requested)')
            print('   └ required by', self._pkg_str(dep.parent, version=False))
            if installed_pkg.version < best_candidate.version:
                ui.warn('Will upgrade')
            elif not downgrade:
                ui.warn('Will not downgrade')
                return
            else:
                ui.warn('Will downgrade')

        if installed_pkg:
            ui.info('Removing', self._pkg_str(installed_pkg))
            self._uninstall_single_pkg(installed_pkg)

        ui.info('Installing', self._pkg_str(Package(dep.name, install_version)))
        if dep.url:
            ui.info('Using URL:', ui.bold(dep.url))

        return install_spec

    def perform_uninstall(self, packages):
        pkgs = self.load_dependency_graph()
        for name in packages:
            pkg = pkgs.find(name)
            if pkg:
                ui.info('Removing', self._pkg_str(pkg))
                self._uninstall_single_pkg(pkg)
            else:
                ui.error(ui.bold(name), 'is not installed')

    def _uninstall_single_pkg(self, pkg):
        entries = pkg.metadata.get_metadata('RECORD').splitlines()
        for line in entries:
            path = line.split(',')[0]
            path = os.path.join(self.site_packages, path)
            if os.path.exists(path):
                os.unlink(path)
                if len(os.listdir(os.path.split(path)[0])) == 0:
                    os.rmdir(os.path.split(path)[0])

    def _req_str(self, req, name=True, version=True):
        if req.url:
            return ui.bold(req.url)
        return (ui.bold(req.name) if name else '') + (ui.cyan(str(req.specifier) or '(any)') if version else '')

    def _pkg_str(self, pkg, name=True, version=True):
        if not pkg:
            return ui.red('none')
        if pkg.name == PackageGraph.PROJECT_PKG:
            return ui.cyan(ui.bold(pkg.name))
        if pkg.name == PackageGraph.USER_PKG:
            return ui.green(ui.bold(pkg.name))
        return (ui.bold(pkg.name) if name else '') + (ui.cyan('@' + str(pkg.version)) if version else '')

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

    def _candidates_for(self, dep):
        return self.finder.find_all_candidates(dep.name)

    def _best_candidate_of(self, dep, candidates):
        if dep:
            compatible_versions = set(
                dep.req.specifier.filter(
                    [str(c.version) for c in candidates],
                    prereleases=False
                )
            )

            if len(compatible_versions) == 0:
                compatible_versions = set(
                    dep.req.specifier.filter(
                        [str(c.version) for c in candidates],
                        prereleases=True
                    )
                )

            applicable_candidates = [
                c for c in candidates if str(c.version) in compatible_versions
            ]
        else:
            applicable_candidates = candidates

        if not len(applicable_candidates):
            return None

        return max(applicable_candidates, key=self.finder._candidate_sort_key)

    def perform_outdated(self):
        pkgs = self.load_dependency_graph()
        if self.requirements:
            deps = pkgs.requirements.deps
        else:
            deps = [Dependency(Requirement(x.name)) for x in pkgs]

        def process_single(dep):
            # TODO
            pip.utils.logging._log_state.indentation = 0

            installed = pkgs.find(dep.name)

            if not installed:
                return

            candidates = self._candidates_for(dep)

            best_candidate = self._best_candidate_of(dep, candidates)
            best_release = self._best_candidate_of(None, candidates)

            if best_release and (not installed or best_release.version > installed.version):
                return (
                    installed,
                    best_candidate.version if best_candidate else None,
                    best_release.version if best_release else None,
                )

        import click
        with multiprocessing.pool.ThreadPool(processes=16) as pool:
            with click.progressbar(pool.imap_unordered(process_single, deps), length=len(deps), label='Checking latest versions') as bar:
                results = [x for x in bar if x]

        rows = []
        for installed, best_candidate, best_release in sorted(results, key=lambda x: x[0]):
            rows.append((
                self._pkg_str(installed),
                ui.cyan(best_candidate) if best_candidate and best_candidate > installed.version else ui.darkwhite(best_candidate),
                ui.green(best_release) if best_release and best_release > installed.version else ui.darkwhite(best_release),
            ))

        if len(rows):
            ui.table(['Installed', 'Available', 'Latest'], rows)

        ui.info(ui.bold(str(len(results))), 'outdated packages')
