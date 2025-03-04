import time
import csv
import os
import re
import json
import io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account

# Lista delle coppie di valute da analizzare
currency_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", 
    "AUDUSD", "NZDUSD", "USDCAD", "EURGBP",
    "EURJPY", "EURCHF", "GBPJPY", "GBPCHF",
    "AUDJPY", "AUDNZD", "NZDJPY", "CADJPY",
    "EURAUD","AUDCAD","AUDNZD","EURNZD","GBPCAD","NZDCAD"
]

# ID della cartella Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1J6DfKmrhAOOennODNkdIbT56As1zbllA"
# Nome del file CSV
CSV_FILE = "myfxbook_data.csv"

# Configurazione Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def get_google_drive_service():
    """Crea il servizio API per Google Drive."""
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    service_account_info = json.loads(os.getenv("GOOGLE_DRIVE_CREDENTIALS"))
    creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    return build("drive", "v3", credentials=creds)

def download_csv_from_drive(service):
    """Scarica il CSV esistente da Google Drive (se presente)."""
    query = f"name='{CSV_FILE}' and '{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])

    if not files:
        print(f"📂 Nessun file CSV trovato su Google Drive, verrà creato un nuovo CSV.")
        return []

    file_id = files[0]["id"]
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)
    decoded_content = file_stream.read().decode("utf-8").splitlines()
    csv_reader = csv.reader(decoded_content)

    return list(csv_reader)

def extract_number(text):
    """Estrae solo il numero da una stringa come '15,999 lots'"""
    match = re.search(r"[\d,]+", text)
    return match.group(0).replace(",", "") if match else None

def get_myfxbook_data(driver, pair):
    """Recupera i dati da Myfxbook."""
    url = f"https://www.myfxbook.com/community/outlook/{pair}"
    driver.get(url)

    try:
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.ID, "currentMetricsTable")))
        rows = table.find_elements(By.TAG_NAME, "tr")

        long_percentage, short_percentage = None, None
        lots_long, lots_short = None, None
        positions_long, positions_short = None, None

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 4:
                action = cells[0].text.strip()
                percentage = cells[1].text.strip()
                lots = extract_number(cells[2].text.strip())
                positions = extract_number(cells[3].text.strip())

                if "Long" in action:
                    long_percentage = percentage
                    lots_long = lots
                    positions_long = positions
                elif "Short" in action:
                    short_percentage = percentage
                    lots_short = lots
                    positions_short = positions

        if not all([long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short]):
            print(f"⚠️ Dati incompleti per {pair}!")
            return None

        return [time.strftime("%Y-%m-%d %H:%M:%S"), pair, long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short]

    except Exception as e:
        print(f"❌ Errore su {pair}: {e}")
        return None

def save_and_upload_csv():
    """Scarica il CSV, aggiunge nuovi dati in append e ricarica il file aggiornato."""
    service = get_google_drive_service()
    existing_data = download_csv_from_drive(service)

    # Creazione di un nuovo file se non esiste
    if not existing_data:
        existing_data.append(["Timestamp", "Pair", "Long %", "Short %", "Lots Long", "Lots Short", "Positions Long", "Positions Short"])

    # Usa una singola istanza di Selenium per tutto il processo
    service_chrome = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service_chrome, options=chrome_options)
    driver.implicitly_wait(3)

    new_data = []
    for pair in currency_pairs:
        row = get_myfxbook_data(driver, pair)
        if row:
            new_data.append(row)
            print(f"✅ {row}")

    driver.quit()

    if not new_data:
        print("❌ Nessun nuovo dato da salvare!")
        return

    existing_data.extend(new_data)

    # Scrivi il nuovo file CSV aggiornato
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(existing_data)

    print(f"✅ CSV aggiornato con {len(new_data)} nuove righe.")

    # Sovrascrive il file su Google Drive
    query = f"name='{CSV_FILE}' and '{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        file_id = files[0]["id"]
        service.files().delete(fileId=file_id).execute()
        print(f"🗑️ File precedente eliminato: {CSV_FILE}")

    file_metadata = {
        "name": CSV_FILE,
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(CSV_FILE, mimetype="text/csv")

    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    print(f"📤 File aggiornato su Google Drive. ID: {uploaded_file.get('id')}")

if __name__ == "__main__":
    save_and_upload_csv()
