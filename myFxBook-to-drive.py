import time
import csv
import os
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 🔹 Lista delle coppie di valute da analizzare
currency_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", 
    "AUDUSD", "NZDUSD", "USDCAD", "EURGBP",
    "EURJPY", "EURCHF", "GBPJPY", "GBPCHF",
    "AUDJPY", "AUDNZD", "NZDJPY", "CADJPY",
    "EURAUD","AUDCAD","AUDNZD","EURNZD","GBPCAD","NZDCAD"
]

# 🔹 ID della cartella Google Drive (sostituiscilo con il tuo)
GOOGLE_DRIVE_FOLDER_ID = "1J6DfKmrhAOOennODNkdIbT56As1zbllA"

# 🔹 Nome del file CSV
CSV_FILE = "myfxbook_data.csv"

# 🔹 Configurazione Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# 🔹 Funzione per autenticarsi su Google Drive con aggiornamento automatico del token
def authenticate_google_drive():
    """Autentica con OAuth 2.0 e aggiorna automaticamente il token."""
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # 🔄 Aggiorna il token automaticamente
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # ✅ Salva il nuovo token aggiornato
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("drive", "v3", credentials=creds)

# 🔹 Funzione per estrarre solo numeri da un testo
def extract_number(text):
    match = re.search(r"[\d,]+", text)
    return match.group(0).replace(",", "") if match else None

# 🔹 Funzione per recuperare i dati da MyFxBook
def get_myfxbook_data(driver, pair):
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

# 🔹 Funzione per salvare i dati e caricare il CSV su Google Drive
def save_and_upload_csv():
    service_drive = authenticate_google_drive()

    # 🔄 Usa una singola istanza di Selenium
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

    # 🔹 Scrive o aggiorna il file CSV
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Pair", "Long %", "Short %", "Lots Long", "Lots Short", "Positions Long", "Positions Short"])
        writer.writerows(new_data)

    print(f"✅ CSV aggiornato con {len(new_data)} nuove righe.")

    # 🔄 Elimina il vecchio file su Google Drive
    query = f"name='{CSV_FILE}' and '{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    results = service_drive.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        file_id = files[0]["id"]
        service_drive.files().delete(fileId=file_id).execute()
        print(f"🗑️ File precedente eliminato: {CSV_FILE}")

    # 🔹 Carica il nuovo file CSV aggiornato
    file_metadata = {"name": CSV_FILE, "parents": [GOOGLE_DRIVE_FOLDER_ID]}
    media = MediaFileUpload(CSV_FILE, mimetype="text/csv")

    uploaded_file = service_drive.files().create(body=file_metadata, media_body=media, fields="id").execute()
    print(f"📤 File caricato su Google Drive con ID: {uploaded_file.get('id')}")

# 🔹 Esegue lo script principale
if __name__ == "__main__":
    save_and_upload_csv()
