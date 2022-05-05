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
        user=res[1].Value,
        password=res[2].Value,
        host=res[0].Value,
        port=5432,
        connect_timeout=3,
    )


#     cursor = db.cursor()
#     return db, cursor
