import json
import os
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def setup_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")
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


def text_of(driver):
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return body.text or ""
    except Exception:
        return ""


def detect_gate(driver):
    page = text_of(driver).lower()
    if "access denied" in page or "errors.edgesuite.net" in page:
        return "access_denied"
    if "captcha" in page:
        return "captcha"
    if "otp" in page or "one time password" in page:
        return "otp"
    if "verify" in page and "mobile" in page:
        return "mobile_verification"
    return None


def scroll_page(driver, steps=18, pause=0.9):
    for i in range(steps):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight * arguments[0] / arguments[1]);",
            i + 1,
            steps,
        )
        time.sleep(pause)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)


def cleaned_lines(page_text):
    bad = {
        "editonetheme",
        "verifiedonetheme",
        "experienceonetheme",
        "walletonetheme",
        "mailonetheme",
        "phoneonetheme",
        "calenderonetheme",
        "locationot",
        "downloadonetheme",
        "deleteonetheme",
        "tickoutlineonetheme",
    }
    out = []
    for raw in page_text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.lower() in bad:
            continue
        out.append(s)
    return out


def idx_of(lines, needle):
    n = needle.lower()
    for i, line in enumerate(lines):
        if n == line.lower():
            return i
    for i, line in enumerate(lines):
        if n in line.lower():
            return i
    return -1


def value_after(lines, label):
    i = idx_of(lines, label)
    if i >= 0 and i + 1 < len(lines):
        return lines[i + 1]
    return None


def idx_startswith(lines, prefix):
    p = prefix.lower()
    for i, line in enumerate(lines):
        if line.lower().startswith(p):
            return i
    return -1


def all_indices_of(lines, needle):
    n = needle.lower()
    out = []
    for i, line in enumerate(lines):
        if line.lower() == n:
            out.append(i)
    return out


def section_between(lines, start, end_markers):
    s = idx_of(lines, start)
    if s < 0:
        return []
    end_idx = len(lines)
    for marker in end_markers:
        e = idx_of(lines[s + 1 :], marker)
        if e >= 0:
            end_idx = min(end_idx, s + 1 + e)
    section = lines[s + 1 : end_idx]
    return [x for x in section if x]


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        k = item.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(item.strip())
    return out


def best_effort_extract(page_text, page_html):
    lines = cleaned_lines(page_text)
    data = {"top_lines": lines[:25]}

    profile_last_updated_idx = idx_startswith(lines, "Profile last updated")
    if profile_last_updated_idx >= 1:
        data["name"] = lines[profile_last_updated_idx - 1]
    if profile_last_updated_idx >= 0:
        if profile_last_updated_idx + 1 < len(lines):
            data["location"] = lines[profile_last_updated_idx + 1]
        if profile_last_updated_idx + 2 < len(lines):
            data["experience"] = lines[profile_last_updated_idx + 2]
        if profile_last_updated_idx + 3 < len(lines):
            data["current_ctc"] = lines[profile_last_updated_idx + 3]

    phones = [x for x in lines if re.fullmatch(r"\d{10,15}", x)]
    if phones:
        data["phone"] = phones[0]
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", page_text)
    if emails:
        data["email"] = emails[0]

    exp = re.search(r"(\d+(?:\.\d+)?)\s+years?", page_text, re.IGNORECASE)
    if exp:
        data["experience_years"] = exp.group(1)

    headline_idx = idx_startswith(lines, "Resume headlineeditOneTheme")
    if headline_idx >= 0 and headline_idx + 1 < len(lines):
        data["resume_headline"] = lines[headline_idx + 1]

    skills = dedupe(re.findall(r'<span class=\"chip typ-14Medium\" title=\"([^\"]+)\"', page_html))
    if skills:
        data["skills"] = skills

    edu_indices = all_indices_of(lines, "Education")
    employment_indices = all_indices_of(lines, "Employment")
    real_education_idx = edu_indices[-1] if edu_indices else -1
    real_employment_idx = -1
    for idx in employment_indices:
        if real_education_idx == -1 or idx < real_education_idx:
            real_employment_idx = idx

    employment_section = []
    if real_employment_idx >= 0 and real_education_idx > real_employment_idx:
        employment_section = lines[real_employment_idx + 1 : real_education_idx]
    employment_section = [
        x for x in employment_section
        if x.lower() not in {"add employment", "editonetheme"} and not x.lower().startswith("add job profile")
    ]
    employment = []
    i = 0
    while i + 3 < len(employment_section):
        title = employment_section[i]
        company = employment_section[i + 1]
        emp_type = employment_section[i + 2]
        duration = employment_section[i + 3]
        if " to " in duration.lower() and "(" in duration and ")" in duration:
            item = {
                "title": title,
                "company": company,
                "employment_type": emp_type,
                "duration": duration,
            }
            if i + 4 < len(employment_section) and " to " not in employment_section[i + 4].lower():
                item["summary"] = employment_section[i + 4]
                i += 1
            employment.append(item)
            i += 4
        else:
            i += 1
    if employment:
        data["employment"] = employment

    education = []
    if real_education_idx >= 0:
        end_candidates = [
            idx_of(lines[real_education_idx + 1 :], "IT skills"),
            idx_of(lines[real_education_idx + 1 :], "Projects"),
            idx_of(lines[real_education_idx + 1 :], "Profile summary"),
            idx_of(lines[real_education_idx + 1 :], "Career profile"),
        ]
        end_candidates = [x for x in end_candidates if x >= 0]
        end = (real_education_idx + 1 + min(end_candidates)) if end_candidates else len(lines)
        education = lines[real_education_idx + 1 : end]
    if education:
        data["education"] = [
            x for x in education
            if not x.lower().startswith("add ")
            and x.lower() != "editonetheme"
        ]

    cert_line = [x for x in lines if "Certification" in x and "Add details of certifications" not in x]
    cert_desc = [x for x in lines if "Add details of certifications" in x]
    if cert_line and not cert_desc:
        data["certifications"] = cert_line

    profile_summary_idx = idx_startswith(lines, "Profile summaryeditOneTheme")
    if profile_summary_idx >= 0 and profile_summary_idx + 1 < len(lines):
        data["profile_summary"] = lines[profile_summary_idx + 1]

    data["preferred_work_location"] = value_after(lines, "Preferred work location")
    data["expected_salary"] = value_after(lines, "Expected salary")
    data["current_industry"] = value_after(lines, "Current industry")
    data["department"] = value_after(lines, "Department")
    data["job_role"] = value_after(lines, "Job role")

    return data


def main():
    email = os.getenv("NAUKRI_EMAIL", "").strip()
    password = os.getenv("NAUKRI_PASSWORD", "").strip()
    out = Path(os.getenv("NAUKRI_OUT", "data/naukri_profile_scrape.json"))
    out.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "ok": False,
        "login_attempted": False,
        "login_success": False,
        "manual_step_required": False,
        "manual_reason": None,
        "current_url": None,
        "profile": {},
        "timestamp": int(time.time()),
    }

    driver = setup_driver(headless=True)
    try:
        wait = WebDriverWait(driver, 20)
        driver.get("https://www.naukri.com/nlogin/login")
        time.sleep(2)

        result["current_url"] = driver.current_url

        if "nlogin" in driver.current_url or "login" in driver.current_url:
            if not email or not password:
                result["manual_step_required"] = True
                result["manual_reason"] = "missing_credentials"
            else:
                result["login_attempted"] = True
                try:
                    wait.until(EC.presence_of_element_located((By.ID, "usernameField"))).send_keys(email)
                    driver.find_element(By.ID, "passwordField").send_keys(password)
                    driver.find_element(By.XPATH, "//button[contains(@type,'submit')]").click()
                except TimeoutException:
                    result["manual_step_required"] = True
                    result["manual_reason"] = "login_form_not_found"

                time.sleep(6)
                result["current_url"] = driver.current_url

        gate = detect_gate(driver)
        if gate:
            result["manual_step_required"] = True
            result["manual_reason"] = gate

        driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(4)
        scroll_page(driver)
        result["current_url"] = driver.current_url

        gate = detect_gate(driver)
        if gate:
            result["manual_step_required"] = True
            result["manual_reason"] = gate

        page_text = text_of(driver)
        if page_text:
            extracted = best_effort_extract(page_text, driver.page_source)
            result["profile"] = extracted

        blocked = result["manual_reason"] == "access_denied"
        result["login_success"] = (
            ("mnjuser" in driver.current_url and "login" not in driver.current_url)
            and not blocked
        )
        result["ok"] = result["login_success"] and not result["manual_step_required"]

        # Save diagnostics for selector tuning.
        screenshot_path = out.with_suffix(".png")
        html_path = out.with_suffix(".html")
        body_text_path = out.with_suffix(".txt")
        driver.save_screenshot(str(screenshot_path))
        html_path.write_text(driver.page_source, encoding="utf-8")
        body_text_path.write_text(page_text, encoding="utf-8")
        result["artifacts"] = {
            "screenshot": str(screenshot_path),
            "html": str(html_path),
            "body_text": str(body_text_path),
        }

    finally:
        driver.quit()

    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
