
from dataclasses import dataclass
import os
from distutils.util import strtobool

from application.config.config import Config
from application.config.environment import Environment
from application.config.parameters import Parameters

# TODO: Analizzare inpuut richiesti e modalità di esecuzione

class AppConfiguration():
    def get_environment(self) -> Environment:
        environment = os.environ.get('ENVIRONMENT')
        aws_default_region = os.environ.get('AWS_DEFULT_REGION')
        destination_bucket = os.environ.get('DESTINATION_BUCKET')
        local_path = os.environ.get('DOWNLOAD_PATH', '/app/metering')
        queue_name = os.environ.get('QUEUE_NAME', '')

        return Environment.factory(environment=environment, aws_default_region=aws_default_region, destination_bucket=destination_bucket, local_path=local_path, queue_name=queue_name)


    def get_parameters(self) -> Parameters:
        companies = os.environ.get('COMPANIES', '')
        historical = bool(strtobool(os.environ.get('HISTORICAL', 'False')))

        return Parameters.factory(companies=companies, start_date=None, end_date=None, historical=historical)


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
