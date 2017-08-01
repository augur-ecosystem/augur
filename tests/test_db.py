from os.path import dirname, abspath
import sys
import unittest

import augur.db

class TestDb(unittest.TestCase):

    def setUp(self):
        augur.db.prepopulate()

    def test_staff(self):
        pass