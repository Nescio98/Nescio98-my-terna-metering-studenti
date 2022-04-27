import psycopg2
import os

os.environ['db_hostname'] = "datalake-prod-eu-west-1b.cgeagqwpmv5k.eu-west-1.rds.amazonaws.com"
os.environ['db_user'] = "datalake_admin"
os.environ['db_password'] = "d0bDtpbjjyUrFycl"


def get_db_connection():
    return psycopg2.connect(
            database="datalake",
            user=os.getenv('db_user'),
            password=os.getenv('db_password'),
            host=os.getenv('db_hostname'),
            port=5432,
            connect_timeout=3        
            )
#     cursor = db.cursor()
#     return db, cursor


