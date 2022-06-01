from dataclasses import dataclass
from datetime import date
from dataclasses_json import dataclass_json

from typing import List


def _parse_companies(companies: str):
    if not companies:
        return []
    else:
        return list(map(str.strip, companies.split(',')))


@dataclass_json
@dataclass(frozen=True)
class Parameters:
    companies: List[str]
    start_date: date
    end_date: date
    historical: bool

    @staticmethod
    def factory(companies:str, start_date:date, end_date:date, historical:bool):
        return Parameters(_parse_companies(companies), start_date, end_date, historical)
    