import ast
import logging
import os
import traceback
from typing import Set, Tuple

from pipreqs.pipreqs import join

logger = logging.getLogger("packages_inspector")


def get_all_imports(path: str) -> Tuple[Set[str], Set[str]]:
    """ Given a path, returns a tuple
        with the list of modules only imported,
        and the list of modules both defined and imported """
    imports = set()
    raw_imports = set()
    candidates = []
    ignore_errors = False
    ignore_dirs = [".hg", ".svn", ".git", ".mypy_cache", ".tox", "__pycache__", "env", "venv", "node_modules"]

    walk = os.walk(path, followlinks=True)
    for root, dirs, files in walk:
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        candidates.append(os.path.basename(root))
        files = [fn for fn in files if os.path.splitext(fn)[1] == ".py"]

        candidates += [os.path.splitext(fn)[0] for fn in files]
        for file_name in files:
            file_name = os.path.join(root, file_name)
            with open(file_name, "r", encoding="utf-8") as f:
                logger.debug(f"reading {file_name}")
                contents = f.read()
            try:
                tree = ast.parse(contents)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for subnode in node.names:
                            logger.debug(f"found {subnode.name=}")
                            raw_imports.add(subnode.name)

                    elif isinstance(node, ast.ImportFrom) and node.module:
                        logger.debug(f"found {node.module=}")
                        if node.level > 0:
                            logger.debug(f"ignore {node.module=} because {node.level=}")
                        else:
                            raw_imports.add(node.module)
            except Exception as exc:
                if ignore_errors:
                    traceback.print_exc()
                    logger.warn("Failed on file: %s" % file_name)
                    continue
                else:
                    logger.error("Failed on file: %s" % file_name)
                    raise exc

    # Clean up imports
    for name in [n for n in raw_imports if n]:
        # Sanity check: Name could have been None if the import
        # statement was as ``from . import X``
        # Cleanup: We only want to first part of the import.
        # Ex: from django.conf --> django.conf. But we only want django
        # as an import.
        cleaned_name, _, _ = name.partition(".")
        imports.add(cleaned_name)

    logger.debug(f"{imports=}")
    logger.debug(f"{candidates=}")

    locally_defined_modules = set(candidates) & imports

    modules = imports - locally_defined_modules
    logger.debug(f"{modules=}")

    with open(join("stdlib"), "r") as f:
        standard_modules = {x.strip() for x in f}

    return modules - standard_modules, locally_defined_modules - standard_modules
