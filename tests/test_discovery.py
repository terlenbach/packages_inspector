import unittest

from packages_inspector.discovery import get_all_imports

from . import test_project_path


class TestDiscovery(unittest.TestCase):
    def test_simple_project(self):
        only_imported_modules, imported_and_defined_modules = get_all_imports(test_project_path)
        self.assertEqual(only_imported_modules, {"requests"})
        self.assertEqual(imported_and_defined_modules, {"django"})
