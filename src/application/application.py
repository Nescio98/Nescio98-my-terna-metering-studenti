from config.config import Config
from config.environment import Environment
from config.parameters import Parameters

from library.main import run


class Application:
    def __init__(self, environment: Environment, parameters: Parameters):
        self.environment = environment
        self.parameters = parameters

    def run(self):
        return run(self.environment, self.parameters)


def factory(config: Config):
    return Application(config.environment, config.parameters)
