import logging
import subprocess
import sys
from enum import Enum, auto
from functools import lru_cache
from typing import Callable, Dict, Optional, Set

import requests
import textdistance  # type: ignore

logger = logging.getLogger("packages_inspector")


MODULE_IGNORED = "module-ignored"


class NoPackageFound(Exception):
    pass


class ModuleIgnored(Exception):
    pass


@lru_cache
def _package_exists(package: str) -> bool:
    exists = requests.get(f"https://pypi.org/pypi/{package}/json").status_code == 200
    logger.debug(f"{package=} {exists=}")
    return exists


def _pip_search_packages(query: str) -> Set[str]:
    """ Returns the list of found packages on pypi """
    return {
        line.split(" ")[0]
        for line in subprocess.run(
            f"{sys.executable} -m pip search {query}".split(" "), capture_output=True, text=True
        ).stdout.split("\n")
        if line
    }


class MappingFinder(Enum):
    ExplicitMapping = auto()
    UsingRequirements = auto()
    UsingPipSearch = auto()
    UsingDumbAssumption = auto()


def _find_package_explicit_mapping(module: str, module_to_package_mapping: Dict[str, str], pypi_calls: bool) -> str:
    # Mapping strategy: the most accurate one
    if package := module_to_package_mapping.get(module):
        if package == MODULE_IGNORED or not pypi_calls or _package_exists(package):
            logger.debug(f"mapped {module=} with {package=} because of an explicit mapping")
        else:
            logger.warning(f"mapping found for {module=} but the {package=} does not seem to exist")
        return package
    raise NoPackageFound()


def _find_package_using_requirements(
    module: str,
    distance_threshold: int,
    packages_in_requirements: Set[str],
    interaction_hook: Callable[[MappingFinder, str, str], Optional[str]],
) -> str:
    # Find in already provided requirements via text distance algorithms
    if not packages_in_requirements:
        raise NoPackageFound()

    for algorithm in {
        textdistance.lcsstr,
        textdistance.lcsseq,
        textdistance.ratcliff_obershelp,
        textdistance.cosine,
    }:
        matches = sorted(packages_in_requirements, key=lambda x: algorithm.normalized_distance(x, module))
        package = matches[0]
        distance = algorithm.distance(package, module)
        if distance < distance_threshold:
            logger.debug(f"mapped {module=} with {package=} using the defined requirements ({algorithm=} {distance=})")
            if valid_package := interaction_hook(MappingFinder.UsingRequirements, module, package):
                return valid_package
        else:
            logger.debug(f"{algorithm=} no corresponding package in the requirements with an acceptable distance ")
    raise NoPackageFound()


def _find_package_using_pip_search(
    module: str, distance_threshold: int, interaction_hook: Callable[[MappingFinder, str, str], Optional[str]],
) -> str:
    # Find via a pip search (not super reliable)
    query = module.replace("_", " ")
    packages = _pip_search_packages(query)
    if packages:
        matches = sorted(packages, key=lambda x: textdistance.hamming.distance(x, module))
        package = matches[0]
        distance = textdistance.hamming.distance(package, module)
        if distance < distance_threshold:
            if len(packages) >= 100:
                logger.warning(
                    f"mapped {module=} with {package=} using a pip search ({distance=}) "
                    f"(WARNING: the results have been truncated)"
                )
            else:
                logger.debug(f"mapped {module=} with {package=} using a pip search ({distance=})")
            if valid_package := interaction_hook(MappingFinder.UsingPipSearch, module, package):
                return valid_package
    raise NoPackageFound()


def _find_package_using_dumb_assumption(
    module: str, interaction_hook: Callable[[MappingFinder, str, str], Optional[str]], pypi_calls: bool
) -> str:
    # Dumb assumption module = package
    if not pypi_calls or _package_exists(module):
        logger.warning(f"mapped {module=} with {module=} based on the probably wrong assumption module=package")
        if package := interaction_hook(MappingFinder.UsingDumbAssumption, module, module):
            return package
    raise NoPackageFound()


def best_package_choice(
    module: str,
    module_to_package_mapping: Dict[str, str],
    packages_in_requirements: Set[str],
    interaction_hook: Callable[[MappingFinder, str, str], Optional[str]],
    pypi_calls: bool,
    distance_threshold: int = 20,
) -> str:
    try:
        while True:
            try:
                return _find_package_explicit_mapping(module, module_to_package_mapping, pypi_calls)
            except NoPackageFound:
                pass

            try:
                return _find_package_using_requirements(
                    module, distance_threshold, packages_in_requirements, interaction_hook
                )
            except NoPackageFound:
                pass

            if pypi_calls:
                try:
                    return _find_package_using_pip_search(module, distance_threshold, interaction_hook)
                except NoPackageFound:
                    pass

            try:
                return _find_package_using_dumb_assumption(module, interaction_hook, pypi_calls)
            except NoPackageFound:
                pass

            logger.info(
                f"All the options for {module=} have been proposed, "
                "consider adding the correct package yourself with the -e option"
            )
    except ModuleIgnored:
        return MODULE_IGNORED

    raise NoPackageFound(f"Unable to find a suitable package for {module}")
