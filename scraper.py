import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Impostazioni Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def get_myfxbook_data():
    """Recupera le percentuali Long/Short da Myfxbook"""
    
    # Usa WebDriver Manager per scaricare automaticamente ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get("https://www.myfxbook.com/community/outlook/EURUSD")
        
        wait = WebDriverWait(driver, 15)
        long_element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'outlook-percentage-long')]")))
        short_element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'outlook-percentage-short')]")))
        
        long_percentage = long_element.text.strip()
        short_percentage = short_element.text.strip()

        if not long_percentage or not short_percentage:
            raise ValueError("❌ Errore: Dati non trovati!")
        
        return long_percentage, short_percentage
    except Exception as e:
        print(f"❌ Errore durante il recupero dei dati: {e}")
        return None, None
    finally:
        driver.quit()

def save_to_csv():
    """Salva i dati su un file CSV"""
    long_percentage, short_percentage = get_myfxbook_data()
    if long_percentage and short_percentage:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        with open("myfxbook_data.csv", "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, long_percentage, short_percentage])

        print(f"✅ {timestamp} | Long: {long_percentage} | Short: {short_percentage}")
    else:
        print("⚠️ Nessun dato valido da salvare.")

if __name__ == "__main__":
    save_to_csv()
