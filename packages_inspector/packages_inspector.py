import configparser
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import typer  # type: ignore
import yaml
from pipreqs.pipreqs import parse_requirements  # type: ignore

from .discovery import get_all_imports
from .logging import ColorFormatter, TyperHandler
from .mapping import MODULE_IGNORED, MappingFinder, ModuleIgnored, NoPackageFound, best_package_choice
from .recorder import DummyRecorder, FileRecorder, MappingRecorder

logger = logging.getLogger("packages_inspector")

app = typer.Typer()


def _keep_only_names(packages: Iterable[Dict[str, str]]) -> Set[str]:
    """ Returns a set of package names based on an iterable """
    return set(package["name"].split("[")[0] for package in packages)


class UnableToFindMapping(Exception):
    def __init__(self, module: str) -> None:
        super().__init__()
        self._module = module


def automatic_package_validation(mapping_finder: MappingFinder, module: str, package: str) -> str:
    # If the proposed package comes from the requirements file, and that the package
    # name almost matches the module name, we assume it's the right one
    if mapping_finder == MappingFinder.UsingRequirements and module.lower().replace(
        "-", "_"
    ) == package.lower().replace("-", "_"):
        return package
    raise UnableToFindMapping(module)


def interactive_package_validation(mapping_finder: MappingFinder, module: str, package: str) -> Optional[str]:
    try:
        return automatic_package_validation(mapping_finder, module, package)
    except UnableToFindMapping:
        pass

    typer.echo(
        f"""
Map the module [{typer.style(module, bold=True)}] with the package [{typer.style(package, bold=True)}]
"""
    )
    while (
        choice := typer.prompt(typer.style("What should we do (y/n/i/e/q/?)?", fg="blue", bold=True), prompt_suffix=" ")
    ) :
        if choice == "y":
            return package
        elif choice == "n":
            raise NoPackageFound()
        elif choice == "i":
            raise ModuleIgnored()
        elif choice == "e":
            return typer.prompt("Specify the package name")
        elif choice == "q":
            raise typer.Exit()
        elif choice == "?":
            typer.echo(
                """
y: accept the proposed mapping
n: do not accept the proposed mapping and try another oneÏ
i: ignore the module (it will be added to the list of ignored modules)
e: explicitly add the name of the corresponding package
q: exit the program
?: display this help
"""
            )
    raise Exception("Not supposed to be here")


def _load_context(path: Path) -> Dict[str, Any]:
    context = {}
    if path.exists():
        logger.debug("loading context")
        with open(path, "r") as f:
            context = yaml.load(f, Loader=yaml.FullLoader)
    return context


def _save_context(path: Path, context: Dict[str, Any]) -> None:
    with open(path, "w") as f:
        yaml.dump(context, f)
    logger.debug("context saved")


def _inspect(
    only_imported_modules: Set[str],
    imported_and_defined_modules: Set[str],
    interaction_hook: Callable[[MappingFinder, str, str], Optional[str]],
    recorder: MappingRecorder = DummyRecorder(),
    context: Dict[str, Any] = {},
    packages_in_requirements: Set[str] = set(),
    extra_module: List[str] = [],
    extra_package: List[str] = [],
    ignore_module: List[str] = [],
    module_to_package_mapping: Dict[str, str] = {},
    keep_package: List[str] = [],
    pypi_calls: bool = False,
) -> Tuple[Set[str], Set[str], Dict[str, Any]]:

    ignore_module_set = set(context.get("ignored_modules", [])) | set(ignore_module)
    logger.debug(f"{ignore_module_set=}")

    extra_module_cleaned_set = (
        set(map(lambda x: x.partition(".")[0], extra_module)) | set(context.get("extra_modules", []))
    ) - ignore_module_set
    logger.debug(f"{extra_module_cleaned_set=}")

    only_imported_modules -= ignore_module_set
    logger.debug(f"{only_imported_modules=}")

    required_modules = only_imported_modules | extra_module_cleaned_set
    logger.debug(f"{required_modules=}")

    imported_and_defined_modules -= ignore_module_set
    logger.debug(f"{imported_and_defined_modules=}")

    extra_package_set = set(context.get("extra_packages", [])) | set(extra_package)

    logger.info("Mapping all the modules with the corresponding packages...")
    try:
        required_packages_mapping = {
            module: recorder.record_mapping(
                module,
                best_package_choice(
                    module, module_to_package_mapping, packages_in_requirements, interaction_hook, pypi_calls
                ),
            )
            for module in required_modules
        }
        required_packages = set(package for package in required_packages_mapping.values() if package != MODULE_IGNORED)

        # Packages that corresponds to modules both defined and imported
        conflicting_packages_mapping = {
            module: recorder.record_mapping(
                module,
                best_package_choice(
                    module,
                    {**module_to_package_mapping, **required_packages_mapping},
                    packages_in_requirements,
                    interaction_hook,
                    pypi_calls,
                ),
            )
            for module in imported_and_defined_modules
        }
        conflicting_packages = set(
            package for package in conflicting_packages_mapping.values() if package != MODULE_IGNORED
        )
    except NoPackageFound as exc:
        logger.critical(str(exc))
        raise typer.Exit(code=1)
    logger.info("Mapping done")

    final_mapping = {**conflicting_packages_mapping, **required_packages_mapping, **conflicting_packages_mapping}
    final_mapping_cleaned = {module: package for module, package in final_mapping.items() if package != MODULE_IGNORED}
    ignore_module_set |= set(module for module, package in final_mapping.items() if package == MODULE_IGNORED)

    mapping_dump = "\n".join(f"{module=} {package=}" for module, package in final_mapping_cleaned.items())
    logger.debug(f"Mapping:\n{mapping_dump}")

    logger.debug(f"{required_packages=}")

    required_packages |= extra_package_set

    extra_module_cleaned_set -= ignore_module_set

    potential_missing_packages = required_packages - packages_in_requirements

    # If some of these packages, the ones that correspond to modules that are both
    # defined and imported, are present in the given requirements, we keep them
    packages_to_keep = conflicting_packages & packages_in_requirements

    packages_to_keep |= set(keep_package)

    unused_packages = packages_in_requirements - required_packages - packages_to_keep

    context = {
        "mapping": final_mapping_cleaned,
        "ignored_modules": list(ignore_module_set),
        "extra_modules": list(extra_module_cleaned_set),
        "extra_packages": list(extra_package_set),
    }

    return potential_missing_packages, unused_packages, context


def _get_package_in_line(line: str) -> Optional[str]:
    matches = re.match(r"^\s*([^#\s~=<>]*).*$", line)
    if matches:
        return matches.group(1)
    return None


def _output_results(
    potential_missing_packages: Set[str],
    unused_packages: Set[str],
    requirements: Optional[Path],
    pipfile: Optional[Path],
) -> None:
    if potential_missing_packages:
        if requirements or pipfile:
            typer.secho("\nPotential missing packages:\n", bold=True)
        else:
            typer.secho("\nDependencies:\n", bold=True)
        typer.echo("\n".join(sorted(potential_missing_packages)))

    if unused_packages:
        typer.secho("\nUnused packages:\n", bold=True)
        typer.echo("\n".join(sorted(unused_packages)))


def _apply_results(
    potential_missing_packages: Set[str],
    unused_packages: Set[str],
    requirements: Optional[Path],
    pipfile: Optional[Path],
) -> None:
    if potential_missing_packages:
        if requirements:
            with open(requirements, "a") as f:
                f.write("\n".join(potential_missing_packages))
        elif pipfile:
            raise NotImplementedError()

    if unused_packages:
        if requirements:
            with open(requirements, "r") as f:
                lines = f.readlines()
            with open(requirements, "w") as f:
                f.writelines(
                    line
                    for line in lines
                    if (package := _get_package_in_line(line)) is None or package not in unused_packages
                )
        elif pipfile:
            raise NotImplementedError()


@app.command()
def packages_inspector(
    path: Path = typer.Argument(".", help="Path of the codebase to inspect"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Also print the debug logs"),
    context_file: Path = typer.Option(Path(".packages-inspector.yaml"), help="Path to the yaml context file"),
    update_context_file: bool = typer.Option(True, help="Update the context file based on the current run"),
    pipfile: Optional[Path] = typer.Option(None, help="Specify a Pipfile as a reference"),
    requirements: Optional[Path] = typer.Option(None, help="Specify a requirements as a reference"),
    error_on_diff: bool = typer.Option(
        True, help="With a requirements specified, exit on error if missing or unused packages are found"
    ),
    extra_module: List[str] = typer.Option(None, "--extra-module", "-e", help="Extra module to consider"),
    extra_package: List[str] = typer.Option(None, "--extra-package", help="Extra package to add"),
    ignore_module: List[str] = typer.Option(None, "--ignore-module", "-i", help="Module to ignore"),
    mapping: List[str] = typer.Option(None, "--mapping", "-m", help="Explicit mapping in the form module:package"),
    keep_package: List[str] = typer.Option(None, help="Add a package that is considered required anyhow"),
    interaction: bool = typer.Option(True, help="Allow or disallow interactions"),
    pypi_calls: bool = typer.Option(
        True, help="Enable or disable the calls to pypi to search for a package, or to search if a package exists"
    ),
    apply: bool = typer.Option(False, help="Apply the changes to the Pipfile or requirements file"),
) -> None:
    """
    Find and validate the list of required packages

    A module is a module in the python context
    A package is a python package installable via pip
    A module can be part of multiple packages
    Modules and packages don't necessarily have the same name
    Modules can be defined both in PyPi (in N packages) and/or locally
    """
    handler = TyperHandler()
    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)

    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if requirements:
        packages_in_requirements = _keep_only_names(parse_requirements(requirements))
    elif pipfile:
        config = configparser.ConfigParser()
        config.read(pipfile)
        packages_in_requirements = set(config["packages"])
    else:
        packages_in_requirements = set()
    logger.debug(f"{packages_in_requirements}")

    context = _load_context(context_file)
    logger.debug(f"{context=}")

    # Some of the mmaping decisions might have already been made in a previous run
    # but didn't end up in the context file. That's why there is this recorded here.
    recorder = FileRecorder()

    logger.info("Discovering all the modules of the codebase...")
    only_imported_modules, imported_and_defined_modules = get_all_imports(path.as_posix())
    logger.info(
        f"Found {len(only_imported_modules)} imported only modules, "
        f"and {len(imported_and_defined_modules)} both imported and defined modules."
    )

    module_to_package_mapping = {
        **recorder.records,
        **context.get("mapping", {}),
        **{arg_split[0]: arg_split[1] for m in mapping if len(arg_split := m.split(":")) == 2},
    }

    interaction_hook = interactive_package_validation if interaction else automatic_package_validation

    try:
        potential_missing_packages, unused_packages, context = _inspect(
            only_imported_modules,
            imported_and_defined_modules,
            interaction_hook,
            recorder,
            context,
            packages_in_requirements,
            extra_module,
            extra_package,
            ignore_module,
            module_to_package_mapping,
            keep_package,
            pypi_calls,
        )
    except UnableToFindMapping as exc:
        critical_message = f"Unable to find the mapping for the python module {exc._module}."
        critical_message += f"\nWe couldn't find any explicit mapping in {context_file}."
        if requirements or pipfile:
            critical_message += (
                f"\nAnd we couldn't find any package with the same name in {requirements if requirements else pipfile}."
            )
        critical_message += "\n\nTry to run packages_inspector manually to update your context file."
        logger.critical(critical_message)
        raise typer.Exit(code=1)

    if update_context_file:
        _save_context(context_file, context)

    recorder.clear()

    _output_results(potential_missing_packages, unused_packages, requirements, pipfile)

    if apply:
        _apply_results(potential_missing_packages, unused_packages, requirements, pipfile)

    if potential_missing_packages or unused_packages:
        raise typer.Exit(code=1)
    else:
        typer.secho("\nAll good", fg="green")


def main() -> None:
    app()


if __name__ == "__main__":
    app()
