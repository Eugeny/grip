from collections import namedtuple
import grip.ui as ui
from .model import PackageGraph, Package, Dependency

InstallAction = namedtuple('InstallAction', ['dependency'])
SaveAction = namedtuple('SaveAction', ['spec'])
RemoveAction = namedtuple('RemoveAction', ['package'])
FailAction = namedtuple('FailAction', [])


class Planner:
    def __init__(self, graph, index=None, quiet=False):
        self.graph = graph
        self.index = index
        self.quiet = quiet

    def prune(self):
        for_removal = []
        for pkg in self.graph:
            if pkg.name in PackageGraph.SYSTEM_PKGS:
                continue

            if all(x in for_removal for x in (pkg.incoming + pkg.incoming_mismatched)):
                for_removal.append(pkg)

        yield from (RemoveAction(pkg) for pkg in for_removal)

    def remove(self, packages):
        for name in packages:
            pkg = self.graph.find(name)
            if pkg:
                yield RemoveAction(pkg)
            elif not self.quiet:
                ui.error(ui.bold(name), 'is not installed')

    def install(self, dep, upgrade=False, downgrade=False, save=False):
        installed_pkg = self.graph.find(dep.name)
        if installed_pkg and dep.matches_version(installed_pkg.version) and not upgrade:
            if not self.quiet:
                ui.info(ui.dep(dep), 'is already installed as', ui.pkg(installed_pkg))
            if save:
                resolved_dep = Dependency.exact(installed_pkg)
                yield SaveAction(resolved_dep)
            return

        if dep.url:
            resolved_dep = dep
        else:
            candidates = self.index.candidates_for(dep)
            best_candidate = self.index.best_candidate_of(dep, candidates)
            if not best_candidate:
                if not self.quiet:
                    ui.error('No packages available for', ui.dep(dep))
                latest = self.index.best_candidate_of(None, candidates)
                if not self.quiet:
                    if latest:
                        ui.error('latest:', latest.version)
                    ui.error(f'all: https://pypi.org/project/{dep.name}/#history')
                yield FailAction()

            resolved_dep = Dependency.exact(Package(dep.name, best_candidate.version))

        if not dep.url and installed_pkg and not dep.matches_version(installed_pkg.version):
            if not self.quiet:
                ui.warn('Dependency mismatch')
                print(' -', ui.pkg(installed_pkg), '(installed)')
                if len(installed_pkg.incoming):
                    print('   └ required by', ui.pkg(installed_pkg.incoming[0].parent, version=False))
                print(' -', ui.dep(dep), '(requested)')
                print('   └ required by', ui.pkg(dep.parent, version=False))

            if installed_pkg.version < best_candidate.version:
                if not self.quiet:
                    ui.warn('Will upgrade')
            elif not downgrade:
                if not self.quiet:
                    ui.warn('Will not downgrade')
                return
            else:
                if not self.quiet:
                    ui.warn('Will downgrade')

        if installed_pkg:
            yield RemoveAction(installed_pkg)

        yield InstallAction(resolved_dep)
        if save:
            yield SaveAction(resolved_dep)
