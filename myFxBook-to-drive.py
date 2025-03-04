import time
import csv
import os
import re  # Per pulire i dati
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Lista delle coppie di valute da analizzare
currency_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", 
    "AUDUSD", "NZDUSD", "USDCAD", "EURGBP",
    "EURJPY", "EURCHF", "GBPJPY", "GBPCHF",
    "AUDJPY", "AUDNZD", "NZDJPY", "CADJPY",
    "EURAUD","AUDCAD","AUDNZD","EURNZD","GBPCAD","NZDCAD"
]

# Nome del file CSV
CSV_FILE = "myfxbook_data.csv"

# ID della cartella Google Drive (modifica con il tuo ID corretto)
GOOGLE_DRIVE_FOLDER_ID = "1J6DfKmrhAOOennODNkdIbT56As1zbllA"

# Configurazione Selenium (ottimizzata)
chrome_options = Options()
chrome_options.add_argument("--headless")  # Esegue senza interfaccia grafica
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("start-maximized")
chrome_options.add_argument("enable-automation")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

def authenticate_google_drive():
    """Autentica l'utente con OAuth 2.0 e restituisce il servizio Google Drive."""
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    
    creds = None
    if os.path.exists("token.json"):
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    return build("drive", "v3", credentials=creds)

def upload_to_drive(service):
    """Carica il file su Google Drive."""
    file_metadata = {
        "name": CSV_FILE,
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(CSV_FILE, mimetype="text/csv")

    try:
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"📤 File caricato con successo su Google Drive. ID: {uploaded_file.get('id')}")
    except Exception as e:
        print(f"❌ Errore durante il caricamento su Google Drive: {e}")

def extract_number(text):
    """Estrae solo il numero da una stringa come '15,999 lots'"""
    match = re.search(r"[\d,]+", text)  # Trova numeri con virgole
    if match:
        return match.group(0).replace(",", "")  # Rimuove la virgola e restituisce solo il numero
    return None

def get_myfxbook_data(driver, pair):
    """Recupera le percentuali Long/Short, i lotti e le posizioni per una specifica coppia di valute"""

    url = f"https://www.myfxbook.com/community/outlook/{pair}"
    driver.get(url)

    try:
        # Aspetta il caricamento della tabella (max 10 sec)
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.ID, "currentMetricsTable")))

        # Trova le righe della tabella
        rows = table.find_elements(By.TAG_NAME, "tr")

        # Variabili per memorizzare i dati
        long_percentage, short_percentage = None, None
        lots_long, lots_short = None, None
        positions_long, positions_short = None, None

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 4:  # La riga deve avere almeno 4 colonne
                action = cells[0].text.strip()  # Long o Short
                percentage = cells[1].text.strip()
                lots = extract_number(cells[2].text.strip())  # Rimuove "lots"
                positions = extract_number(cells[3].text.strip())  # Rimuove le "," nelle posizioni

                if "Long" in action:
                    long_percentage = percentage
                    lots_long = lots
                    positions_long = positions
                elif "Short" in action:
                    short_percentage = percentage
                    lots_short = lots
                    positions_short = positions

        # Controllo che tutti i dati siano presenti
        if not all([long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short]):
            print(f"⚠️ Dati incompleti per {pair}!")
            return pair, None, None, None, None, None, None

        return pair, long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short

    except Exception as e:
        print(f"❌ Errore su {pair}: {e}")
        return pair, None, None, None, None, None, None

def save_to_csv():
    """Salva i dati per più coppie di valute su un file CSV, più veloce"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # Usa una singola istanza di Selenium per tutto il processo
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)  # Attesa implicita per ridurre il codice di attesa manuale

    # Verifica se il CSV esiste
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Scrive l'header solo se il file non esiste
        if not file_exists:
            writer.writerow(["Timestamp", "Pair", "Long %", "Short %", "Lots Long", "Lots Short", "Positions Long", "Positions Short"])

        for pair in currency_pairs:
            pair, long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short = get_myfxbook_data(driver, pair)
            if all([long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short]):
                writer.writerow([timestamp, pair, long_percentage, short_percentage, lots_long, lots_short, positions_long, positions_short])
                print(f"✅ {timestamp} | {pair} | Long: {long_percentage} | Short: {short_percentage} | Lots Long: {lots_long} | Lots Short: {lots_short} | Positions Long: {positions_long} | Positions Short: {positions_short}")
            else:
                print(f"⚠️ Nessun dato valido per {pair}")

    driver.quit()  # Chiudi il browser solo alla fine

    # Carica su Google Drive
    service_drive = authenticate_google_drive()
    upload_to_drive(service_drive)

if __name__ == "__main__":
    save_to_csv()
