from dataclasses import dataclass
from datetime import date
from dataclasses_json import dataclass_json

from typing import List


def _parse_companies(companies: str):
    if not companies:
        return []
    else:
        companies = list(map(str.strip, companies.split(",")))
        for i in range(len(companies)):
            companies[i] = (
                companies[i].split()[0].upper()
                + " "
                + companies[i].split()[1][0].upper()
                + companies[i].split()[1][1:].lower()
            )
        return companies


@dataclass_json
@dataclass(frozen=True)
class Parameters:
    companies: List[str]
    start_date: date
    end_date: date
    historical: bool
    relevant: bool

    @staticmethod
    def factory(
        companies: str,
        start_date: date,
        end_date: date,
        historical: bool,
        relevant: bool,
    ):
        return Parameters(
            _parse_companies(companies), start_date, end_date, historical, relevant
        )
