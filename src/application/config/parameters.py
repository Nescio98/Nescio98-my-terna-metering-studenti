from dataclasses import dataclass
from datetime import date
from dataclasses_json import dataclass_json

from typing import List



@dataclass_json
@dataclass(frozen=True)
class Parameters:
    company: str
    historical: bool

    @staticmethod
    def factory(
        company: str,
        historical: bool,
    ):
        return Parameters(
            company, historical)
