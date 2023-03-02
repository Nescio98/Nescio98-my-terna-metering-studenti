import logging
import os
import json
import boto3
import sys
import subprocess
from logging import StreamHandler
from botocore.exceptions import ClientError
from typing import Dict, List
from application.library.new_metadata_parser import parse, rup, version

# This variables are defined in serverless:
# ENVIRONMENT
# SERVICE_NAME
# TODO: da mettere a posto (non ci dovrebbero essee riferimeti espliciti al env)
REGION = os.environ["AWS_DEFAULT_REGION"]

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


def get_parameters(parameters):
    """Get variables from AWS parameter store

    :param parameters: List of parameters to retrieve
    """
    ssm_client = boto3.client("ssm", region_name=REGION)
    return ssm_client.get_parameters(Names=parameters, WithDecryption=True)




def list_keys_from_s3(bucket_name: str, prefix: str):
    """
    List the object key in an S3 bucket filtered for a specific prefix. 
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    for object in bucket.objects.filter(Prefix=prefix, Delimiter='/'):
        if object.key.endswith('/'):
            continue
        yield object.key


def already_on_s3(bucket_mane: str, prefix: str) -> Dict[str, int]:
    keys = list_keys_from_s3(bucket_mane, prefix)
    return {rup(p):version(p) for p in map(parse, keys)}


def get_missing(uploaded_om_S3: Dict[str, int], plants: List[Dict]):
    if not uploaded_om_S3:
        return plants
    else:
        missing = [plant for plant in plants if not uploaded_om_S3.get(plant['codiceUp'], '') == plant['versione']]
        return missing
