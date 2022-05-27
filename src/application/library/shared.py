import logging
import os
import json
import boto3
import sys
import subprocess
from logging import StreamHandler
from botocore.exceptions import ClientError

# This variables are defined in serverless:
# ENVIRONMENT
# SERVICE_NAME
ENVIRONMENT = os.environ["ENVIRONMENT"]
SERVICE_NAME = os.environ["SERVICE_NAME"]
REGION = os.environ["REGION"]
CONSOLE_LOGGER_LEVEL = logging.DEBUG
LOGGER_LEVEL = logging.DEBUG
EGO_LOGGER_LEVEL = 100  # logging.ERROR


class EGOHandler(StreamHandler):
    def __init__(self):
        StreamHandler.__init__(self)

    # def emit(self, record):
    #     msg = self.format(record)
    #     msg=msg.replace("'","\"")
    #     subj="Job " + SERVICE_NAME + ":{0} returned ERROR.".format(ENVIRONMENT)
    #     transmitAlert(msg, "email", EMAIL_RECIPIENTS, SERVICE_NAME, subj)


def deployToFargate():
    client = boto3.client("ecs")
    response = client.run_task(
        cluster=f"default",
        count=1,
        enableECSManagedTags=False,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [
                    "subnet-060126506e400d7cb",
                    "subnet-06144cb1fe1dbd38b",
                    "subnet-0a302591beab0099d",
                ],
                "securityGroups": [
                    "sg-013ba8c102109773e",
                ],
                "assignPublicIp": "DISABLED",
            }
        },
        propagateTags="TASK_DEFINITION",
        taskDefinition=f"prod-fargate-RunFromLambdaTest",
    )
    print(response)


def initializeLogs(
    loggerLevel, consoleLoggerLevel, customLoggerLevel, logPath=None, fileName="amr"
):
    # initializing logging formatter
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")

    # initializing logger
    logger = logging.getLogger(__name__)
    logger.setLevel(loggerLevel)

    # initializing console handler for logging
    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(consoleLoggerLevel)
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)

    # adding custom handler
    egohandler = EGOHandler()
    egohandler.setLevel(customLoggerLevel)
    egohandler.setFormatter(formatter)
    logger.addHandler(egohandler)

    logger.propagate = False

    return (
        formatter,
        logger,
        consoleHandler,
    )


_, logger, _  = initializeLogs(LOGGER_LEVEL, CONSOLE_LOGGER_LEVEL, EGO_LOGGER_LEVEL)


def publish_event(message, logger):
    payload = dict(status=message, foo_num=100)
    Entries = [
        {
            "Source": "{}.{}.{}".format(ENVIRONMENT, SERVICE_NAME, message),
            "Detail": json.dumps(payload),
            "EventBusName": "default",
            "DetailType": "topic",
        },
    ]
    client = boto3.client("events", region_name=REGION)
    logger.debug("Published event: {0}".format(Entries))
    response = client.put_events(Entries=Entries)
    logger.debug("Response from AWS: {0}".format(response))
    if response["FailedEntryCount"] == 0:
        return True
    return False


def upload_file(file_name, bucket, s3client, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param s3client: Boto3 S3 client
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    try:
        response = s3client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


def run(command, logger, log_stdout=True):
    """Execute a command inside python

    :param command: The command to execute
    :param logger: The logger object
    :param log_stdout: Optional, default value True, if True log output
    """
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    logger.info(command)
    if result.returncode == 0:
        if log_stdout and result.stdout:
            logger.debug(result.stdout)
        logger.info("Done")
    else:
        if result.stderr:
            logger.error(result.stderr)
        exit(1)


def get_parameters(parameters):
    """Get variables from AWS parameter store

    :param parameters: List of parameters to retrieve
    """
    ssm_client = boto3.client("ssm", region_name=REGION)
    return ssm_client.get_parameters(Names=parameters, WithDecryption=True)
