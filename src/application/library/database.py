import psycopg2
from datetime import datetime

from ..library.shared import get_parameters, logger

# TODO: Da muovere in un helper
res = get_parameters(
    [
        "/prod/datalake/host",
        "/prod/datalake/lambda/username",
        "/prod/datalake/lambda/password",
    ]
)


def get_aws_param():
    for p in res["Parameters"]:
        if "host" in p.get("Name"):
            host = p.get("Value")
        elif "password" in p.get("Name"):
            password = p.get("Value")
        elif "username" in p.get("Name"):
            username = p.get("Value")

    return (host, username, password)


# TODO: Da rivedere (mi riconnetto ogni volta o riutilizzo la stessa connessione?)
def get_db_connection(host: str, username: str, password: str):
    return psycopg2.connect(
        database="datalake",
        user=username,
        password=password,
        host=host,
        port=5432,
        connect_timeout=3,
    )


def get_plants(is_relevant: str, company: str):
    try:
        db = get_db_connection(*get_aws_param())
        cursor = db.cursor()

        query = f"""
          SELECT
            "CodiceSAPR"
          FROM
            zoho_crm."Impianti"
          WHERE
            "UnitàDisp.Come" = '{company}'
            AND "Rilevante" = {str(is_relevant).upper()}
            AND "AttualmenteDisp.Terna?" = TRUE; """

        cursor.execute(query)
        plants = cursor.fetchall()
        p_number = len(plants)
        logger.info(
            f"Found {p_number} {company} {'relevant' if is_relevant else 'not relevant'} plants"
        )
    finally:
        cursor.close()
        db.close()
    return plants, p_number


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
        dt = datetime.now()
        ts = datetime.timestamp(dt)
        db = get_db_connection(*get_aws_param())
        cursor = db.cursor()
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
            '{ts}') """

        cursor.execute(query)
        db.commit()
    finally:
        cursor.close()
        db.close()


def get_downloaded_files(anno: int, mese: int, tipologia: str, dispacciato_da: str):
    try:
        db = get_db_connection(*get_aws_param())
        cursor = db.cursor()
        query = f"""
          SELECT
	        "nome_file"
          FROM
	        terna."downloaded_measure_files"
          WHERE
            "anno" = {anno}
            AND mese = {mese}
            AND "tipologia" = '{tipologia}'
            AND "dispacciato_da" = '{dispacciato_da}'; """

        cursor.execute(query)
        measures = cursor.fetchall()
        if len(measures) > 0:
            res = set(list(zip(*measures))[0])
        else:
            res = None
    finally:
        cursor.close()
        db.close()
    return res
