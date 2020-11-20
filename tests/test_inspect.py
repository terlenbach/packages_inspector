import logging
import unittest
from typing import Optional

from packages_inspector.mapping import MappingFinder
from packages_inspector.packages_inspector import _inspect


def interaction_no_hook(mapping_finder: MappingFinder, module: str, package: str) -> Optional[str]:
    return package


class TestInpect(unittest.TestCase):
    def setUp(self):
        super().setUp()
        logging.getLogger().setLevel(logging.CRITICAL)

    def test_simple_missing_package(self) -> None:
        potential_missing_packages, unused_packages, _ = _inspect(
            only_imported_modules={"requests"},
            imported_and_defined_modules=set(),
            interaction_hook=interaction_no_hook,
        )

        self.assertEqual(potential_missing_packages, {"requests"})
        self.assertEqual(unused_packages, set())

    def test_simple_unused_package(self) -> None:
        potential_missing_packages, unused_packages, _ = _inspect(
            only_imported_modules={"requests"},
            imported_and_defined_modules=set(),
            packages_in_requirements={"requests", "pyyaml"},
            interaction_hook=interaction_no_hook,
        )

        self.assertEqual(potential_missing_packages, set())
        self.assertEqual(unused_packages, {"pyyaml"})
