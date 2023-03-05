import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    year: str
    month: str
    sapr: str
    relevant: bool

    def to_json(self) -> str:
        return json.dumps(self.__dict__)
    
    @staticmethod
    def from_json(jobj: str) -> 'Message':
        return Message(**json.loads(jobj))
    

