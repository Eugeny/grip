import unittest
from grip.model import PackageGraph, Package, Dependency
from grip.index import Index
from grip.planner import Planner, InstallAction, RemoveAction, SaveAction, FailAction


class TestPackageGraph(unittest.TestCase):
    def mkplanner(self):
        p = Planner(graph=PackageGraph(
            items=[
                Package('celery', '1', deps=[Dependency('django>=2')]),
                Package('django', '2.5', deps=[Dependency('pytz>2017')]),
                Package('pytz', '2016'),
                Package('wheel', '1.0'),
            ],
            requirements=[
                Dependency('django>1'),
            ],
        ), quiet=True)
        p.graph.resolve_dependencies()
        return p

    def assertPlanEquals(self, a, b):
        self.assertEquals(list(a), b)

    def test_remove(self):
        p = self.mkplanner()
        self.assertPlanEquals(p.remove(['django']), [RemoveAction(p.graph.find('django'))])

    def test_prune(self):
        p = self.mkplanner()
        self.assertPlanEquals(p.prune(), [RemoveAction(p.graph.find('celery'))])

    def test_install_url(self):
        p = self.mkplanner()
        d = Dependency('new==2.0')
        d.url = 'git@server:acme/new.git'
        self.assertPlanEquals(p.install(d), [InstallAction(d)])
        self.assertEquals(next(p.install(d)).dependency.url, d.url)

    def test_install_index(self):
        p = self.mkplanner()
        p.index = Index('')
        pkgs = [Package('django', '1.0'), Package('django', '2.0'), Package('django', '3.0-beta')]
