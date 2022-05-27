
from dataclasses import dataclass
import os

from application.config.config import Config
from application.config.environment import Environment
from application.config.parameters import Parameters

# TODO: Analizzare inpuut richiesti e modalità di esecuzione

class AppConfiguration():
    def get_environment(self) -> Environment:
        # environment = os.environ.get('ENVIRONMENT')
        # source_bucket = os.environ.get('SOURCE_BUCKET') # 'ego-gfs-data'
        # destination_bucket = source_bucket if not os.environ.get('DESTINATION_BUCKET') else os.environ.get('DESTINATION_BUCKET')
        # destination_path = os.environ.get("GRIB_PATH", "/app/data")
        # queue_name = os.environ.get('QUEUE_NAME', '')

        # return Environment.factory(environment=environment,
        #                             destination_bucket=destination_bucket,
        #                             local_grib_path=destination_path,
        #                             queue_name=queue_name
        #                         )

        return Environment(environment="environment", destination_bucket="destination_bucket", historical="", local_path="destination_path", queue_name="queue_name")


    def get_parameters(self) -> Parameters:
        keys = [] # os.environ.get('S3_KEYS', '').split(',')
        return Parameters.factory(keys=keys)


    def build(self) -> Config:
        """
        Retrieve the app configuration from the environment variables and/or command line.
        :return: A Config instance containing the configuration and parameters.
        """
        config = self.get_environment()
        if not config.queue_name:
            parameters = self.get_parameters()
            return Config(config, parameters)
        else:
            return Config(config, None)
