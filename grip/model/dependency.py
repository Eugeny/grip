import pkg_resources
from pip.req.req_install import InstallRequirement
from pip._vendor.packaging.requirements import Requirement

from .package import Package


class Dependency:
    def __init__(self, req, parent=None):
        self.url = None
        if isinstance(req, InstallRequirement):
            self.req = req.req
            if req.link:
                self.url = req.link.url
        elif isinstance(req, str):
            self.req = Requirement(req)
        elif isinstance(req, pkg_resources.Requirement):
            self.req = req
        else:
            raise TypeError('Must be an InstallRequirement, Requirement or a str, was: %s' % type(req))

        self.parent = parent
        self.resolved_to = None
        self.potential_candidate = None

    @staticmethod
    def exact(package):
        return Dependency(f'{package.name}=={package.version}')

    @property
    def name(self):
        return Package.sanitize_name(self.req.name)

    @property
    def specifier(self):
        return self.req.specifier

    def matches_version(self, version):
        return len(list(self.req.specifier.filter([str(version)]))) > 0

    def __str__(self):
        if self.url:
            return f'{self.url}#egg={str(self.req)}'
        else:
            return str(self.req)

    def __gt__(self, other):
        return self.name > other.name
