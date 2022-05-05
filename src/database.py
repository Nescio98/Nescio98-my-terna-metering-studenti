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
        user=res["Parameters"][1].get("Value"),
        password=res["Parameters"][2].get("Value"),
        host=res["Parameters"][0].get("Value"),
        port=5432,
        connect_timeout=3,
    )


#     cursor = db.cursor()
#     return db, cursor
