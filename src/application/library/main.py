import os
import re
import datetime
from dateutil.relativedelta import relativedelta
from time import sleep
from calendar import month
from cmath import log
from multiprocessing.connection import wait
from multiprocessing.pool import Pool
from glob2 import glob
import copy

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
from application.library.shared import logger, upload_file, get_parameters, already_on_s3,make_monthly_queue_list
from application.library.message import Message


# TODO: spostare in un helper

def get_login_credentials(environment):
    '''
    Ottiene le credenziali per fare il login tramite una richiesta https

    RETURN 
    ------
    dizionario con coppie nome:valore (username:password)
    '''
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
    local_path,
    destination_bucket,
    s3_client: boto3.client,
):
    '''
    definizione del nome del file da salvare su s3 in formato csv (quando scarichi l'excel devi fare un salva con nome, questo è il nome)
    '''
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

    else:
        logger.error("File %s not uploaded to S3." % os.path.basename(filename))


# def start_watcher(local_path: str, destination_bucket_name: str):
#     event_handler = Handler("mock s3 client", destination_bucket_name, local_path)
#     observer = watchdog.observers.Observer()
#     observer.schedule(event_handler, path=local_path, recursive=True)
#     observer.start()
#     # observer.join()


def get_driver_options(local_path: str):
    '''
    setta le opzioni di selenium per disabilitare i javascript.  
    '''
    options = Options()
    options.binary_location = "/usr/bin/google-chrome-stable"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    prefs = {"profile.default_content_settings.popups": 0,    
            "download.default_directory":local_path,       
            "download.prompt_for_download": False,
            "download.directory_upgrade": True}
    options.add_experimental_option("prefs", prefs)

    return options


def wait_element(driver: webdriver, by: By, element_id: str):
    '''
    prende come parametri by ed element id e aspetta fino a 30 secondi per trovare quell'oggetto nella pagina, se non lo trova la prima volta refrasha la pagina, se ancora non lo trova prova a riloggare
    '''
    wait = WebDriverWait(driver, 30)
    current_url=driver.current_url
    try:
        wait.until(EC.presence_of_element_located((by, element_id)))
        return None
    except exceptions.TimeoutException:
        logger.info("TimeoutException, reloading page...")
        driver.get(current_url)
        try:
            wait.until(EC.presence_of_element_located((by, element_id)))
            return None
        except exceptions.TimeoutException:
            logger.info("TimeoutException, trying to login...")
            driver=login(company, userid, password, local_path)
            driver.get(current_url)
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((by, element_id)))
            return driver


def login(company: str, user_id: str, password: str, local_path: str):
    '''
    prova a loggare 3 volte
    '''
    logger.info("Login with " + company + " account.")
    access = False
    tries = 0
    while not access and tries < 3:
        driver = webdriver.Chrome(options=get_driver_options(local_path))
        wait = WebDriverWait(driver, 30)
        driver.get("https://myterna.terna.it/portal/portal/myterna")
        assert "MyTerna" in driver.title
        driver.find_element(
            by=By.CSS_SELECTOR, value="div.col-m-6:nth-child(1) > a:nth-child(1)"
        ).click()
        assert "MyTerna" in driver.title
        # driver.find_element(by=By.NAME, value="userid").send_keys(user_id)
        
        driver.find_element(
            by=By.CSS_SELECTOR, value="#cookie_popup > div > div:nth-child(5) > button:nth-child(1)"
        ).click()
        
        driver.find_element(by=By.NAME, value="password")

        wait.until(EC.presence_of_element_located((By.NAME, "userid"))).send_keys(user_id)

        # driver.find_element(by=By.NAME, value="password").send_keys(password)
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)
        driver.find_element(by=By.NAME, value="login").click()
        try:
            wait.until(EC.presence_of_element_located((By.ID, "nameSurnameCustomer")))
            # b =wait_element(driver, By.ID, "nameSurnameCustomer")
            # if b != None:
            #     driver = b
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
    '''
    definizione del nome del file da salvare su s3 in formato csv (quando scarichi l'excel devi fare un salva con nome, questo è il nome)
    '''
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
    year: str,
    month: str,
    is_relevant: bool,
    p: int = 0,
):
    
    '''
    selenium accede alla pagina curve di carico per l'inserimento dei dati da scaricare.
    '''
    if is_relevant:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MainPage.aspx")
    else:
        driver.get("https://myterna.terna.it/metering/Curvecarico/MisureUPNRMain.aspx")

    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlAnno")
    if b != None:
            driver = b

    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlAnno")
    ).select_by_value(str(year))

    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlMese")
    if b != None:
            driver = b
    Select(
        driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlMese")
    ).select_by_value(str(int(month)))

    if not is_relevant:
        b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_ddlTipoUP")
        if b != None:
            driver = b
        Select(
            driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_ddlTipoUP")
        ).select_by_value("UPNR_PUNTUALE")

    #if not historical:
    if is_relevant:
        b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtImpiantoDesc")
        if b != None:
            driver = b
        driver.find_element(
            by=By.ID, value="ctl00_cphMainPageMetering_txtImpiantoDesc"
        ).send_keys(p)
    else:
        b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_txtCodiceUPDesc")
        if b != None:
            driver = b
        driver.find_element(
            by=By.ID, value="ctl00_cphMainPageMetering_txtCodiceUPDesc"
        ).send_keys(p)

    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_rbTutte").click()
    driver.find_element(by=By.ID, value="ctl00_cphMainPageMetering_btSearh").click()

    # wait_element(driver, By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati")
    
    #la regex si aspetta una stringa qualsiasi con almeno un numero diverso da 0 es.(xxx5xxxx)
    have_results = re.compile(".*[1-9]\d*.*")
  
    
    #se hai dei risultati ritorni la lunghezza della griglia contenente i risultati, altrimenti stampi che non hai trovato nulla
    if (
        have_results.match(
            driver.find_element(
                By.ID, "ctl00_cphMainPageMetering_lblRecordTrovati"
            ).text
        )
        != None
    ):
        l = len(
            driver.find_elements(
                By.XPATH, '//*[@id="ctl00_cphMainPageMetering_GridView1"]/tbody/tr'
            )
        )
        return l
    else:
        logger.info("No data for plant: " + p)

    return 0


def get_metering_data(driver: webdriver.Chrome):
    '''
    siamo in curve di carico dopo aver clickato la lente di ingrandimento, ritorniamo codice up, codice_psv, versione, validazione, sapr
    '''
    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP")
    if b != None:
            driver = b 
    codice_up = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodiceUP"
    ).get_attribute("value")

    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV")
    if b != None:
            driver = b 

    codice_psv = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxCodicePSV"
    ).get_attribute("value")

    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxVersione")
    if b != None:
            driver = b 
    versione = driver.find_element(
        By.ID, "ctl00_cphMainPageMetering_tbxVersione"
    ).get_attribute("value")

    b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_tbxValidatozioneTerna")
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
    on_s3,
    filename,
    local_path,
    sapr,
    versione,
    codice_up,
    company,
    destination_bucket,
    s3_client: boto3.client,
):
    if on_s3.get(codice_up,"") == int(versione):
        driver.execute_script("window.history.go(-1)")
        return False
    
    else:
        b=wait_element(
            driver, By.ID, "ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport"
        )
        
        if b != None:
            driver = b

        logger.info(f"Downloading {sapr} metering version {versione}...")

        driver.find_element(
            by=By.ID,
            value="ctl00_cphMainPageMetering_Toolbar2_ToolButtonExport",
        ).click()

        for sleeps in range(30):
            if len(glob("Curve_*.txt")) > 0:
                break
            elif sleeps == 300:
                pass #todo gestisci se il file non viene scaricato
            sleep(1)

        downloaded_file = glob("Curve_*.txt")
        downloaded_file = downloaded_file[0]

        if os.path.isfile(downloaded_file):
            os.rename(r"" + downloaded_file, filename)

        
        on_moved(filename,local_path,destination_bucket,s3_client,)
        
        if historical:
            current_date_time = datetime.datetime.now()
            date = current_date_time.date()
            c_year = date.strftime("%Y")
            c_month = date.strftime("%m")
            c_day = date.strftime("%d")
            os.makedirs(
                f"{local_path}/terna/csv/{company.lower().replace(' ', '-')}/conguagli/{c_year}_{c_month}_{c_day}",
                exist_ok=True,)
            name = filename.rsplit("/",1)[-1]
            duplicate_filename= f"{local_path}/terna/csv/{company.lower().replace(' ', '-')}/conguagli/{c_year}_{c_month}_{c_day}/{name}"
            #if os.path.isfile(filename):
            os.rename(r"" + filename, duplicate_filename)
            on_moved(duplicate_filename,local_path,destination_bucket,s3_client,)
        
    driver.execute_script("window.history.go(-1)")
    return True


def download_meterings(
    driver: webdriver.Chrome,
    company: str,
    year: str,
    month: str,
    s3_client: boto3.client,
    is_relevant: bool,
    local_path: str,
    plant: str = "",
    destination_bucket: str = "",
    
):
    '''
    It checks if the current file is already on s3 and, if not, it downloads the file and upload it on s3
    '''
    if is_relevant:
        plant_type = "UPR"
    else:
        plant_type = "UPNR"
        
    #dizionario contente i file di s3
    on_s3 = already_on_s3(destination_bucket, f"terna/csv/{company.lower().replace(' ', '-')}/{year}/{month}/")

    driver.get("https://myterna.terna.it/metering/Home.aspx")
 
    logger.info("Searching plant {} .".format(plant))
    res = search_meterings(
                driver,
                year,
                month,
                is_relevant,
                plant,
            )
    if res > 0:
        for v in range(1,res):
            b=wait_element(driver, By.ID, "ctl00_cphMainPageMetering_GridView1")
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

            date = str(year) + str(month)

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
                on_s3,
                filename,
                local_path,
                plant,
                versione,
                codice_up,
                company,
                destination_bucket,
                s3_client,
            ):
                logger.info("Skipping {} ".format(filename))
                return None
            
            else: return filename.replace(local_path + "/", "")


def get_metering(
    driver,
    relevant: bool,
    company: str,
    year: str,
    month: str,
    local_path,
    destination_bucket,
    plant
):
    '''
    It calls the download_metering() and it appends the result in the log_list
    
    '''
    #conversion to string from the parameters of the Message class, due to a bug
    year=str(year)
    if isinstance(month,int) and month < 10:
        month = "0"+str(month)
    else: str(month)

    s3_client = boto3.client("s3")

    os.makedirs(
        f"{local_path}/terna/csv/{company.lower().replace(' ', '-')}/{year}/{month}",
        exist_ok=True,)
    
    result = download_meterings(
                driver,
                company,
                year,
                month,
                s3_client,
                relevant,
                local_path,
                plant,
                destination_bucket,)
    if result:
        log_list.append(result)
    



def run(environment: Environment, parameters: Parameters):
    os.makedirs(environment.local_path, exist_ok=True)
    credentials = get_login_credentials(environment.environment)

    global company, userid, password, local_path,log_list, historical
    company = parameters.company
    userid = credentials[f'/prod/myterna/{company.lower().replace(" ", "-")}/user']
    password = credentials[f'/prod/myterna/{company.lower().replace(" ", "-")}/password']
    local_path = environment.local_path
    historical = parameters.historical
    log_list =[]

    driver = login(company, userid, password, local_path)
    sqs_client = boto3.client('sqs', region_name='eu-west-1')
    queue_url = 'https://sqs.eu-west-1.amazonaws.com/092381324368/test-scraper-tso'

    logger.info(f"Downloading metering for {company}")

    #i=0
    while True:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )

        if 'Messages' not in response:
            break

        for m in response['Messages']:
            msg = Message.from_json(m['Body'])
            reciept_handle = m['ReceiptHandle']
            get_metering(driver,msg.relevant,company,msg.year,msg.month,local_path,environment.destination_bucket,msg.sapr)
            #i+=1
            #logger.info(f"{i}")
            response = sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=reciept_handle
                ) 
    logger.info(f"Download completed")
    for res in log_list:
        #print(res) #invia la lista
        pass
    return True
