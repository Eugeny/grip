import os
import sys
from pip.commands import InstallCommand
import pip.utils.logging
import multiprocessing.pool
from pip._vendor.packaging.requirements import Requirement
from virtualenv import create_environment
import grip.ui as ui

from .model import Dependency, PackageGraph, Package
from .requirements import RequirementsTxt
from .planner import Planner, RemoveAction, InstallAction, FailAction
from .index import Index


class App:
    def __init__(self):
        self.interactive = False
        self.virtualenv = None
        self.requirements = None
        self.site_packages = sys.path[-1]
        if 'VIRTUAL_ENV' in os.environ:
            self.set_virtualenv(os.environ['VIRTUAL_ENV'])

        self.index_url = 'https://pypi.org/simple/'
        self.index = Index(self.index_url)

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
                return RequirementsTxt(subpath)

    def set_requirements(self, requirements):
        self.requirements = requirements

    def load_dependency_graph(self):
        graph = PackageGraph.from_directory(self.site_packages)

        if self.requirements:
            graph.set_requirements(self.requirements.read())

        graph.resolve_dependencies()
        return graph

    def run_actions(self, actions):
        for action in actions:
            if isinstance(action, InstallAction):
                ui.info('Installing', ui.pkg(Package(action.dependency.name, action.version)))
                command = InstallCommand()
                command.main(['--no-deps', '--index-url', self.index_url, '--target', self.site_packages, '--ignore-installed', '--upgrade', action.spec])
            if isinstance(action, FailAction):
                sys.exit(1)
            if isinstance(action, RemoveAction):
                ui.info('Removing', ui.pkg(action.package))
                entries = action.package.metadata.get_metadata('RECORD').splitlines()
                for line in entries:
                    path = line.split(',')[0]
                    path = os.path.join(self.site_packages, path)
                    if os.path.exists(path):
                        os.unlink(path)
                        if len(os.listdir(os.path.split(path)[0])) == 0:
                            os.rmdir(os.path.split(path)[0])

    def perform_check(self, silent=False):
        pkgs = self.load_dependency_graph()
        problem_counter = 0

        for pkg in pkgs:
            if pkg.name in PackageGraph.SYSTEM_PKGS:
                continue

            if len(pkg.incoming_mismatched) > 0:
                if not silent:
                    print(' -', ui.pkg(pkg), '(installed)')
                    for index, dep in enumerate(pkg.incoming + pkg.incoming_mismatched):
                        print('  ', '├──' if (index < len(pkg.incoming + pkg.incoming_mismatched) - 1) else '└──', end='')
                        print(
                            ui.bold(ui.green('[ok]') if dep in pkg.incoming else ui.yellow('[mismatch]')),
                            ui.dep(dep, name=False),
                            'required by',
                            ui.pkg(dep.parent, version=False)
                        )
                    print()
                problem_counter += 1

            if len(pkg.incoming + pkg.incoming_mismatched) == 0:
                if not silent:
                    print(' -', ui.pkg(pkg), '(installed)')
                    print('   └──', ui.bold(ui.red('extraneous')))
                    print()
                problem_counter += 1

        if problem_counter:
            ui.warn(problem_counter, 'dependency problems found')
            if silent:
                ui.warn('Run', ui.bold('grip check'), 'for more information')
        elif not silent:
            ui.info('No problems found')

    def perform_freeze(self):
        pkgs = self.load_dependency_graph()
        for pkg in pkgs:
            print(ui.bold(pkg.name) + ui.cyan('==' + str(pkg.version)))

    def perform_install_requirements(self):
        graph = self.load_dependency_graph()
        self.perform_install(graph.requirements.deps)

    def perform_install(self, deps, save=False):
        direct_deps = deps
        install_queue = deps[:]
        graph = self.load_dependency_graph()
        while len(install_queue):
            dep = install_queue.pop(0)

            actions = list(Planner(graph, self.index).install(dep, downgrade=(dep in direct_deps)))
            self.run_actions(actions)

            if save and dep in direct_deps:
                self.requirements.add(dep)

            graph = self.load_dependency_graph()
            pkg = graph.match(dep)
            if pkg:
                for sub_dep in pkg.deps:
                    if not sub_dep.resolved_to:
                        install_queue.append(sub_dep)

    def perform_prune(self):
        graph = self.load_dependency_graph()
        self.run_actions(Planner(graph).prune())

    def perform_uninstall(self, packages):
        graph = self.load_dependency_graph()
        self.run_actions(Planner(graph).remove(packages))

    def perform_list(self):
        pkgs = self.load_dependency_graph()
        ui.info(ui.bold(str(len(pkgs))), 'packages installed')
        for pkg in pkgs:
            print(' -', ui.pkg(pkg))
            for index, dep in enumerate(pkg.deps):
                print('  ', '├──' if (index < len(pkg.deps) - 1) else '└──', end='')
                print(dep.name + ui.cyan(str(dep.req.specifier)), end=' ')
                if dep.resolved_to:
                    print(ui.green('→'), ui.pkg(dep.resolved_to))
                else:
                    print(ui.red('→ none'))

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

            candidates = self.index.candidates_for(dep)

            best_candidate = self.index.best_candidate_of(dep, candidates)
            best_release = self.index.best_candidate_of(None, candidates)

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
                ui.pkg(installed),
                ui.cyan(best_candidate) if best_candidate and best_candidate > installed.version else ui.darkwhite(best_candidate),
                ui.green(best_release) if best_release and best_release > installed.version else ui.darkwhite(best_release),
            ))

        if len(rows):
            ui.table(['Installed', 'Available', 'Latest'], rows)

        ui.info(ui.bold(str(len(results))), 'outdated packages')
