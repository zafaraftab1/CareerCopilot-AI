"""Debug script to inspect Naukri profile page and find correct selectors."""
import time, os
from pathlib import Path
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

load_dotenv()
EMAIL    = os.getenv("NAUKRI_EMAIL", "")
PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

options = Options()
options.add_argument("--window-size=1600,900")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument(
    "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(options=options)
try:
    driver.get("https://www.naukri.com/nlogin/login")
    time.sleep(3)

    for by, sel in [(By.ID, "usernameField"), (By.CSS_SELECTOR, "input[type='email']")]:
        e = driver.find_elements(by, sel)
        if e: e[0].send_keys(EMAIL); break
    for by, sel in [(By.ID, "passwordField"), (By.CSS_SELECTOR, "input[type='password']")]:
        e = driver.find_elements(by, sel)
        if e: e[0].send_keys(PASSWORD); break
    btns = driver.find_elements(By.XPATH, "//button[@type='submit']")
    if btns: btns[0].click()
    time.sleep(5)

    print(f"Logged in. URL: {driver.current_url}")
    driver.get("https://www.naukri.com/mnjuser/profile")
    time.sleep(5)

    driver.save_screenshot("logs/profile_page.png")
    print("Screenshot saved to logs/profile_page.png")

    # Dump all clickable edit spans/buttons
    print("\n--- Edit buttons found ---")
    for el in driver.find_elements(By.CSS_SELECTOR, "[class*='edit'], [class*='pencil'], [title='Edit']"):
        try:
            txt = el.text.strip() or el.get_attribute("title") or el.get_attribute("class")
            parent = el.find_element(By.XPATH, "./..").get_attribute("class")
            print(f"  tag={el.tag_name} text='{txt}' class='{el.get_attribute('class')}' parent='{parent}' displayed={el.is_displayed()}")
        except: pass

    # Dump page source around headline
    src = driver.page_source
    # Find headline section
    idx = src.lower().find("headline")
    if idx > 0:
        snippet = src[max(0,idx-200):idx+500]
        Path("logs/headline_html.txt").write_text(snippet)
        print("\nHeadline HTML snippet saved to logs/headline_html.txt")

    idx2 = src.lower().find("keyskill")
    if idx2 < 0:
        idx2 = src.lower().find("key skill")
    if idx2 > 0:
        snippet2 = src[max(0,idx2-200):idx2+500]
        Path("logs/skills_html.txt").write_text(snippet2)
        print("Skills HTML snippet saved to logs/skills_html.txt")

    input("Press ENTER to close browser...")
finally:
    driver.quit()
