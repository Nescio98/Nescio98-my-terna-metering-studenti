from calendar import month
from cmath import log
from multiprocessing.connection import wait
from time import sleep
import datetime
import os
import boto3
import database
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from shared import upload_file

DOWNLOAD_PATH = "/tmp/measures"


def get_plants(is_relevant, company):
    try:
        db = database.get_db_connection()
        cursor = db.cursor()
        query = (
            'SELECT "CodiceSAPR" FROM zoho_crm."Impianti" WHERE "UnitàDisp.Come" = \''
        )
        query += company + "' AND \"Rilevante\" = '" + str(is_relevant).lower() + "'; "
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


def login(company):
    logger.info("Login with " + company + " account.")
    access = False
    while not access:
        options = Options()
        options.binary_location = "/usr/bin/google-chrome-stable"
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        chrome_prefs = {
            "download.default_directory": DOWNLOAD_PATH,
            "javascript.enabled": False,
        }
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        options.experimental_options["prefs"] = chrome_prefs

        driver = webdriver.Chrome(options=options)
        driver.get("https://myterna.terna.it/portal/portal/myterna")
        assert "MyTerna" in driver.title
        driver.find_element(
            by=By.CSS_SELECTOR, value="div.col-m-6:nth-child(1) > a:nth-child(1)"
        ).click()
        assert "MyTerna" in driver.title
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "userid"))
        ).send_keys(os.environ[company.upper().replace(" ", "_") + "_USER_ID"])

        driver.find_element(by=By.NAME, value="password").send_keys(
            os.environ[company.upper().replace(" ", "_") + "_PASSWORD"]
        )
        driver.find_element(by=By.NAME, value="login").click()
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "nameSurnameCustomer"))
            )
            access = True
            logger.info("Logged in with " + company + " account.")
        except:
            access = False
            driver.close()
    return driver


def donwload_metering(plants, p_number, is_relevant, company, driver):

    x = 0  # counter for not found plants
    y = 0  # counter for the number of plants

    driver.get("https://myterna.terna.it/metering/Home.aspx")
    for p in plants:
        y = y + 1
        logger.info("Searching plant {} ({} of {}).".format(p[0], y, p_number))
        if is_relevant:
            driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
        else:
            driver.get(
                "https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx"
            )
        currentDateTime = datetime.datetime.now()
        date = currentDateTime.date()
        c_year = date.strftime("%Y")
        c_month = str(int(date.strftime("%m")) - 1)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "ctl00_cphMainPageMetering_ddlAnno"))
        )
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlAnno")
        ).select_by_value(c_year)
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlMese")
        ).select_by_value(c_month)
        if is_relevant:
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtImpiantoDesc"
            ).send_keys(p)
        else:
            Select(
                driver.find_element(
                    by=By.ID, value="ctl00_cphMainPageMetering_ddlTipoUP"
                )
            ).select_by_value("UPNR_PUNTUALE")
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtCodiceUPDesc"
            ).send_keys(p)
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_rbTutte").click()
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_btSearh").click()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati")
            )
        )
        try:
            table = driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_GridView1"
            )
            l = len(table.find_elements(by=By.CSS_SELECTOR, value="tr")) - 1
        except:
            logger.info("No data for plant: " + p[0])
            x += 1
            continue

        v = 1
        while v <= l:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_GridView1")
                )
            )
            table = driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_GridView1"
            )
            cells = table.find_elements(by=By.CSS_SELECTOR, value="tr")[
                v
            ].find_elements(by=By.TAG_NAME, value=("td"))
            cells[0].click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport")
                )
            )
            logger.info("Downloading {} metering v.{}...".format(p[0], v))
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport"
            ).click()
            while not os.path.exists(DOWNLOAD_PATH + "/Curve_97686.txt"):
                sleep(1)
            if os.path.isfile(DOWNLOAD_PATH + "/Curve_97686.txt"):
                filename = (
                    DOWNLOAD_PATH
                    + "/"
                    + company
                    + "-"
                    + str(p[0])
                    + "-"
                    + str(c_month)
                    + "-"
                    + str(c_year)
                    + "-v"
                    + str(v)
                    + ".xlsx"
                )
                while os.path.exists(filename):
                    v += 1
                    filename = (
                        DOWNLOAD_PATH
                        + "/"
                        + company
                        + "-"
                        + str(p[0])
                        + "-"
                        + str(c_month)
                        + "-"
                        + str(c_year)
                        + "-v"
                        + str(v)
                        + ".xlsx"
                    )
                os.rename(r"" + DOWNLOAD_PATH + "/Curve_97686.txt", filename)
            driver.execute_script("window.history.go(-1)")
            v += 1

    logger.info(
        "Downloaded data of " + str(p_number - x) + "/" + str(p_number) + " plants"
    )


def main(l):
    global logger
    logger = l
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
    companies = ["EGO Energy", "EGO Data"]
    for company in companies:
        driver = login(company)
        try:
            plants, p_number = get_plants(False, company)
            if p_number != 0:
                donwload_metering(
                    plants, p_number, False, company, driver
                )  # Download EGO Energy unrelevant metering
            else:
                logger.info("No metering for EGO Energy unrelevant plants!")
            plants, p_number = get_plants(True, company)
            if p_number != 0:
                donwload_metering(
                    plants, p_number, True, company, driver
                )  # Download EGO Energy relevant metering
            else:
                logger.info("No metering for EGO Energy relevant plants!")
        finally:
            driver.close()
            s3 = boto3.client(
                "s3",
                aws_access_key_id=os.environ["ACCESS_KEY"],
                aws_secret_access_key=os.environ["SECRET_KEY"],
            )
            for measure in os.listdir(DOWNLOAD_PATH):
                if measure.endswith(".xlsx"):
                    upload_file(measure, "ego-my-terna-metering", s3)


if __name__ == "__main__":
    main()
