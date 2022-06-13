from dataclasses import dataclass

from .environment import Environment
from .parameters import Parameters


@dataclass
class Config:
    environment: Environment
    parameters: Parameters

    @staticmethod
    def factory(environment: Environment, parameters: Parameters):
        return Config(environment=environment, parameters=parameters)
