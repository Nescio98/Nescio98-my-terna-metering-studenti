import os
import re
import datetime
from dateutil.relativedelta import relativedelta
from time import sleep
from calendar import month
from cmath import log
from multiprocessing.connection import wait
from glob2 import glob

import boto3
import watchdog.events
import watchdog.observers

from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions as exceptions
from selenium.webdriver.support import expected_conditions as EC

import database
from shared import logger
from shared import upload_file
from shared import *


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

    def on_moved(self, event):
        logger.info("Uploading file % s to S3." % event.dest_path)
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
        + "/csv/"
        + company.lower().replace(" ", "-")
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


def search_meterings(driver, year, month, is_relevant, p=0, found=0, not_found=0):
    wait = WebDriverWait(driver, 30)
    if is_relevant:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
    else:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx")
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
    if not HISTORY:
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
    have_results = re.compile(".*[1-9]\d*.*")
    if (
        have_results.match(
            driver.find_element(
                By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati"
            ).text
        )
        != None
    ):
        found = found + 1
        l = len(
            driver.find_elements(
                By.XPATH, '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr'
            )
        )
        return l, found, not_found
    elif not HISTORY:
        logger.info("No data for plant: " + p[0])
    not_found += 1
    return 0, found, not_found


def get_metering_data(driver):
    wait = WebDriverWait(driver, 30)
    wait.until(
        EC.presence_of_element_located((By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP"))
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
        EC.presence_of_element_located((By.ID, "ctl00_cphMainPageMetering_tbxVersione"))
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
    sapr = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxImpiantoCod"
    ).get_attribute("value")
    return codice_up, codice_psv, versione, validazione, sapr


def download(
    driver,
    files,
    filename,
    sapr,
    versione,
    year,
    month,
    plant_type,
    codice_up,
    codice_psv,
    validazione,
    company,
):
    wait = WebDriverWait(driver, 30)
    if files != None and os.path.basename(filename) in files:
        return False
    else:
        wait.until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport",
                )
            )
        )
        logger.info("Downloading {} metering v.{}...".format(sapr, versione))
        driver.find_element(
            by=By.ID,
            value="ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport",
        ).click()
        while len(glob(DOWNLOAD_PATH + "/Curve_*.txt")) <= 0:
            sleep(1)
        downloaded_file = glob(DOWNLOAD_PATH + "/Curve_*.txt")
        downloaded_file = downloaded_file[0]
        if os.path.isfile(downloaded_file):
            os.rename(r"" + downloaded_file, filename)
        database.upload_measure(
            os.path.basename(filename),
            year,
            month,
            plant_type,
            sapr,
            codice_up,
            codice_psv,
            versione,
            validazione,
            company,
        )
    driver.execute_script("window.history.go(-1)")
    return True


def donwload_meterings(
    driver,
    wait,
    company,
    year,
    month,
    is_relevant,
    plants=0,
    p_number=0,
    found=0,
    not_found=0,
):
    if not HISTORY:
        month = (
            datetime.datetime.strptime(month, "%m") - relativedelta(months=1)
        ).strftime("%m")
    if is_relevant:
        plant_type = "UPR"
    else:
        plant_type = "UPNR"
    files = database.get_downloaded_files(year, month, plant_type, company)

    os.makedirs(
        DOWNLOAD_PATH
        + "/csv/"
        + company.lower().replace(" ", "-")
        + "/"
        + year
        + "/"
        + month,
        exist_ok=True,
    )
    driver.get("https://myterna.terna.it/metering/Home.aspx")
    if HISTORY:
        res, _, _ = search_meterings(driver, year, month, is_relevant)
        if res > 0:
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "ctl00_cphMainPageMetering_GridView1")
                )
            )
            table = driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_GridView1"
            )
            if len(table.find_elements(by=By.CSS_SELECTOR, value="tr")) > 0:
                x = 1  # cycle throught pages
                i = 1  # cycle throught page results
                has_next_page = True
                new_metering = True
                while new_metering:
                    while has_next_page:
                        wait.until(
                            EC.presence_of_element_located(
                                (
                                    By.XPATH,
                                    '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]',
                                )
                            )
                        )
                        last_page = driver.find_element(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]',
                        )
                        if last_page.text == "...":
                            last_page.click()
                        else:
                            last_page.click()
                            has_next_page = False
                    wait.until(
                        EC.presence_of_element_located(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                        )
                    )
                    res = driver.find_elements(
                        By.XPATH,
                        value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                    )
                    res = res[1:-1]
                    if (
                        len(res) - i < 0
                    ):  # if there are no more results on the page then go previous page
                        page = driver.find_element(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()-'
                            + str(x)
                            + "]",
                        )
                        x += 1
                        i = 1
                        page.click()
                    wait.until(
                        EC.presence_of_element_located(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                        )
                    )
                    res = driver.find_elements(
                        By.XPATH,
                        value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                    )
                    res = res[1:-1]
                    cells = res[len(res) - i].find_elements(by=By.TAG_NAME, value="td")
                    cells[0].click()
                    (
                        codice_up,
                        codice_psv,
                        versione,
                        validazione,
                        sapr,
                    ) = get_metering_data(driver)
                    date = year + month
                    filename = create_file_name(
                        plant_type,
                        date,
                        codice_up,
                        codice_psv,
                        versione,
                        validazione,
                        company,
                    )

                    if not download(
                        driver,
                        files,
                        filename,
                        sapr,
                        versione,
                        year,
                        month,
                        plant_type,
                        codice_up,
                        codice_psv,
                        validazione,
                        company,
                    ):
                        logger.info(
                            "Didn't found new {} metering for company {}, year {}, month {}".format(
                                plant_type, company, year, month
                            )
                        )
                        new_metering = False
                    i += 1
                return plants, found, not_found
        else:
            logger.info(
                "Didn't found any metering for company {}, type {}, year {}, month {}".format(
                    company, plant_type, year, month
                )
            )
    else:
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
            res, found, not_found = search_meterings(
                driver, year, month, is_relevant, p, found, not_found
            )
            if res > 0:
                v = 1
                while v < res:
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
                    codice_up, codice_psv, versione, validazione, _ = get_metering_data(
                        driver
                    )
                    date = year + month
                    filename = create_file_name(
                        plant_type,
                        date,
                        codice_up,
                        codice_psv,
                        versione,
                        validazione,
                        company,
                    )

                    if not download(
                        driver,
                        files,
                        filename,
                        p[0],
                        versione,
                        year,
                        month,
                        plant_type,
                        codice_up,
                        codice_psv,
                        validazione,
                        company,
                    ):
                        logger.info("Skipping {} ".format(filename))
                    v += 1
        return plants, found, not_found


HISTORY = False


def main():
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    companies = ["EGO Energy", "EGO Data"]
    start_watcher(DOWNLOAD_PATH)
    current_date_time = datetime.datetime.now()
    date = current_date_time.date()
    year = date.strftime("%Y")
    month = date.strftime("%m")
    for company in companies:
        if HISTORY:
            logger.info("Downloading history metering for {}".format(company))
            for year in range(int(year) - 5, int(year) + 1):
                driver = login(company)
                wait = WebDriverWait(driver, 30)
                for month in range(1, 13):
                    if month < 10:
                        month = "0" + str(month)
                    _, found, not_found = donwload_meterings(
                        driver, wait, company, str(year), str(month), True
                    )
                    logger.info("Found {} plants for {}/{}".format(found, month, year))
                    logger.info(
                        "Not found {} plants for {}/{}".format(not_found, month, year)
                    )
        else:
            logger.info("Downloading metering for {}".format(company))
            to_do_plants, p_number = database.get_plants(True, company)
            if p_number != 0:
                found = 0
                not_found = 0
                while len(to_do_plants) > 0:
                    driver = login(company)
                    wait = WebDriverWait(driver, 30)
                    to_do_plants, found, not_found = donwload_meterings(
                        driver,
                        wait,
                        company,
                        year,
                        month,
                        True,
                        to_do_plants,
                        p_number,
                        found,
                        not_found,
                    )  # Download EGO Energy relevant metering
                logger.info(
                    "Downloaded data of " + str(found) + "/" + str(p_number) + " plants"
                )
            else:
                logger.info("No metering for " + company + " relevant plants!")
            to_do_plants, p_number = database.get_plants(False, company)
            if p_number != 0:
                found = 0
                not_found = 0
                while len(to_do_plants) > 0:
                    driver = login(company)
                    wait = WebDriverWait(driver, 30)
                    to_do_plants, found, not_found = donwload_meterings(
                        driver,
                        wait,
                        company,
                        year,
                        month,
                        False,
                        to_do_plants,
                        p_number,
                        found,
                        not_found,
                    )  # Download EGO Energy relevant metering
                logger.info(
                    "Downloaded data of " + str(found) + "/" + str(p_number) + " plants"
                )
            else:
                logger.info("No metering for " + company + "unrelevant plants!")


if __name__ == "__main__":
    main()
