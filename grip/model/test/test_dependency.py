import pkg_resources
import unittest
from grip.model import Dependency, Version, Package


class TestDependency(unittest.TestCase):
    def test_ctor_str(self):
        dep = Dependency('django==2.0')
        self.assertEqual(dep.name, 'django')
        self.assertTrue(dep.matches_version('2.0'))
        self.assertFalse(dep.matches_version('2.1'))

    def test_ctor_pkgr_req(self):
        req = pkg_resources.Requirement('django==2.0')
        dep = Dependency(req)
        self.assertEqual(dep.name, 'django')
        self.assertTrue(dep.matches_version('2.0'))
        self.assertFalse(dep.matches_version('2.1'))

    def test_ctor_err(self):
        with self.assertRaises(TypeError):
            Dependency(2)

    def test_matching(self):
        dep = Dependency('celery>=3,<5')
        self.assertFalse(dep.matches_version('2.7'))
        self.assertTrue(dep.matches_version(Version('3.0')))
        self.assertTrue(dep.matches_version('3.2'))
        self.assertFalse(dep.matches_version('5'))

    def test_compare(self):
        a = Dependency('celery>=3,<5')
        b = Dependency('django==2')
        self.assertGreater(b, a)
        self.assertLess(a, b)

    def test_exact(self):
        a = Dependency('django==2')
        b = Dependency.exact(Package('django' ,'2'))
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.specifier, b.specifier)

    def test_str(self):
        dep = Dependency.exact(Package('django' ,'2'))
        self.assertEqual(str(dep), 'django==2')
        dep = Dependency('django==2')
        dep.url = 'git+git@github.com:a/b.git'
        self.assertEqual(str(dep), dep.url + '#egg=django==2')
