import psycopg2
import os
from shared import get_parameters

res = get_parameters(
    [
        "/prod/datalake/host",
        "/prod/datalake/lambda/username",
        "/prod/datalake/lambda/password",
    ]
)


def get_db_connection():
    for p in res["Parameters"]:
        if "host" in p.get("Name"):
            host = p.get("Value")
        elif "password" in p.get("Name"):
            password = p.get("Value")
        elif "username" in p.get("Name"):
            username = p.get("Value")
    return psycopg2.connect(
        database="datalake",
        user=username,
        password=password,
        host=host,
        port=5432,
        connect_timeout=3,
    )


#     cursor = db.cursor()
#     return db, cursor
