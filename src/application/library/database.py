from typing_extensions import final
import psycopg2
from datetime import datetime

from shared import get_parameters, logger

# TODO: Da muovere in un helper
# TODO: gestire staging
res = get_parameters(
    [
        "/prod/datalake/host",
        "/prod/datalake/database",
        "/prod/datalake/lambda/username",
        "/prod/datalake/lambda/password",
    ]
)


def get_aws_param():
    for p in res["Parameters"]:
        if "host" in p.get("Name"):
            host = p.get("Value")
        elif "database" in p.get("Name"):
            database = p.get("Value")
        elif "password" in p.get("Name"):
            password = p.get("Value")
        elif "username" in p.get("Name"):
            username = p.get("Value")

    return (host, database, username, password)


# TODO: Da rivedere (mi riconnetto ogni volta o riutilizzo la stessa connessione?)
def get_db_connection(host: str, database: str, username: str, password: str):
    try:
        connection = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=host,
            port=5432,
            connect_timeout=3,
        )
        return connection
    except (Exception, psycopg2.Error) as e:
        logger.exception(f"Cannot connect to database {database}", e)


def execute_query(connection, query):
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except (Exception, psycopg2.Error) as e:
        logger.exception("Error executing query", e)
    finally:
        if connection:
            cursor.close()
            connection.close()


def get_plants(is_relevant: bool, company: str):
    query = f"""
        SELECT
            "CodiceSAPR"
        FROM
            zoho_crm."Impianti"
        WHERE
            "UnitàDisp.Come" = '{company}' AND
            "Rilevante" = {str(is_relevant).upper()} AND
            "AttualmenteDisp.Terna?" = TRUE; """

    conn = get_db_connection(*get_aws_param())
    plants = execute_query(conn, query)
    p_number = len(plants)
    logger.info(
        f"Found {p_number} {company} {'relevant' if is_relevant else 'not relevant'} plants"
    )
    return plants, p_number


def get_downloaded_files(anno: int, mese: int, tipologia: str, dispacciato_da: str):
    query = f"""
        SELECT
            "nome_file"
        FROM
            terna."downloaded_measure_files"
        WHERE
            "anno" = {anno} AND
             mese = {mese} AND
            "tipologia" = '{tipologia}' AND
            "dispacciato_da" = '{dispacciato_da}'; """

    conn = get_db_connection(*get_aws_param())
    measures = execute_query(conn, query)
    return set(list(zip(*measures))[0]) if len(measures) > 0 else set()


def write_measure(
    nome_file: str,
    anno: int,
    mese: int,
    tipologia: str,
    sapr: str,
    codice_up: str,
    codice_psv: str,
    vers: str,
    validazione: str,
    dispacciato_da: str,
):
    try:
        connection = get_db_connection(*get_aws_param())
        cursor = connection.cursor()
        query = f"""
          INSERT INTO terna."downloaded_measure_files" VALUES (
            '{nome_file}',
             {anno},
             {mese},
            '{tipologia}',
            '{sapr}',
            '{codice_up}',
            '{codice_psv}',
             {vers},
             {validazione},
            '{dispacciato_da}',
            '{datetime.utcnow()}'); """

        cursor.execute(query)
        connection.commit()
    except (Exception, psycopg2.Error) as e:
        logger.exception(
            f"Error when trying to insert downloaded measure file for {nome_file}", e
        )
    finally:
        if connection:
            cursor.close()
            connection.close()
