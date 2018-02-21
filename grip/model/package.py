from pip._vendor.packaging.version import Version
import pkg_resources


class Package:
    def __init__(self, name, version, metadata=None, deps=None):
        self.name = Package.sanitize_name(name)
        self.metadata = metadata
        if type(version) == str:
            self.version = Version(version)
        else:
            self.version = version
        self.deps = deps or []
        self.incoming = []
        self.incoming_mismatched = []

    @staticmethod
    def from_distribution(dist):
        return Package(dist.project_name, dist.version, metadata=dist)

    @staticmethod
    def sanitize_name(name):
        return pkg_resources.safe_name(name).lower()

    def __str__(self):
        return f'{self.name}@{self.version}'

    def __eq__(self, other):
        return self.name == other.name

    def __gt__(self, other):
        return self.name > other.name

    def __repr__(self):
        return f'<Package: {self.name}@{self.version}>'
