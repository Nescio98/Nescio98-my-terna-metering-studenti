from dataclasses import dataclass
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(frozen=True)
class Environment:
    environment: str
    aws_default_region: str
    destination_bucket: str
    local_path: str
    queue_name: str

    @staticmethod
    def factory(environment: str, aws_default_region: str, destination_bucket: str,  local_path: str, queue_name: str = ''):
        return Environment(environment, aws_default_region, destination_bucket, local_path, queue_name)

   