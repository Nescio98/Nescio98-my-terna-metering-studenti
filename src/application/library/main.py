import os
import re
import datetime
from dateutil.relativedelta import relativedelta
from time import sleep
from calendar import month
from cmath import log
from multiprocessing.connection import wait
import multiprocessing
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

from application.config.environment import Environment
from application.config.parameters import Parameters

from application.library.database import get_plants, get_downloaded_files, write_measure
from application.library.shared import logger, upload_file, get_parameters


# TODO: spostare in un helper
def get_login_credentials(environment):
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


# class Handler(watchdog.events.PatternMatchingEventHandler):
#     def __init__(self, s3_client, destination_bucket_name: str, local_path: str):
#         # Set the patterns for PatternMatchingEventHandler
#         watchdog.events.PatternMatchingEventHandler.__init__(
#             self,
#             patterns=["UPR*.txt", "UPNR*.txt"],
#             ignore_directories=True,
#             case_sensitive=False,
#         )
#         # TODO: Fix this
#         # self._s3 = s3_client
#         self._s3 = boto3.client(
#             "s3",
#             # TODO: Credential must be removed. Access to S3 is granted with policy attached to the Task
#             # aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
#             # aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
#         )
#         self._destination_bucket = destination_bucket_name
#         self._local_path = local_path


def on_moved(
    filename: str,
    year,
    month,
    plant_type,
    sapr,
    codice_up,
    codice_psv,
    versione,
    validazione,
    company,
    local_path,
    destination_bucket,
    s3_client: boto3.client,
):
    logger.info("Uploading file % s to S3." % os.path.basename(filename))
    # Event is modified, you can process it now
    res = upload_file(
        filename,
        destination_bucket,
        s3_client,
        filename.replace(local_path + "/", ""),
    )
    if res:
        logger.info("File %s uploaded to S3." % os.path.basename(filename))
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
    else:
        logger.error("File %s not uploaded to S3." % os.path.basename(filename))


# def start_watcher(local_path: str, destination_bucket_name: str):
#     event_handler = Handler("mock s3 client", destination_bucket_name, local_path)
#     observer = watchdog.observers.Observer()
#     observer.schedule(event_handler, path=local_path, recursive=True)
#     observer.start()
#     # observer.join()


def get_driver_options(local_path: str):
    options = Options()
    options.binary_location = "/usr/bin/google-chrome-stable"

    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    chrome_prefs = {
        "download.default_directory": local_path,
        "javascript.enabled": False,
    }
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    options.experimental_options["prefs"] = chrome_prefs

    return options


def wait_element(driver: webdriver, by: By, element_id: str):
    wait = WebDriverWait(driver, 30)
    current_url=driver.current_url()
    try:
        wait.until(EC.presence_of_element_located((by, element_id)))
        return True
    except exceptions.TimeoutException:
        logger.info("TimeoutException, reloading page...")
        driver.get(current_url)
        try:
            wait.until(EC.presence_of_element_located((by, element_id)))
        except exceptions.TimeoutException:
            logger.info("TimeoutException, trying to login...")
            driver=login(company, userid, password, local_path)
            driver.get(current_url)
            wait = WebDriverWait(driver, 30)
            return wait.until(EC.presence_of_element_located((by, element_id))), driver
        



def login(company: str, user_id: str, password: str, local_path: str):
    logger.info("Login with " + company + " account.")
    access = False
    tries = 0
    while not access and tries <= 15:
        driver = webdriver.Chrome(options=get_driver_options(local_path))
        driver.get("https://myterna.terna.it/portal/portal/myterna")
        assert "MyTerna" in driver.title
        driver.find_element(
            by=By.CSS_SELECTOR, value="div.col-m-6:nth-child(1) > a:nth-child(1)"
        ).click()
        assert "MyTerna" in driver.title

        _,b = wait_element(driver, By.NAME, "userid").send_keys(user_id)
        if b != None:
            driver = b
        # wait.until(EC.presence_of_element_located((By.NAME, "userid"))).send_keys(user_id)

        driver.find_element(by=By.NAME, value="password").send_keys(password)
        driver.find_element(by=By.NAME, value="login").click()
        try:
            _,b =wait_element(driver, By.ID, "nameSurnameCustomer")
            if b != None:
                driver = b
            access = True
            logger.info(f"Logged in with {company} account.")
        except Exception as e:
            access = False
            tries += 1
            driver.close()
            logger.info("Login Failed")
            logger.info("Retrying login...")
    return driver


def create_file_name(
    local_path, plant_type, date, rup, x, version, validation, company
):
    return (
        local_path
        + "/terna/csv/"
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
        + ".csv"
    )


def search_meterings(
    driver: webdriver.Chrome,
    year: int,
    month: int,
    is_relevant: bool,
    p: int = 0,
    found: int = 0,
    not_found: int = 0,
    historical: bool = False,
):
    if is_relevant:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
    else:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx")

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlAnno")
    if b != None:
            driver = b

    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlAnno")
    ).select_by_value(year)

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlMese")
    if b != None:
            driver = b
    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlMese")
    ).select_by_value(str(int(month)))

    if not is_relevant:
        _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlTipoUP")
        if b != None:
            driver = b
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlTipoUP")
        ).select_by_value("UPNR_PUNTUALE")

    if not historical:
        if is_relevant:
            _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtImpiantoDesc")
            if b != None:
                driver = b
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtImpiantoDesc"
            ).send_keys(p)
        else:
            _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtCodiceUPDesc")
            if b != None:
                driver = b
            driver.find_element(
                by=By.ID, value="ctl00_cphMainPageMetering_txtCodiceUPDesc"
            ).send_keys(p)

    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_rbTutte").click()
    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_btSearh").click()

    # wait_element(driver, By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati")

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
    elif not historical:
        logger.info("No data for plant: " + p[0])
    not_found += 1
    return 0, found, not_found


def get_metering_data(driver: webdriver.Chrome):

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP")
    if b != None:
            driver = b
    codice_up = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP"
    ).get_attribute("value")

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV")
    if b != None:
            driver = b

    codice_psv = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV"
    ).get_attribute("value")

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxVersione")
    if b != None:
            driver = b
    versione = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxVersione"
    ).get_attribute("value")

    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxValidatozioneTerna")
    if b != None:
            driver = b
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
    driver: webdriver.Chrome,
    files,
    filename,
    local_path,
    sapr,
    versione,
    year,
    month,
    plant_type,
    codice_up,
    codice_psv,
    validazione,
    company,
    destination_bucket,
    s3_client: boto3.client,
):
    if files != None and os.path.basename(filename) in files:
        driver.execute_script("window.history.go(-1)")
        return False
    else:

        _,b=wait_element(
            driver, By.ID, "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport"
        )
        if b != None:
            driver = b

        logger.info(f"Downloading {sapr} metering version {versione}...")

        driver.find_element(
            by=By.ID,
            value="ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport",
        ).click()

        while len(glob(local_path + "/Curve_*.txt")) <= 0:
            sleep(1)

        downloaded_file = glob(local_path + "/Curve_*.txt")
        downloaded_file = downloaded_file[0]

        if os.path.isfile(downloaded_file):
            os.rename(r"" + downloaded_file, filename)
        p = multiprocessing.Process(
            target=on_moved,
            args=(
                filename,
                year,
                month,
                plant_type,
                sapr,
                codice_up,
                codice_psv,
                versione,
                validazione,
                company,
                local_path,
                destination_bucket,
                s3_client,
            ),
        )
        p.start()
    driver.execute_script("window.history.go(-1)")
    return True


def donwload_meterings(
    driver: webdriver.Chrome,
    company: str,
    year: int,
    month: int,
    s3_client: boto3.client,
    is_relevant: bool,
    local_path: str,
    plants: int = 0,
    p_number: int = 0,
    found: int = 0,
    not_found: int = 0,
    historical: bool = False,
    destination_bucket: str = "",
):
    if not historical:
        month = (
            datetime.datetime.strptime(month, "%m") - relativedelta(months=1)
        ).strftime("%m")
    if is_relevant:
        plant_type = "UPR"
    else:
        plant_type = "UPNR"

    files = get_downloaded_files(year, month, plant_type, company)

    os.makedirs(
        f"{local_path}/terna/csv/{company.lower().replace(' ', '-')}/{year}/{month}",
        exist_ok=True,
    )

    driver.get("https://myterna.terna.it/metering/Home.aspx")
    if historical:
        res, _, _ = search_meterings(
            driver, year, month, is_relevant, historical=historical
        )
        if res > 0:

            _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_GridView1")
            if b != None:
                driver = b
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

                        _,b=wait_element(
                            driver,
                            By.XPATH,
                            '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]',
                        )
                        if b != None:
                            driver = b

                        last_page = driver.find_element(
                            By.XPATH,
                            value='//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[last()]/td/table/tbody/tr/td[last()]',
                        )

                        if last_page.text == "...":
                            last_page.click()
                        else:
                            last_page.click()
                            has_next_page = False

                    _,b=wait_element(
                        driver,
                        By.XPATH,
                        '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr[1]',
                    )
                    if b != None:
                        driver = b

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
                        if page.text != "...":
                            x += 1
                        else:
                            x = 1
                        i = 1
                        page.click()

                    _,b=wait_element(
                        driver,
                        By.XPATH,
                        '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr',
                    )
                    if b != None:
                        driver = b

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
                        local_path,
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
                        local_path,
                        sapr,
                        versione,
                        year,
                        month,
                        plant_type,
                        codice_up,
                        codice_psv,
                        validazione,
                        company,
                        destination_bucket,
                        s3_client,
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
            return 0, 0, 0
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
                driver,
                year,
                month,
                is_relevant,
                p,
                found,
                not_found,
                historical=historical,
            )
            if res > 0:
                v = 1
                while v < res:

                    _,b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_GridView1")
                    if b != None:
                        driver = b
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
                        local_path,
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
                        local_path,
                        p[0],
                        versione,
                        year,
                        month,
                        plant_type,
                        codice_up,
                        codice_psv,
                        validazione,
                        company,
                        destination_bucket,
                        s3_client,
                    ):
                        logger.info("Skipping {} ".format(filename))
                    v += 1
        return plants, found, not_found


def get_metering(
    relevant: bool,
    company: str,
    year: int,
    month: int,
    userid: str,
    password: str,
    local_path,
    s3_client,
    destination_bucket,
):
    to_do_plants, p_number = get_plants(relevant, company)
    if p_number != 0:
        found = 0
        not_found = 0
        while len(to_do_plants) > 0:
            driver = login(company, userid, password, local_path)
            to_do_plants, found, not_found = donwload_meterings(
                driver,
                company,
                year,
                month,
                s3_client,
                relevant,
                local_path,
                to_do_plants,
                p_number,
                found,
                not_found,
                False,
                destination_bucket,
            )  # Download EGO Energy relevant metering
        logger.info(f"Downloaded data of {str(found)}/{str(p_number)} plants")
    else:
        logger.info(f"No metering for {company} relevant plants!")


def run(environment: Environment, parameters: Parameters):
    os.makedirs(environment.local_path, exist_ok=True)
    companies = parameters.companies
    # start_watcher(environment.local_path, environment.destination_bucket)
    s3_client = boto3.client("s3")
    current_date_time = datetime.datetime.now()
    date = current_date_time.date()
    c_year = date.strftime("%Y")
    c_month = date.strftime("%m")
    # TO DO: Spostare in application config
    credentials = get_login_credentials(environment.environment)
    global company, userid, password, local_path

    for company in companies:
        userid = credentials[f'/prod/myterna/{company.lower().replace(" ", "-")}/user']
        password = credentials[
            f'/prod/myterna/{company.lower().replace(" ", "-")}/password'
        ]
        if parameters.historical:
            if parameters.relevant:
                logger.info(f"Downloading history relevant metering for {company}")
                for year in range(int(c_year) - 5, int(c_year) + 1):
                    driver = login(company, userid, password, environment.local_path)
                    if year != c_year:
                        for month in map(str, range(1, 13)):
                            month = month.zfill(2)

                            _, found, not_found = donwload_meterings(
                                driver,
                                company,
                                str(year),
                                str(month),
                                s3_client,
                                is_relevant=True,
                                local_path=environment.local_path,
                                historical=True,
                                destination_bucket=environment.destination_bucket,
                            )
                    else:
                        for month in map(str, range(1, int(c_month) - 1)):
                            month = month.zfill(2)

                            _, found, not_found = donwload_meterings(
                                driver,
                                company,
                                str(year),
                                str(month),
                                s3_client,
                                is_relevant=True,
                                local_path=environment.local_path,
                                historical=True,
                                destination_bucket=environment.destination_bucket,
                            )
            else:
                logger.info(f"Downloading history unrelevant metering for {company}")
                for year in range(int(c_year) - 5, int(c_year) + 1):
                    driver = login(company, userid, password, environment.local_path)
                    if year != c_year:
                        for month in map(str, range(1, 13)):
                            month = month.zfill(2)

                            _, found, not_found = donwload_meterings(
                                driver,
                                company,
                                str(year),
                                str(month),
                                s3_client,
                                is_relevant=False,
                                local_path=environment.local_path,
                                historical=True,
                                destination_bucket=environment.destination_bucket,
                            )
                    else:
                        for month in map(str, range(1, int(c_month) - 1)):
                            month = month.zfill(2)

                        _, found, not_found = donwload_meterings(
                            driver,
                            company,
                            str(year),
                            str(month),
                            s3_client,
                            is_relevant=False,
                            local_path=environment.local_path,
                            historical=True,
                            destination_bucket=environment.destination_bucket,
                        )
        else:
            logger.info(f"Downloading metering for {company}")
            # Download EGO Energy metering relevant
            get_metering(
                True,
                company,
                c_year,
                c_month,
                userid,
                password,
                environment.local_path,
                s3_client,
                destination_bucket=environment.destination_bucket,
            )
            # Download EGO Energy metering not relevant
            get_metering(
                False,
                company,
                c_year,
                c_month,
                userid,
                password,
                environment.local_path,
                s3_client,
                destination_bucket=environment.destination_bucket,
            )
    # TODO; da vedere
    return True
