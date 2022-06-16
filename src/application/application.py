from application.config.config import Config
from application.config.environment import Environment
from application.config.parameters import Parameters

from application.library.main import run


class Application:
    def __init__(self, environment: Environment, parameters: Parameters):
        self.environment = environment
        self.parameters = parameters

    def run(self):
        return run(self.environment, self.parameters)


def factory(config: Config):
    return Application(config.environment, config.parameters)
