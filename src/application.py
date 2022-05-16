from calendar import month
from cmath import log
from multiprocessing.connection import wait
from time import sleep
import datetime
from dateutil.relativedelta import relativedelta
import os
import boto3
import database
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions as exceptions

from selenium.webdriver.support import expected_conditions as EC
import watchdog.events
import watchdog.observers
import re
from shared import upload_file

DOWNLOAD_PATH = "/tmp/measures"


class Handler(watchdog.events.PatternMatchingEventHandler):
    def __init__(self):
        # Set the patterns for PatternMatchingEventHandler
        watchdog.events.PatternMatchingEventHandler.__init__(
            self,
            patterns=["UPR*.txt", "UPNR*.txt"],
            ignore_directories=True,
            case_sensitive=False,
        )
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ["ACCESS_KEY"],
            aws_secret_access_key=os.environ["SECRET_KEY"],
        )

    # def on_created(self, event):
    #     print("Watchdog received created event - % s." % event.src_path)
    #     # Event is created, you can process it now

    # def on_modified(self, event):
    #     print("Watchdog received modified event - % s." % event.src_path)
    #     # Event is modified, you can process it now

    def on_moved(self, event):
        print("Uploading file % s to S3." % event.dest_path)
        # Event is modified, you can process it now
        file = event.dest_path
        upload_file(
            file,
            "ego-my-terna-metering",
            self.s3,
            file.replace(DOWNLOAD_PATH + "/", ""),
        )


def start_watcher(src_path):
    event_handler = Handler()
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=src_path, recursive=True)
    observer.start()
    # observer.join()


def get_plants(is_relevant, company):
    try:
        db = database.get_db_connection()
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


def login(company):
    logger.info("Login with " + company + " account.")
    access = False
    while not access:
        options = Options()
        options.binary_location = "/usr/bin/google-chrome-stable"
        # options.binary_location = "/usr/bin/chromium"
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
        wait = WebDriverWait(driver, 10)
        driver.get("https://myterna.terna.it/portal/portal/myterna")
        assert "MyTerna" in driver.title
        driver.find_element(
            by=By.CSS_SELECTOR, value="div.col-m-6:nth-child(1) > a:nth-child(1)"
        ).click()
        assert "MyTerna" in driver.title
        wait.until(EC.presence_of_element_located((By.NAME, "userid"))).send_keys(
            os.environ[company.upper().replace(" ", "_") + "_USER_ID"]
        )

        driver.find_element(by=By.NAME, value="password").send_keys(
            os.environ[company.upper().replace(" ", "_") + "_PASSWORD"]
        )
        driver.find_element(by=By.NAME, value="login").click()
        try:
            wait.until(EC.presence_of_element_located((By.ID, "nameSurnameCustomer")))
            access = True
            logger.info("Logged in with " + company + " account.")
        except:
            access = False
            driver.close()
    return driver


def create_file_name(plant_type, date, rup, x, version, validation, company):
    return (
        DOWNLOAD_PATH
        + "/"
        + company
        + "/"
        + date[:4]
        + "/"
        + date[-2:]
        + "/"
        + str(plant_type)
        + "_"
        + str(date)
        + "."
        + str(rup)
        + "."
        + str(x)
        + "."
        + str(version)
        + "."
        + str(validation)
        + ".txt"
    )


def donwload_metering(plants, p_number, is_relevant, company, driver, found, not_found):
    wait = WebDriverWait(driver, 30)
    current_date_time = datetime.datetime.now()
    date = current_date_time.date()
    year = date.strftime("%Y")
    month = (date - relativedelta(months=1)).strftime("%m")
    if not os.path.exists(DOWNLOAD_PATH + "/" + company + "/" + year + "/" + month):
        os.makedirs(DOWNLOAD_PATH + "/" + company + "/" + year + "/" + month)
    driver.get("https://myterna.terna.it/metering/Home.aspx")
    if len(plants) / 100 >= 1:
        n = 100
    else:
        n = len(plants)
    for _ in range(0, n):
        p = plants.pop()
        logger.info(
            "Searching plant {} ({} of {}).".format(
                p[0], found + not_found + 1, p_number
            )
        )
        if is_relevant:
            driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
            plant_type = "UPR"
        else:
            driver.get(
                "https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx"
            )
            plant_type = "UPNR"
        wait.until(
            EC.presence_of_element_located((By.ID, "ctl00_cphMainPageMetering_ddlAnno"))
        )
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlAnno")
        ).select_by_value(year)
        wait.until(
            EC.presence_of_element_located((By.ID, "ctl00_cphMainPageMetering_ddlMese"))
        )
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlMese")
        ).select_by_value(str(int(month)))
        if is_relevant:
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_txtImpiantoDesc")
                )
            )
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtImpiantoDesc"
            ).send_keys(p)
        else:
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_ddlTipoUP")
                )
            )
            Select(
                driver.find_element(
                    by=By.ID, value="ctl00_cphMainPageMetering_ddlTipoUP"
                )
            ).select_by_value("UPNR_PUNTUALE")
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_txtCodiceUPDesc")
                )
            )
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtCodiceUPDesc"
            ).send_keys(p)
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_rbTutte").click()
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_btSearh").click()
        wait.until(
            EC.presence_of_element_located(
                (By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati")
            )
        )
        have_results = re.compile(".*[1-9][0-9]*.*")
        if (
            have_results.match(
                driver.find_element(
                    By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati"
                ).text
            )
            != None
        ):
            found = found + 1
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_GridView1")
                )
            )
            table = driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_GridView1"
            )
            l = len(table.find_elements(by=By.CSS_SELECTOR, value="tr")) - 1
        else:
            logger.info("No data for plant: " + p[0])
            not_found += 1
            continue

        v = 1
        while v <= l:
            wait.until(
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
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP")
                )
            )
            codice_up = driver.find_element(
                By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP"
            ).get_attribute("value")
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV")
                )
            )
            codice_psv = driver.find_element(
                By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV"
            ).get_attribute("value")
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_tbxVersione")
                )
            )
            versione = driver.find_element(
                By.ID, "ctl00_cphMainPageMetering_tbxVersione"
            ).get_attribute("value")
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_tbxValidatozioneTerna")
                )
            )
            validazione = datetime.datetime.strptime(
                (
                    driver.find_element(
                        By.ID, "ctl00_cphMainPageMetering_tbxValidatozioneTerna"
                    ).get_attribute("value")
                ),
                "%d/%m/%Y %H:%M:%S",
            ).strftime("%Y%m%d%H%M%S")
            date = str(year) + str(month)
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport")
                )
            )
            logger.info("Downloading {} metering v.{}...".format(p[0], versione))
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport"
            ).click()
            while not os.path.exists(DOWNLOAD_PATH + "/Curve_97686.txt"):
                sleep(1)
            if os.path.isfile(DOWNLOAD_PATH + "/Curve_97686.txt"):
                filename = create_file_name(
                    plant_type,
                    date,
                    codice_up,
                    codice_psv,
                    versione,
                    validazione,
                    company,
                )
                os.rename(r"" + DOWNLOAD_PATH + "/Curve_97686.txt", filename)
            driver.execute_script("window.history.go(-1)")
            v += 1
    return plants, found, not_found


def main(l):
    global logger
    logger = l
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
    start_watcher(DOWNLOAD_PATH)
    companies = ["EGO Data", "EGO Energy"]
    for company in companies:
        to_do_plants, p_number = get_plants(True, company)
        if p_number != 0:
            found = 0
            not_found = 0
            while len(to_do_plants) > 0:
                driver = login(company)
                try:
                    to_do_plants, found, not_found = donwload_metering(
                        to_do_plants, p_number, True, company, driver, found, not_found
                    )  # Download EGO Energy relevant metering
                finally:
                    driver.close()
            logger.info(
                "Downloaded data of " + str(found) + "/" + str(p_number) + " plants"
            )
        else:
            logger.info("No metering for " + company + " relevant plants!")
        to_do_plants, p_number = get_plants(False, company)
        if p_number != 0:
            found = 0
            not_found = 0
            while len(to_do_plants) > 0:
                driver = login(company)
                try:
                    to_do_plants, found, not_found = donwload_metering(
                        to_do_plants, p_number, False, company, driver, found, not_found
                    )  # Download EGO Energy relevant metering
                finally:
                    driver.close()
            logger.info(
                "Downloaded data of " + str(found) + "/" + str(p_number) + " plants"
            )
        else:
            logger.info("No metering for " + company + "unrelevant plants!")


if __name__ == "__main__":
    main()
