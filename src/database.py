import psycopg2
import os
from shared import *

res = get_parameters(
    [
        "/prod/datalake/host",
        "/prod/datalake/lambda/username",
        "/prod/datalake/lambda/password",
    ]
)


def get_db_connection():
    return psycopg2.connect(
        database="datalake",
        user=os.getenv(res[1].Value),
        password=os.getenv(res[2].Value),
        host=os.getenv(res[0].Value),
        port=5432,
        connect_timeout=3,
    )


#     cursor = db.cursor()
#     return db, cursor
