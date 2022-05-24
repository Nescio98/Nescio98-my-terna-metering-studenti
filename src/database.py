import psycopg2

from shared import get_parameters, logger


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


def get_plants(is_relevant, company):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        query = (
            'SELECT "CodiceSAPR" FROM zoho_crm."Impianti" WHERE "UnitàDisp.Come" = \''
        )
        query += (
            company
            + "' AND \"Rilevante\" = '"
            + str(is_relevant).lower()
            + "' AND \"AttualmenteDisp.Terna?\" = 'true'; "
        )
        cursor.execute(query)
        plants = cursor.fetchall()
        p_number = len(plants)
        logger.info(
            "Found {} {} {} plants".format(
                p_number, company, "relevant" if is_relevant else "unrelevant"
            )
        )
    finally:
        cursor.close()
        db.close()
    return plants, p_number


def upload_measure(
    nome_file,
    anno,
    mese,
    tipologia,
    sapr,
    codice_up,
    codice_psv,
    vers,
    validazione,
    dispacciato_da,
):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        query = (
            'INSERT INTO terna."downloaded_measure_files" VALUES (\''
            + nome_file
            + "','"
            + anno
            + "','"
            + mese
            + "','"
            + tipologia
            + "','"
            + sapr
            + "','"
            + codice_up
            + "','"
            + codice_psv
            + "','"
            + vers
            + "','"
            + validazione
            + "','"
            + dispacciato_da
            + "')"
        )
        cursor.execute(query)
        db.commit()
    finally:
        cursor.close()
        db.close()


def get_downloaded_files(anno, mese, tipologia, dispacciato_da):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        query = (
            'SELECT "nome_file" FROM terna."downloaded_measure_files" WHERE "anno" = \''
        )

        query += (
            anno
            + "' AND \"mese\" = '"
            + mese
            + "' AND \"tipologia\" = '"
            + tipologia
            + "' AND \"dispacciato_da\" = '"
            + dispacciato_da
            + "';"
        )

        cursor.execute(query)
        measures = cursor.fetchall()
        if len(measures) > 0:
            res = set(list(zip(*measures))[0])
            # res = [item for t in measures for item in t]
        else:
            res = None
    finally:
        cursor.close()
        db.close()
    return res


#     cursor = db.cursor()
#     return db, cursor