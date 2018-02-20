import unittest
from grip.model import Package, Version


class TestPackage(unittest.TestCase):
    def test_name_sanitizer(self):
        pkg = Package('Django_module', '1.0')
        self.assertEqual(pkg.name, 'django-module')

    def test_version(self):
        pkg = Package('pkg', '1.0')
        self.assertEqual(pkg.version, Version('1.0'))
        pkg = Package('pkg', Version('1.0'))
        self.assertEqual(pkg.version, Version('1.0'))

    def test_comparison(self):
        a = Package('a', '1.0')
        a_1 = Package('a', '1.1')
        b = Package('b', '1.0')

        self.assertEqual(a, a_1)
        self.assertLess(a, b)

    def test_str(self):
        pkg = Package('Django', '1.0')
        self.assertEqual(str(pkg), 'django@1.0')
