import abc
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

logger = logging.getLogger("packages_inspector")


# This class below is here because of:
# https://github.com/python/mypy/issues/5374
@dataclass
class _MappingRecorder:
    records: Dict[str, str] = field(default_factory=dict)


class MappingRecorder(_MappingRecorder, abc.ABC):
    @abc.abstractmethod
    def clear(self) -> None:
        ...

    @abc.abstractmethod
    def record_mapping(self, module: str, package: str) -> str:
        ...


@dataclass
class FileRecorder(MappingRecorder):
    records_file: str = ".mappings"

    def __post_init__(self) -> None:
        logger.debug(f"looking up {self.records_file}")
        if Path(self.records_file).exists():
            with open(self.records_file, "rb") as f:
                try:
                    self.records = pickle.load(f)
                except Exception as err:
                    logger.exception(f"could not load {self.records_file}: {err}")
                    raise

    def clear(self) -> None:
        if (path := Path(self.records_file)).exists():
            path.unlink()

    def record_mapping(self, module: str, package: str) -> str:
        logger.debug(f"saving the mapping {module=} {package=}")
        self.records[module] = package
        with open(self.records_file, "wb") as f:
            pickle.dump(self.records, f)
        return package


class DummyRecorder(MappingRecorder):
    def clear(self) -> None:
        pass

    def record_mapping(self, module: str, package: str) -> str:
        return package
