import os
import pkg_resources

from .package import Package
from .dependency import Dependency


class PackageGraph(list):
    PROJECT_PKG = '-project-'
    USER_PKG = '-you-'
    SYSTEM_PKGS = ['wheel', 'setuptools', 'pip']

    def __init__(self, items=[], requirements=[]):
        list.__init__(self, items)
        self.requirements = Package(PackageGraph.PROJECT_PKG, None)
        self.set_requirements(requirements)

    def set_requirements(self, deps):
        deps = list(deps)
        for dep in deps:
            dep.parent = self.requirements
        self.requirements.deps = sorted(deps)

    @staticmethod
    def from_directory(site_packages):
        pkgs = []
        for dir in os.listdir(site_packages):
            if dir.endswith('.dist-info'):
                dist_info = os.path.join(site_packages, dir)
                dists = pkg_resources.distributions_from_metadata(dist_info)
                for dist in dists:
                    pkg = Package.from_distribution(dist)
                    pkg.deps = sorted((Dependency(x, pkg) for x in dist.requires()), key=lambda x: str(x))
                    pkgs.append(pkg)

        return PackageGraph(sorted(pkgs))

    def find(self, name):
        name = Package.sanitize_name(name)
        for pkg in self:
            if pkg.name == name:
                return pkg

    def match(self, dep):
        for pkg in self:
            if pkg.name == dep.name and dep.matches_version(pkg.version):
                return pkg

    def resolve_dependencies(self):
        for pkg in self + [self.requirements]:
            for dep in pkg.deps:
                dep.resolved_to = None
                for candidate in self:
                    if candidate.name == dep.name:
                        if dep.matches_version(candidate.version):
                            dep.resolved_to = candidate
                            candidate.incoming.append(dep)
                        else:
                            candidate.incoming_mismatched.append(dep)
