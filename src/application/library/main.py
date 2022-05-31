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

from ..library.database import get_plants, get_downloaded_files, write_measure
from ..library.shared import ENVIRONMENT, logger, upload_file, get_parameters
#from .shared import *


DOWNLOAD_PATH = os.environ["DOWNLOAD_PATH"]  # "/tmp/measures"
DESTINATION_BUCKET = os.environ["BUCKET"]
HISTORY = True
ENVIRONMENT = "prod"
COMPANIES = ["EGO Energy", "EGO Data"]


# TODO: spostare in un helper
def get_login_credentials(environment):
    environment = "prod"
    parameter_names = [
        f"/{environment}/myterna/ego-energy/user",
        f"/{environment}/myterna/ego-energy/password",
        f"/{environment}/myterna/ego-data/user",
        f"/{environment}/myterna/ego-data/password",
    ]
    response = get_parameters(parameter_names)
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        parameters = {p["Name"]: p["Value"] for p in response["Parameters"]}
        return parameters
    else:
        return {}


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
            # TODO: Credential must be removed. Access to S3 is granted with policy attached to the Task
            # aws_access_key_id=os.environ["ACCESS_KEY"],
            # aws_secret_access_key=os.environ["SECRET_KEY"],
        )

    def on_moved(self, event):
        logger.info("Uploading file % s to S3." % event.dest_path)
        # Event is modified, you can process it now
        file = event.dest_path
        upload_file(
            file,
            DESTINATION_BUCKET,
            self.s3,
            file.replace(DOWNLOAD_PATH + "/", ""),
        )


def start_watcher(src_path):
    event_handler = Handler()
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=src_path, recursive=True)
    observer.start()
    # observer.join()


def get_driver_options():
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

    return options


def wait_element(driver:webdriver, by:By, element_id:str):
    wait = WebDriverWait(driver, 30)
    return wait.until(EC.presence_of_element_located((by, element_id)))


def login(company: str, user_id: str, password: str):
    logger.info("Login with " + company + " account.")
    access = False
    while not access:
        driver = webdriver.Chrome(options=get_driver_options())
        driver.get("https://myterna.terna.it/portal/portal/myterna")
        assert "MyTerna" in driver.title
        driver.find_element(by=By.CSS_SELECTOR,
            value="div.col-m-6:nth-child(1) > a:nth-child(1)"
        ).click()
        assert "MyTerna" in driver.title

        wait_element(driver, By.NAME, "userid").send_keys(user_id)
        # wait.until(EC.presence_of_element_located((By.NAME, "userid"))).send_keys(user_id)

        driver.find_element(by=By.NAME, value="password").send_keys(password)
        driver.find_element(by=By.NAME, value="login").click()
        try:
            wait_element(driver, By.ID, "nameSurnameCustomer")
            access = True
            logger.info(f"Logged in with {company} account.")
        except Exception as e:
            access = False
            driver.close()
            # TODO: Log exception?
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
    if is_relevant:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
    else:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx")

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlAnno")

    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlAnno")
    ).select_by_value(year)

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlMese")

    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlMese")
    ).select_by_value(str(int(month)))

    if not HISTORY:
        if is_relevant:
            wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtImpiantoDesc")
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtImpiantoDesc"
            ).send_keys(p)
        else:
            wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlTipoUP")
            Select(
                driver.find_element(
                    by=By.ID, value="ctl00_cphMainPageMetering_ddlTipoUP"
                )
            ).select_by_value("UPNR_PUNTUALE")

            wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtCodiceUPDesc")

            driver.find_element(by=By.ID,
                value="ctl00_cphMainPageMetering_txtCodiceUPDesc").send_keys(p)

    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_rbTutte").click()
    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_btSearh").click()

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati")

    have_results = re.compile(".*[1-9]\d*.*")
    if have_results.match(
        driver.find_element(
            By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati"
        ).text
    ) != None:
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

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP")

    codice_up = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP"
    ).get_attribute("value")

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV")

    codice_psv = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV"
    ).get_attribute("value")

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxVersione")

    versione = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxVersione"
    ).get_attribute("value")

    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxValidatozioneTerna")

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
    if files != None and os.path.basename(filename) in files:
        driver.execute_script("window.history.go(-1)")
        return False
    else:

        wait_element(driver, By.ID, "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport")

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

        write_measure(
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
    files = get_downloaded_files(year, month, plant_type, company)

    os.makedirs(f"{DOWNLOAD_PATH}/csv/{company.lower().replace(' ', '-')}/{year}/{month}", exist_ok=True)

    driver.get("https://myterna.terna.it/metering/Home.aspx")
    if HISTORY:
        res, _, _ = search_meterings(driver, year, month, is_relevant)
        if res > 0:

            wait_element(driver, By.ID, "ctl00_cphMainPageMetering_GridView1")

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

                        wait_element(driver, By.XPATH,
                            '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]')

                        last_page = driver.find_element(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]',
                        )

                        if last_page.text == "...":
                            last_page.click()
                        else:
                            last_page.click()
                            has_next_page = False

                    wait_element(driver, By.XPATH,
                        '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[1]')

                    res = driver.find_elements(
                        By.XPATH,
                        value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                    )
                    res = res[1:-1]
                    if (len(res) - i < 0):  # if there are no more results on the page then go previous page
                        page = driver.find_element(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()-'
                            + str(x)
                            + "]",
                        )
                        x += 1
                        i = 1
                        page.click()

                    wait_element(driver, By.XPATH,
                        '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr')

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

                    filename = create_file_name(plant_type, date, codice_up,
                                                codice_psv, versione, validazione, company)

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

                    wait_element(driver, By.ID, "ctl00_cphMainPageMetering_GridView1")

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

                    filename = create_file_name(plant_type, date, codice_up,
                        codice_psv, versione, validazione, company)

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


def get_metering(relevant: bool, company: str, year: int, month: int,userid: str, password: str):
    to_do_plants, p_number = get_plants(relevant, company)
    if p_number != 0:
        found = 0
        not_found = 0
        while len(to_do_plants) > 0:
            driver = login(company, userid, password)
            to_do_plants, found, not_found = donwload_meterings(
                driver,
                company,
                year,
                month,
                relevant,
                to_do_plants,
                p_number,
                found,
                not_found,
            )  # Download EGO Energy relevant metering
        logger.info(
            f"Downloaded data of {str(found)}/{str(p_number)} plants"
        )
    else:
        logger.info(f"No metering for {company} relevant plants!")


def run():
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    companies = COMPANIES
    start_watcher(DOWNLOAD_PATH)
    current_date_time = datetime.datetime.now()
    date = current_date_time.date()
    year = date.strftime("%Y")
    month = date.strftime("%m")
    # TO DO: Spostare in application config
    credentials = get_login_credentials(ENVIRONMENT)

    # userid = credentials[f'/{ENVIRONMENT}/myterna/{company.lower().replace(" ", "-")}/user']
    # password = credentials[f'/{ENVIRONMENT}/myterna/{company.lower().replace(" ", "-")}/password']
    for company in companies:
        userid = credentials[f'/prod/myterna/{company.lower().replace(" ", "-")}/user']
        password = credentials[
            f'/prod/myterna/{company.lower().replace(" ", "-")}/password'
        ]
        if HISTORY:
            logger.info(f"Downloading history metering for {company}")
            for year in range(int(year) - 5, int(year) + 1):
                driver = login(company, userid, password)

                for month in map(str, range(1, 13)):
                    month = month.zfill(2)

                    _, found, not_found = donwload_meterings(
                        driver, company, str(year), str(month), True
                    )
                    logger.info(f"Found {found} plants for {month}/{year}")
                    logger.info(f"Not found {not_found} plants for {month}/{year}")
        else:
            logger.info(f"Downloading metering for {company}")
            # Download EGO Energy metering relevant
            get_metering(True, company, year, month, userid, password)
            # Download EGO Energy metering not relevant
            get_metering(False, company, year, month, userid, password)
    # TODO; da vedere
    return True


if __name__ == "__main__":
    run()
