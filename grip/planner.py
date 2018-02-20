from collections import namedtuple
import grip.ui as ui
from .model import PackageGraph

InstallAction = namedtuple('InstallAction', ['dependency', 'spec', 'version'])
RemoveAction = namedtuple('RemoveAction', ['package'])
FailAction = namedtuple('FailAction', [])


class Planner:
    def __init__(self, graph, index=None):
        self.graph = graph
        self.index = index

    def prune(self):
        for pkg in self.graph:
            if pkg.name in PackageGraph.SYSTEM_PKGS:
                continue

            if len(pkg.incoming + pkg.incoming_mismatched) == 0:
                yield RemoveAction(pkg)

    def remove(self, packages):
        for name in packages:
            pkg = self.graph.find(name)
            if pkg:
                yield RemoveAction(pkg)
            else:
                ui.error(ui.bold(name), 'is not installed')

    def install(self, dep, downgrade=False):
        installed_pkg = self.graph.find(dep.name)
        if installed_pkg and dep.matches_version(installed_pkg.version):
            ui.info(ui.dep(dep), 'is already installed as', ui.pkg(installed_pkg))
            return

        if dep.url:
            install_spec = dep.to_pip_spec()
            install_version = None
        else:
            candidates = self.index.candidates_for(dep)
            best_candidate = self.index.best_candidate_of(dep, candidates)
            if not best_candidate:
                ui.error('No packages available for', ui.dep(dep))
                latest = self.index.best_candidate_of(None, candidates)
                if latest:
                    ui.error('latest:', latest.version)
                ui.error(f'all: https://pypi.org/project/{dep.name}/#history')
                yield FailAction()

            install_spec = f'{dep.name}=={str(best_candidate.version)}'
            install_version = best_candidate.version

        if not dep.url and installed_pkg and not dep.matches_version(installed_pkg.version):
            ui.warn('Dependency mismatch')
            print(' -', ui.pkg(installed_pkg), '(installed)')
            if len(installed_pkg.incoming):
                print('   └ required by', ui.pkg(installed_pkg.incoming[0].parent, version=False))
            print(' -', ui.dep(dep), '(requested)')
            print('   └ required by', ui.pkg(dep.parent, version=False))
            if installed_pkg.version < best_candidate.version:
                ui.warn('Will upgrade')
            elif not downgrade:
                ui.warn('Will not downgrade')
                return
            else:
                ui.warn('Will downgrade')

        if installed_pkg:
            yield RemoveAction(installed_pkg)

        yield InstallAction(dep, install_spec, install_version)
