from contextlib import contextmanager
import logging
import multiprocessing.pool
import os
import sys
import subprocess
from urllib.parse import urlparse
from urllib.request import urlretrieve

import pip.utils.logging
from pip.commands import InstallCommand
from pip._vendor.packaging.requirements import Requirement
from virtualenv import create_environment

import grip.ui as ui
import grip.templates as templates

from .model import Dependency, PackageGraph
from .requirements import TxtRequirements, SetupPyRequirements
from .planner import Planner, RemoveAction, InstallAction, FailAction, SaveAction
from .index import Index



@contextmanager
def pip_progress():
    with ui.log_line() as log:
        def emit(self, record):
            log(record.getMessage())

        logging.StreamHandler.emit = emit
        yield


class App:
    def __init__(self):
        self.interactive = False
        self.virtualenv = None
        self.requirements = None
        self.cached_requirements = None
        self.site_packages = sys.path[-1]
        if 'VIRTUAL_ENV' in os.environ:
            self.set_virtualenv(os.environ['VIRTUAL_ENV'])

        self.index_url = 'https://pypi.org/simple/'
        self.index = Index(self.index_url)

    def ensure_virtualenv(self):
        virtualenv = self.locate_virtualenv()
        if virtualenv:
            self.set_virtualenv(virtualenv)
        else:
            ui.warn('Could not find a local virtualenv.')
            if self.interactive and ui.yn('Create one?'):
                def validate_interpreter(name):
                    try:
                        subprocess.check_call([name, '-V'])
                    except:
                        raise Exception('Could not find %s' % name)

                name = ui.prompt('Folder name', default='venv')
                interpreter = ui.prompt('Interpreter', default='python3', validate=validate_interpreter)
                path = os.path.join(os.getcwd(), name)
                self.create_virtualenv(path, interpreter)
                self.set_virtualenv(path)
            else:
                ui.error('Aborting.')
                sys.exit(1)

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
        candidates = ['requirements.txt', 'REQUIREMENTS', 'requirements', 'requirements/default.txt']
        if not path:
            path = os.getcwd()

        for candidate in candidates:
            subpath = os.path.join(path, candidate)
            if os.path.isfile(subpath):
                return TxtRequirements(subpath)

        setuppy = os.path.join(path, 'setup.py')
        if os.path.isfile(setuppy):
            return SetupPyRequirements(setuppy)

    def set_requirements(self, requirements):
        self.requirements = requirements

    def load_dependency_graph(self):
        graph = PackageGraph.from_directory(self.site_packages)

        if self.requirements:
            if not self.cached_requirements:
                self.cached_requirements = self.requirements.read()
            graph.set_requirements(self.cached_requirements)

        graph.resolve_dependencies()
        return graph

    def run_actions(self, actions):
        for action in actions:
            if isinstance(action, InstallAction):
                ui.info('Installing', ui.dep(action.dependency))
                command = InstallCommand()
                with pip_progress():
                    command.main([
                        '--no-deps',
                        '--index-url', self.index_url,
                        '--prefix', self.virtualenv,
                        '--ignore-installed',
                        '--upgrade',
                        str(action.dependency)
                    ])
            if isinstance(action, SaveAction):
                self.requirements.add(action.spec)
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

    def perform_init(self):
        default_url = 'http://example.com'
        try:
            default_url = subprocess.check_output(['git', 'config', 'remote.origin.url']).decode().strip()
            if 'git@' in default_url:
                default_url = default_url.replace(':', '/')
                default_url = default_url.replace('git@', 'https://')
            if default_url.endswith('.git'):
                default_url = default_url[:-4]
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pass

        default_author = 'ACME Inc.'
        default_email = 'info@acme.inc'
        try:
            default_author = subprocess.check_output(['git', 'config', 'user.name']).decode().strip()
            default_email = subprocess.check_output(['git', 'config', 'user.email']).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pass

        vars = {}
        for key, prompt, default in (
            ('name', 'PyPI project name', os.path.basename(os.getcwd())),
            ('version', 'Version', '1.0.0'),
            ('description', 'Short description', 'FooBar Enhanced Edition'),
            ('url', 'Project URL', default_url),
            ('author', 'Author', default_author),
            ('author_email', 'E-mail', default_email),
            ('package', 'Root Python package name', os.path.basename(os.getcwd()).replace('-', '_')),
        ):
            vars[key] = ui.prompt(prompt, default=default)

        if not os.path.exists(vars['package']):
            os.mkdir(vars['package'])

        for name, template in (
            ('setup.py', templates.setup_py),
            ('setup.cfg', templates.setup_cfg),
            ('.gitignore', templates.gitignore),
            ('requirements.txt', ''),
            (os.path.join(vars['package'], '__init__.py'), templates.package_init),
        ):
            if os.path.exists(name):
                ui.warn(ui.bold(name), 'already exists')
            else:
                ui.info('writing', ui.bold(name))
                with open(name, 'w') as f:
                    f.write(template.format(**vars))

    def perform_run(self, binary, args):
        if not self.virtualenv:
            ui.error('No virtualenv available')
            sys.exit(1)
        path = os.path.join(self.virtualenv, 'bin', binary)
        if not os.path.exists(path):
            ui.error(path, 'does not exist')
            sys.exit(1)
        os.execvp(path, [binary] + list(args))

    def perform_check(self, silent=False):
        pkgs = self.load_dependency_graph()
        problem_counter = 0
        extraneous_counter = 0

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
                extraneous_counter += 1
                if not silent:
                    print(' -', ui.pkg(pkg), '(installed)')
                    print('   └──', ui.bold(ui.yellow('extraneous')))
                    print()

        if problem_counter:
            ui.warn(problem_counter, 'dependency problems found')
            if silent:
                ui.warn('Run', ui.bold('grip check'), 'for more information')
        elif not silent and not extraneous_counter:
            ui.info('No problems found')

    def perform_freeze(self):
        pkgs = self.load_dependency_graph()
        for pkg in pkgs:
            print(ui.bold(pkg.name) + ui.cyan('==' + str(pkg.version)))

    def perform_install_requirements(self):
        graph = self.load_dependency_graph()
        self.perform_install(graph.requirements.deps)

    def perform_install(self, deps, upgrade=False, save=False):
        direct_deps = deps
        install_queue = deps[:]
        graph = self.load_dependency_graph()
        while len(install_queue):
            dep = install_queue.pop(0)

            actions = list(Planner(graph, self.index).install(dep, upgrade=upgrade, downgrade=(dep in direct_deps), save=save))
            self.run_actions(actions)

            graph = self.load_dependency_graph()
            pkg = graph.match(dep)
            if pkg:
                for sub_dep in pkg.deps:
                    if not sub_dep.resolved_to:
                        install_queue.append(sub_dep)

    def perform_download(self, deps, source=False):
        for dep in deps:
            candidates = self.index.candidates_for(dep, source=source)
            best_candidate = self.index.best_candidate_of(dep, candidates)
            if not best_candidate:
                ui.error('No packages available for', ui.dep(dep))
                sys.exit(1)

            url = best_candidate.location.url
            name = os.path.basename(urlparse(url).path)
            ui.info('Downloading', ui.bold(name))
            urlretrieve(url, name)

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

    def perform_why(self, package):
        pkgs = self.load_dependency_graph()
        pkg = pkgs.find(package)
        if not pkg:
            ui.error(package, 'is not installed')
            sys.exit(1)
        for dep in pkg.incoming:
            print(ui.pkg(pkg), end='')
            while dep:
                print(' ←', ui.pkg(dep.parent), end='')
                dep = (dep.parent.incoming + [None])[0]
            print()
