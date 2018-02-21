import unittest
from unittest.mock import MagicMock
from grip.model import Package, Dependency
from grip.index import Index


class TestIndex(unittest.TestCase):
    def test_best_candidate_of(self):
        i = Index('')
        pkgs = [Package('django', '1.0'), Package('django', '2.0'), Package('django', '3.0-beta')]
        for pkg in pkgs:
            pkg.location = MagicMock()
            pkg.location.is_wheel = False
        self.assertEquals(i.best_candidate_of(Dependency('django>=1.0'), pkgs), pkgs[1])
        self.assertEquals(i.best_candidate_of(Dependency('django>=2.0'), pkgs), pkgs[1])
        self.assertEquals(i.best_candidate_of(Dependency('django>2.0'), pkgs), pkgs[2])
        self.assertEquals(i.best_candidate_of(Dependency('django>2.0'), []), None)
        self.assertEquals(i.best_candidate_of(None, pkgs), pkgs[2])
