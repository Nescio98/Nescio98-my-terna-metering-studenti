from dataclasses import dataclass
from dataclasses_json import dataclass_json

from typing import List


@dataclass_json
@dataclass(frozen=True)
class Parameters:
    keys: list[str]

    @staticmethod
    def factory(keys: list[str]):
        return Parameters(keys)
    