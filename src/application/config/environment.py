from dataclasses import dataclass
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(frozen=True)
class Environment:
    environment: str
    destination_bucket: str
    historical: bool
    local_path: str
    queue_name: bool

    @staticmethod
    def factory(environment: str, destination_bucket: str, historical: bool,  local_path: str, queue_name: str = ''):
        return Environment(environment, destination_bucket, historical, local_path, queue_name)

   