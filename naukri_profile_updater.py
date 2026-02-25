"""
Naukri Daily Profile Updater
Rotates resume headline and adds a key skill daily to keep profile active/visible.
Designed to run at 7 AM via macOS launchd.

Usage:
    python naukri_profile_updater.py            # headless (for scheduled run)
    python naukri_profile_updater.py --visible  # show browser (for testing)
"""

import sys
import time
import json
import os
import logging
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

load_dotenv()

# ─── USER CONFIG ─────────────────────────────────────────────────────────────

EMAIL    = os.getenv("NAUKRI_EMAIL", "")
PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

# Script rotates through these headlines one per day
HEADLINE_VARIANTS = [
    "Python Developer | AI/ML Engineer | Backend Development | 2+ Years",
    "AI/ML Engineer | Python Developer | Machine Learning | Backend",
    "Backend Developer | Python | Artificial Intelligence | Machine Learning",
    "Python | Machine Learning Engineer | AI Developer | Backend Systems",
]

# Script cycles through these skills — adds the "next" one daily
ALL_SKILLS = [
    "Python", "Machine Learning", "Deep Learning", "NLP",
    "Django", "Flask", "FastAPI", "SQL", "TensorFlow", "PyTorch",
    "Docker", "Git", "REST API", "Data Analysis", "Scikit-learn",
]

# ─── PATHS ───────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
STATE_FILE = BASE_DIR / ".profile_update_state.json"
LOG_DIR    = BASE_DIR / "logs"
LOG_FILE   = LOG_DIR / "profile_updater.log"

# ─────────────────────────────────────────────────────────────────────────────


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"headline_index": 0, "skill_index": 0, "last_run": None}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def naukri_login(driver, email: str, password: str) -> bool:
    log = logging.getLogger(__name__)
    driver.get("https://www.naukri.com/nlogin/login")
    time.sleep(3)

    # Fill email
    email_elem = None
    for by, sel in [
        (By.ID, "usernameField"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[placeholder*='Email']"),
        (By.CSS_SELECTOR, "input[name='email']"),
    ]:
        elems = driver.find_elements(by, sel)
        if elems:
            email_elem = elems[0]
            break

    # Fill password
    pwd_elem = None
    for by, sel in [
        (By.ID, "passwordField"),
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.CSS_SELECTOR, "input[name='password']"),
    ]:
        elems = driver.find_elements(by, sel)
        if elems:
            pwd_elem = elems[0]
            break

    if not email_elem or not pwd_elem:
        log.error("Login form fields not found")
        return False

    email_elem.clear()
    email_elem.send_keys(email)
    pwd_elem.clear()
    pwd_elem.send_keys(password)

    # Submit
    submit_btns = driver.find_elements(By.XPATH, "//button[@type='submit']")
    if submit_btns:
        submit_btns[0].click()
    else:
        pwd_elem.submit()

    time.sleep(5)
    logged_in = "nlogin" not in driver.current_url
    log.info(f"Login result — URL: {driver.current_url} | logged_in: {logged_in}")
    return logged_in


def update_headline(driver, headline: str) -> bool:
    log = logging.getLogger(__name__)
    try:
        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(4)
        wait = WebDriverWait(driver, 15)

        # Click the pencil/edit icon near the Resume Headline section
        edit_clicked = False
        for xpath in [
            "//div[contains(@class,'resumeHeadline')]//span[contains(@class,'edit') or contains(@class,'pencil')]",
            "//section[contains(@class,'resumeHeadline')]//span[@title='Edit']",
            "//div[@id='resumeHeadline']//span[contains(@class,'edit')]",
            "//p[@class='headline']//parent::div//span[contains(@class,'edit')]",
        ]:
            elems = driver.find_elements(By.XPATH, xpath)
            if elems:
                driver.execute_script("arguments[0].click();", elems[0])
                edit_clicked = True
                time.sleep(2)
                break

        if not edit_clicked:
            log.warning("Headline edit button not found — trying JS scroll + click")
            driver.execute_script(
                "document.querySelectorAll('[class*=edit]').forEach(e => {"
                "  if(e.closest('[class*=headline]')) e.click();"
                "});"
            )
            time.sleep(2)

        # Find the textarea / input
        input_elem = None
        for by, sel in [
            (By.CSS_SELECTOR, "textarea[name='headline']"),
            (By.CSS_SELECTOR, "input[name='headline']"),
            (By.XPATH, "//textarea[contains(@placeholder,'eadline')]"),
            (By.XPATH, "//input[contains(@placeholder,'eadline')]"),
            (By.CSS_SELECTOR, ".editHeadline textarea"),
            (By.CSS_SELECTOR, ".editHeadline input"),
        ]:
            elems = driver.find_elements(by, sel)
            if elems:
                input_elem = elems[0]
                break

        if not input_elem:
            log.warning("Headline input field not found")
            return False

        # Clear and type new headline
        input_elem.click()
        input_elem.send_keys(Keys.CONTROL + "a")
        input_elem.send_keys(Keys.DELETE)
        input_elem.clear()
        time.sleep(0.5)
        input_elem.send_keys(headline)
        time.sleep(1)

        # Click Save
        for xpath in [
            "//button[contains(text(),'Save')]",
            "//button[contains(@class,'save')]",
            "//input[@type='submit']",
        ]:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                btns[0].click()
                time.sleep(3)
                log.info(f"Headline updated: {headline}")
                return True

        log.warning("Save button not found after editing headline")
        return False

    except Exception as e:
        log.error(f"Headline update failed: {e}")
        return False


def add_key_skill(driver, skill: str) -> bool:
    log = logging.getLogger(__name__)
    try:
        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(4)
        wait = WebDriverWait(driver, 15)

        # Click edit on Key Skills section
        edit_clicked = False
        for xpath in [
            "//div[contains(@class,'keySkills')]//span[contains(@class,'edit') or contains(@class,'pencil')]",
            "//section[contains(@class,'keySkills')]//span[@title='Edit']",
            "//div[@id='keySkills']//span[contains(@class,'edit')]",
        ]:
            elems = driver.find_elements(By.XPATH, xpath)
            if elems:
                driver.execute_script("arguments[0].click();", elems[0])
                edit_clicked = True
                time.sleep(2)
                break

        if not edit_clicked:
            log.warning("Skills edit button not found")
            return False

        # Find skills input field
        skill_input = None
        for by, sel in [
            (By.XPATH, "//input[contains(@placeholder,'kill')]"),
            (By.CSS_SELECTOR, "input[placeholder*='skill']"),
            (By.CSS_SELECTOR, "input[placeholder*='Skill']"),
            (By.CSS_SELECTOR, ".keyskillSuggest input"),
        ]:
            elems = driver.find_elements(by, sel)
            if elems:
                skill_input = elems[0]
                break

        if not skill_input:
            log.warning("Skill input field not found")
            return False

        skill_input.click()
        skill_input.send_keys(skill)
        time.sleep(2)

        # Select from autocomplete dropdown
        selected_from_dropdown = False
        for xpath in [
            f"//ul[contains(@class,'suggestionsDropdown')]//li[contains(text(),'{skill}')]",
            f"//div[contains(@class,'dropdown')]//li[normalize-space()='{skill}']",
            f"//ul[contains(@class,'suggestions')]//li[contains(.,'{skill}')]",
        ]:
            opts = driver.find_elements(By.XPATH, xpath)
            if opts:
                opts[0].click()
                selected_from_dropdown = True
                time.sleep(1)
                break

        if not selected_from_dropdown:
            skill_input.send_keys(Keys.RETURN)
            time.sleep(1)

        # Click Save
        for xpath in [
            "//button[contains(text(),'Save')]",
            "//button[contains(@class,'save')]",
        ]:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                btns[0].click()
                time.sleep(3)
                log.info(f"Skill added: {skill}")
                return True

        log.warning("Save button not found after adding skill")
        return False

    except Exception as e:
        log.error(f"Skill update failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Naukri Daily Profile Updater")
    parser.add_argument(
        "--visible", action="store_true",
        help="Show browser window (useful for debugging)"
    )
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger(__name__)
    log.info("=" * 50)
    log.info("Naukri Daily Profile Update — Starting")
    log.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 50)

    if not EMAIL or not PASSWORD:
        log.error("NAUKRI_EMAIL or NAUKRI_PASSWORD not set. Add them to .env file.")
        sys.exit(1)

    state = load_state()

    # Pick today's headline and skill
    h_idx = state.get("headline_index", 0) % len(HEADLINE_VARIANTS)
    s_idx = state.get("skill_index", 0) % len(ALL_SKILLS)
    today_headline = HEADLINE_VARIANTS[h_idx]
    today_skill    = ALL_SKILLS[s_idx]

    log.info(f"Today's headline: {today_headline}")
    log.info(f"Today's skill:    {today_skill}")

    driver = get_driver(headless=not args.visible)
    try:
        logged_in = naukri_login(driver, EMAIL, PASSWORD)

        if not logged_in:
            log.error("Login failed — stopping.")
            return

        h_ok = update_headline(driver, today_headline)
        s_ok = add_key_skill(driver, today_skill)

        # Advance rotation indexes for tomorrow
        state["headline_index"] = (h_idx + 1) % len(HEADLINE_VARIANTS)
        state["skill_index"]    = (s_idx + 1) % len(ALL_SKILLS)
        state["last_run"]           = datetime.now().isoformat()
        state["last_headline"]      = today_headline
        state["last_skill_added"]   = today_skill
        state["headline_updated"]   = h_ok
        state["skill_updated"]      = s_ok
        save_state(state)

        log.info(f"Result — Headline: {'OK' if h_ok else 'FAILED'} | Skill: {'OK' if s_ok else 'FAILED'}")

    except Exception as e:
        log.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        driver.quit()
        log.info("Browser closed. Done.")


if __name__ == "__main__":
    main()