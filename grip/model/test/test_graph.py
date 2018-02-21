import os
import tempfile
import unittest
from grip.model import PackageGraph, Package, Dependency


class TestPackageGraph(unittest.TestCase):
    def mkgraph(self):
        return PackageGraph(
            items=[
                Package('celery', '1', deps=[Dependency('django>=2')]),
                Package('django', '2.5', deps=[Dependency('pytz>2017')]),
                Package('pytz', '2016'),
            ],
            requirements=[
                Dependency('django>1'),
            ],
        )

    def test_list(self):
        g = self.mkgraph()
        self.assertEqual(g[0].name, 'celery')
        self.assertEqual(g[1].name, 'django')

    def test_match(self):
        g = self.mkgraph()
        self.assertEqual(g.match(Dependency('django>3')), None)
        self.assertEqual(g.match(Dependency('django<3')), g.find('django'))

    def test_find(self):
        g = self.mkgraph()
        self.assertEqual(g.find('celery'), g[0])
        self.assertEqual(g.find('django'), g[1])

    def test_resolution(self):
        g = self.mkgraph()
        g.resolve_dependencies()
        self.assertEqual(g.find('django').incoming, [g.find('celery').deps[0], g.requirements.deps[0]])
        self.assertEqual(g.find('django').incoming_mismatched, [])
        self.assertEqual(g.find('pytz').incoming, [])
        self.assertEqual(g.find('pytz').incoming_mismatched, [g.find('django').deps[0]])
        self.assertEqual(g.find('celery').deps[0].resolved_to, g.find('django'))
        self.assertEqual(g.find('django').deps[0].resolved_to, None)

    def test_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(tmp + '/a-1.dist-info')
            with open(tmp + '/a-1.dist-info/METADATA', 'w') as f:
                f.write('Metadata-Version: 2.0\n')
                f.write('Name: a\n')
                f.write('Version: 1\n')
                f.write('Requires-Dist: b (>=2)\n')

            os.mkdir(tmp + '/b-2.dist-info')
            with open(tmp + '/b-2.dist-info/METADATA', 'w') as f:
                f.write('Metadata-Version: 2.0\n')
                f.write('Name: b\n')
                f.write('Version: 1\n')

            g = PackageGraph.from_directory(tmp)
            self.assertEqual(g[0].name, 'a')
            self.assertEqual(str(g[0].version), '1')
            self.assertEqual(g[1].name, 'b')
            self.assertEqual(str(g[1].version), '2')
            self.assertEqual(g[0].deps[0].name, 'b')
            self.assertTrue(g[0].deps[0].matches_version('2'))
