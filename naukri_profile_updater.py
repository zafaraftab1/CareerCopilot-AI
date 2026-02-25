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

# 4 headline variants — rotated daily (keep them similar so they look genuine)
HEADLINE_VARIANTS = [
    "AWS Python Developer | Generative AI Engineer | Backend Microservices & Serverless Architect | LLM, RAG, LangChain Expert",
    "Python Developer | Generative AI Engineer | AWS Serverless & Microservices | LLM, RAG & LangChain",
    "Generative AI Engineer | Python Developer | AWS Lambda & Serverless | LangChain, RAG, LLM Expert",
    "Backend Microservices Architect | Python | AWS Cloud | Generative AI | LLM & RAG Specialist",
]

# Skills to cycle through daily (not already in profile — adds variety)
ROTATING_SKILLS = [
    "Docker", "Kubernetes", "Redis", "Git",
    "OpenAI API", "Pinecone", "DynamoDB", "Terraform",
    "GitHub Actions", "GraphQL", "MongoDB", "Jenkins",
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

    email_elem = None
    for by, sel in [
        (By.ID, "usernameField"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[placeholder*='Email']"),
    ]:
        elems = driver.find_elements(by, sel)
        if elems:
            email_elem = elems[0]
            break

    pwd_elem = None
    for by, sel in [
        (By.ID, "passwordField"),
        (By.CSS_SELECTOR, "input[type='password']"),
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

    submit_btns = driver.find_elements(By.XPATH, "//button[@type='submit']")
    if submit_btns:
        submit_btns[0].click()
    else:
        pwd_elem.submit()

    time.sleep(5)
    logged_in = "nlogin" not in driver.current_url
    log.info(f"Login — URL: {driver.current_url} | success: {logged_in}")
    return logged_in


def update_headline(driver, headline: str) -> bool:
    """Open headline edit modal, replace text, save."""
    log = logging.getLogger(__name__)
    try:
        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(4)
        wait = WebDriverWait(driver, 15)

        # Click the edit icon inside the Resume headline widget
        edit_btn = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//div[contains(@class,'widgetHead') and contains(.,'Resume headline')]"
            "//span[contains(@class,'edit')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", edit_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", edit_btn)
        log.info("Clicked headline edit button")

        # Wait for the modal textarea to appear
        textarea = wait.until(EC.visibility_of_element_located((
            By.CSS_SELECTOR, "textarea[name='resumeHeadline'], #resumeHeadlineTxt"
        )))
        time.sleep(1)

        # Clear and type new headline
        textarea.click()
        textarea.send_keys(Keys.CONTROL + "a")
        textarea.send_keys(Keys.COMMAND + "a")   # macOS
        textarea.clear()
        time.sleep(0.3)
        textarea.send_keys(headline)
        log.info(f"Typed headline: {headline}")
        time.sleep(1)

        # Click Save — use JS to avoid interactability issues (btn-dark-ot confirmed via debug)
        time.sleep(1)
        driver.execute_script("""
            var btns = document.querySelectorAll('button.btn-dark-ot');
            for (var b of btns) {
                if (b.offsetParent !== null) { b.click(); break; }
            }
        """)
        time.sleep(3)

        log.info(f"Headline saved: {headline}")
        return True

    except Exception as e:
        log.error(f"Headline update failed: {e}")
        return False


def add_key_skill(driver, skill: str) -> bool:
    """Open skills edit modal, type new skill, save."""
    log = logging.getLogger(__name__)
    try:
        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(4)
        wait = WebDriverWait(driver, 15)

        # Click the edit icon inside the Key skills widget
        edit_btn = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//div[contains(@class,'widgetHead') and contains(.,'Key skills')]"
            "//span[contains(@class,'edit')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", edit_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", edit_btn)
        log.info("Clicked skills edit button")

        # Wait for the "Add skills" input inside the modal
        skill_input = wait.until(EC.visibility_of_element_located((
            By.CSS_SELECTOR, "input[placeholder='Add skills'], #keySkillSugg"
        )))
        time.sleep(1)

        # Type skill and wait for autocomplete
        skill_input.click()
        skill_input.send_keys(skill)
        time.sleep(2)

        # Try selecting from autocomplete dropdown
        selected = False
        for dropdown_xpath in [
            f"//ul[contains(@class,'sugComp') or contains(@class,'suggestions') or contains(@class,'dropdown')]"
            f"//li[contains(.,'{skill}')]",
            f"//*[contains(@class,'Sbtn') or contains(@class,'suggestion-item') or contains(@class,'suggestItem')]"
            f"[contains(.,'{skill}')]",
        ]:
            opts = driver.find_elements(By.XPATH, dropdown_xpath)
            if opts:
                opts[0].click()
                selected = True
                log.info(f"Selected '{skill}' from dropdown")
                break

        if not selected:
            # Press Enter to add as free-text if no dropdown showed
            skill_input.send_keys(Keys.RETURN)
            log.info(f"Added '{skill}' via Enter key")

        time.sleep(1)

        # Click Save (class confirmed via debug)
        time.sleep(1)
        driver.execute_script("""
            var btns = document.querySelectorAll('button.btn-dark-ot');
            for (var b of btns) {
                if (b.offsetParent !== null) { b.click(); break; }
            }
        """)
        time.sleep(3)

        log.info(f"Skills saved with new skill: {skill}")
        return True

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
    log.info("=" * 55)
    log.info("Naukri Daily Profile Update — Starting")
    log.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 55)

    if not EMAIL or not PASSWORD:
        log.error("NAUKRI_EMAIL or NAUKRI_PASSWORD not set in .env")
        sys.exit(1)

    state = load_state()
    h_idx = state.get("headline_index", 0) % len(HEADLINE_VARIANTS)
    s_idx = state.get("skill_index", 0) % len(ROTATING_SKILLS)

    today_headline = HEADLINE_VARIANTS[h_idx]
    today_skill    = ROTATING_SKILLS[s_idx]

    log.info(f"Today's headline : {today_headline}")
    log.info(f"Today's new skill: {today_skill}")

    driver = get_driver(headless=not args.visible)
    try:
        if not naukri_login(driver, EMAIL, PASSWORD):
            log.error("Login failed — aborting.")
            return

        h_ok = update_headline(driver, today_headline)
        s_ok = add_key_skill(driver, today_skill)

        # Advance rotation for tomorrow
        state["headline_index"] = (h_idx + 1) % len(HEADLINE_VARIANTS)
        state["skill_index"]    = (s_idx + 1) % len(ROTATING_SKILLS)
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
        log.info("=" * 55)


if __name__ == "__main__":
    main()
