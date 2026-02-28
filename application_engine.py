"""
Application automation engine for job applications
"""
from datetime import datetime, date
from models import db, JobApplication, JobListing, DailyApplicationLog
from resume_matcher import SkillMatcher
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
import time

import re
import logging
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

class ApplicationEngine:
    """
    Handles job application automation and tracking
    """

    def __init__(self, config=None):
        self.config = config or Config()
        self.skill_matcher = SkillMatcher()
        self.daily_limit = self._get_config_value('DAILY_APPLICATION_LIMIT', 20)
        self.match_threshold = self._get_config_value('MATCH_SCORE_THRESHOLD', 70)

    def _get_config_value(self, key, default=None):
        """Read setting from class-style config or dict-like Flask config."""
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)

    def get_daily_application_count(self, target_date=None):
        """Get number of applications submitted today"""
        if target_date is None:
            target_date = date.today()

        count = JobApplication.query.filter(
            JobApplication.status == 'applied',
            db.func.date(JobApplication.application_date) == target_date
        ).count()

        return count

    def can_apply_today(self):
        """Check if we can still apply today (respects daily limit)"""
        today_count = self.get_daily_application_count()
        return today_count < self.daily_limit

    def get_remaining_applications_today(self):
        """Get remaining applications allowed today"""
        today_count = self.get_daily_application_count()
        return max(0, self.daily_limit - today_count)

    def evaluate_job(self, job_data, candidate_id):
        """
        Evaluate if candidate should apply to a job
        Returns: (decision, score, analysis)
        """
        # Extract job information
        job_description = job_data.get('description', '')
        required_skills = job_data.get('required_skills', [])
        experience_required = job_data.get('experience_required', '')

        # Calculate match score
        match_score, analysis = self.skill_matcher.calculate_match_score(
            job_description,
            required_skills,
            experience_required
        )

        # Decision logic
        decision = "apply" if match_score >= self.match_threshold else "skip"

        return {
            "decision": decision,
            "match_score": match_score,
            "analysis": analysis,
            "passes_threshold": match_score >= self.match_threshold
        }

    def _get_or_create_job_listing(self, job_data):
        """Get existing job listing by portal_job_id or create a new one."""
        portal_job_id = job_data.get('portal_job_id')
        if not portal_job_id:
            raise ValueError("portal_job_id is required to create an application")

        listing = JobListing.query.filter_by(portal_job_id=portal_job_id).first()
        if listing:
            return listing

        listing = JobListing(
            job_title=job_data.get('job_title', 'Unknown Role'),
            company=job_data.get('company', 'Unknown Company'),
            location=job_data.get('location', 'Unknown Location'),
            portal=job_data.get('portal', 'unknown'),
            portal_job_id=portal_job_id,
            description=job_data.get('description', ''),
            required_skills=job_data.get('required_skills', []),
            experience_required=job_data.get('experience_required', ''),
            salary_range=job_data.get('salary_range', ''),
            job_url=job_data.get('job_url', '')
        )
        db.session.add(listing)
        db.session.commit()
        return listing

    def create_application(self, job_data, candidate_id, match_score, analysis, status='applied'):
        """Create a job application record"""
        listing = self._get_or_create_job_listing(job_data)
        application = JobApplication(
            job_id=listing.id,
            candidate_id=candidate_id,
            match_score=match_score,
            match_analysis=analysis,
            status=status,
            application_date=datetime.utcnow(),
            resume_version='latest'
        )
        db.session.add(application)
        db.session.commit()
        return application

    def check_duplicate_application(self, portal_job_id, candidate_id):
        """Check if candidate already applied to this portal job."""
        if not portal_job_id:
            return False

        existing = JobApplication.query.join(JobListing).filter(
            JobListing.portal_job_id == portal_job_id,
            JobApplication.candidate_id == candidate_id,
            JobApplication.status.in_(['applied', 'interview_received'])
        ).first()
        return existing is not None

    def process_job_batch(self, jobs, candidate_id):
        """
        Process a batch of jobs for application
        Returns list of results
        """
        results = []
        remaining_today = self.get_remaining_applications_today()

        for job_data in jobs:
            if remaining_today <= 0:
                results.append({
                    "job": job_data,
                    "status": "skipped",
                    "reason": "Daily application limit reached"
                })
                continue

            # Check for duplicates
            if self.check_duplicate_application(job_data.get('portal_job_id'), candidate_id):
                results.append({
                    "job": job_data,
                    "status": "skipped",
                    "reason": "Already applied to this job"
                })
                continue

            # Evaluate job
            evaluation = self.evaluate_job(job_data, candidate_id)

            if evaluation["decision"] == "apply":
                # Simulate application submission
                try:
                    # In production, this would use Selenium to fill forms and submit
                    result = self._submit_application(job_data, candidate_id)

                    # Record in database
                    application = self.create_application(
                        job_data,
                        candidate_id,
                        evaluation["match_score"],
                        evaluation["analysis"],
                        status='applied'
                    )

                    remaining_today -= 1

                    results.append({
                        "job": job_data,
                        "status": "applied",
                        "match_score": evaluation["match_score"],
                        "application_id": application.id,
                        "analysis": evaluation["analysis"]
                    })
                except Exception as e:
                    results.append({
                        "job": job_data,
                        "status": "error",
                        "reason": str(e)
                    })
            else:
                results.append({
                    "job": job_data,
                    "status": "skipped",
                    "reason": f"Below match threshold ({evaluation['match_score']}%)",
                    "match_score": evaluation["match_score"],
                    "analysis": evaluation["analysis"]
                })

        return results

    def _submit_application(self, job_data, candidate_id):
        """
        Submit job application using browser automation
        This is a placeholder - actual implementation uses Selenium
        """
        # In production, this would:
        # 1. Open job application page
        # 2. Fill candidate profile
        # 3. Upload resume
        # 4. Submit application
        # 5. Handle CAPTCHA if needed

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "job_url": job_data.get('job_url')
        }

    def update_daily_stats(self, jobs_scraped=0, jobs_matched=0, jobs_applied=0):
        """Update daily application statistics"""
        today = date.today()

        stats = DailyApplicationLog.query.filter(
            DailyApplicationLog.date == today
        ).first()

        if not stats:
            stats = DailyApplicationLog(
                date=today,
                jobs_scraped=jobs_scraped,
                jobs_matched=jobs_matched,
                jobs_applied=jobs_applied
            )
            db.session.add(stats)
        else:
            stats.jobs_scraped += jobs_scraped
            stats.jobs_matched += jobs_matched
            stats.jobs_applied += jobs_applied

        db.session.commit()
        return stats


class EmailNotifier:
    """
    Send email notifications for job applications
    """

    def __init__(self, config=None):
        self.config = config or Config()

    def send_daily_summary(self, recipient_email, application_results, daily_stats):
        """
        Send daily application summary email
        """
        try:
            # Create email content
            subject = f"Daily Job Application Summary - {date.today()}"

            applied_jobs = [r for r in application_results if r['status'] == 'applied']
            skipped_jobs = [r for r in application_results if r['status'] == 'skipped']

            html_content = self._generate_email_html(applied_jobs, skipped_jobs, daily_stats)

            # Send email
            self._send_email(recipient_email, subject, html_content)

            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

    def _generate_email_html(self, applied_jobs, skipped_jobs, daily_stats):
        """Generate HTML email content"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #2c3e50; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-card {{ 
                    background: #f8f9fa; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border-left: 4px solid #3498db; 
                }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #3498db; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                .job-list {{ margin-top: 30px; }}
                .job-item {{ 
                    background: #fff; 
                    border: 1px solid #ddd; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px; 
                }}
                .job-title {{ font-weight: bold; color: #2c3e50; }}
                .job-company {{ color: #666; font-size: 14px; }}
                .match-score {{ 
                    display: inline-block; 
                    background: #27ae60; 
                    color: white; 
                    padding: 5px 10px; 
                    border-radius: 3px; 
                    margin-left: 10px;
                }}
                .match-score.low {{
                    background: #e74c3c;
                }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>AI Job Application Summary</h1>
                <p>Daily report for <strong>{date.today()}</strong></p>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value">{daily_stats.jobs_applied}</div>
                        <div class="stat-label">Applications Submitted</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{daily_stats.jobs_matched}</div>
                        <div class="stat-label">Jobs Matched</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{daily_stats.jobs_scraped}</div>
                        <div class="stat-label">Jobs Scraped</div>
                    </div>
                </div>
                
                <div class="job-list">
                    <h2>✅ Applied Jobs ({len(applied_jobs)})</h2>
        """

        for job in applied_jobs:
            match_score = job.get('match_score', 0)
            html += f"""
                    <div class="job-item">
                        <div class="job-title">
                            {job['job'].get('job_title', 'N/A')}
                            <span class="match-score">{match_score}%</span>
                        </div>
                        <div class="job-company">
                            {job['job'].get('company', 'N/A')} • {job['job'].get('location', 'N/A')}
                        </div>
                        <div style="font-size: 13px; color: #555; margin-top: 8px;">
                            {job.get('analysis', {}).get('reasoning', 'Good match')}
                        </div>
                    </div>
            """

        html += """
                    <h2>⏭️ Skipped Jobs ({len(skipped_jobs)})</h2>
        """

        for job in skipped_jobs[:5]:  # Show only first 5 skipped
            match_score = job.get('match_score', 0)
            html += f"""
                    <div class="job-item" style="opacity: 0.7;">
                        <div class="job-title">
                            {job['job'].get('job_title', 'N/A')}
                            <span class="match-score low">{match_score}%</span>
                        </div>
                        <div class="job-company">
                            {job['job'].get('company', 'N/A')} • {job['job'].get('location', 'N/A')}
                        </div>
                        <div style="font-size: 13px; color: #999;">
                            Reason: {job.get('reason', 'Below match threshold')}
                        </div>
                    </div>
            """

        html += f"""
                </div>
                
                <div class="footer">
                    <p>This is an automated report from your AI Job Application Assistant</p>
                    <p>Next run scheduled for tomorrow</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html


class NaukriAutoApplyAgent:
    """
    Selenium executor for Naukri apply flow (best-effort).
    """

    CANDIDATE_ANSWERS = {
        "name": "MD Aftab Alam", "first_name": "MD Aftab", "last_name": "Alam",
        "email": "aftab.work86@gmail.com", "phone": "8178248632", "mobile": "8178248632",
        "current_location": "Hyderabad", "city": "Hyderabad",
        "total_experience": "4", "experience_years": "4",
        "current_ctc": "14", "current_salary": "14",
        "expected_ctc": "17", "expected_salary": "17",
        "notice_period": "Immediate", "notice": "Immediate", "availability": "Immediate",
        "employed": "No", "currently_employed": "No",
        "relocate": "Yes", "relocation": "Yes", "willing_relocate": "Yes",
        "default_yes_no": "Yes",
        "preferred_locations": "Hyderabad, Noida, Gurgaon, Delhi NCR, Mumbai, Kolkata, Remote",
    }

    def __init__(self, config=None, headless=False):
        self.config = config or Config()
        self.headless = headless

    def _cfg(self, key, default=''):
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)

    def _driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,1000")
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

    def login(self, driver, email=None, password=None):
        email = email or self._cfg("NAUKRI_EMAIL", "")
        password = password or self._cfg("NAUKRI_PASSWORD", "")

        if not email or not password:
            return {
                "mode": "manual",
                "ok": False,
                "message": "NAUKRI_EMAIL/NAUKRI_PASSWORD missing. Login manually in opened browser."
            }

        driver.get("https://www.naukri.com/nlogin/login")
        wait = WebDriverWait(driver, 20)

        username_elem = None
        password_elem = None
        username_selectors = [
            (By.ID, "usernameField"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[placeholder*='Email'], input[placeholder*='email']"),
            (By.CSS_SELECTOR, "input[name='email']"),
        ]
        password_selectors = [
            (By.ID, "passwordField"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.CSS_SELECTOR, "input[name='password']"),
        ]

        for by, sel in username_selectors:
            elems = driver.find_elements(by, sel)
            if elems:
                username_elem = elems[0]
                break
        for by, sel in password_selectors:
            elems = driver.find_elements(by, sel)
            if elems:
                password_elem = elems[0]
                break

        if not username_elem or not password_elem:
            # If the login form isn't visible, try proceeding to homepage in case of preserved session.
            driver.get("https://www.naukri.com/mnjuser/homepage")
            time.sleep(3)
            if "mnjuser" in driver.current_url:
                return {"mode": "session", "ok": True, "message": "Existing session detected"}
            return {"mode": "credentials", "ok": False, "message": "Login form not found"}

        try:
            username_elem.clear()
        except Exception:
            pass
        username_elem.send_keys(email)

        try:
            password_elem.clear()
        except Exception:
            pass
        password_elem.send_keys(password)

        submit_buttons = driver.find_elements(By.XPATH, "//button[contains(@type,'submit')]")
        if submit_buttons:
            submit_buttons[0].click()
        else:
            password_elem.submit()

        time.sleep(4)
        return {"mode": "credentials", "ok": True, "message": "Login attempted"}

    # ── Popup handler helpers ──────────────────────────────────────────────────

    # ── Visual debug helper ────────────────────────────────────────────────────

    def _highlight(self, driver, element, color: str = "#fff3cd", border: str = "2px solid #f0a500"):
        """Briefly highlight an element with a coloured border so you can see it being filled."""
        try:
            driver.execute_script(
                "arguments[0].style.border = arguments[1]; "
                "arguments[0].style.backgroundColor = arguments[2];",
                element, border, color,
            )
        except Exception:
            pass

    def _identify_field_intent(self, label: str, placeholder: str, name_attr: str) -> str:
        """Map label/placeholder/name text to a CANDIDATE_ANSWERS key."""
        text = f"{label} {placeholder} {name_attr}".lower()

        if any(k in text for k in ["expected ctc", "expected salary", "expected compensation"]):
            return "expected_ctc"
        if any(k in text for k in ["current ctc", "current salary", "present ctc", "current compensation"]):
            return "current_ctc"
        if any(k in text for k in ["notice period", "notice", "joining", "availability"]):
            return "notice_period"
        if any(k in text for k in ["total experience", "years of experience", "total exp", "experience"]):
            return "total_experience"
        if any(k in text for k in ["preferred location", "preferred city", "preferred work location"]):
            return "preferred_locations"
        if any(k in text for k in ["current location", "present location", "city", "location"]):
            return "current_location"
        if any(k in text for k in ["relocat", "willing to relocat", "open to relocat"]):
            return "relocate"
        if any(k in text for k in ["currently employed", "are you employed", "employment status", "currently working"]):
            return "employed"
        if any(k in text for k in ["phone", "mobile", "contact number"]):
            return "phone"
        if any(k in text for k in ["email", "e-mail"]):
            return "email"
        if any(k in text for k in ["last name", "surname"]):
            return "last_name"
        if any(k in text for k in ["first name"]):
            return "first_name"
        if any(k in text for k in ["full name", "name"]):
            return "name"
        return "unknown"

    def _fill_field(self, driver, element, value: str, field_type: str) -> bool:
        """Fill a single form element with the given value (with visual highlight)."""
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            time.sleep(0.3)
            self._highlight(driver, element)   # yellow flash so you see it
            time.sleep(0.4)

            if field_type in ("text", "textarea", "email", "number", "tel", "search"):
                element.clear()
                # Type character-by-character so it's readable on screen
                for ch in value:
                    element.send_keys(ch)
                    time.sleep(0.04)
                self._highlight(driver, element, color="#d4edda", border="2px solid #28a745")  # green = done
                time.sleep(0.3)
                return True

            elif field_type == "select":
                sel = Select(element)
                value_lower = value.lower()
                for opt in sel.options:
                    if value_lower in opt.text.lower():
                        sel.select_by_visible_text(opt.text)
                        self._highlight(driver, element, color="#d4edda", border="2px solid #28a745")
                        time.sleep(0.4)
                        return True
                for opt in sel.options:
                    opt_val = (opt.get_attribute("value") or "").lower()
                    if value_lower in opt_val:
                        sel.select_by_value(opt.get_attribute("value"))
                        self._highlight(driver, element, color="#d4edda", border="2px solid #28a745")
                        time.sleep(0.4)
                        return True
                return False

            elif field_type in ("radio", "checkbox"):
                self._highlight(driver, element, color="#cce5ff", border="2px solid #004085")
                time.sleep(0.3)
                if not element.is_selected():
                    try:
                        element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", element)
                return True

        except Exception:
            pass
        return False

    def _generate_ai_answer(self, question_text: str, job_data: dict) -> str:
        """Use Ollama to generate an answer to an open-ended screening question."""
        base_url = self._cfg("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        model    = self._cfg("OLLAMA_MODEL", "llama3.2:3b")
        timeout  = getattr(Config, "OLLAMA_ANSWER_TIMEOUT", 20)

        system_prompt = (
            "You are MD Aftab Alam, a 4-year experienced Python/AWS/AI engineer "
            "applying for jobs on Naukri. Answer job application screening questions "
            "concisely and professionally in 1-3 sentences. Do not include any preamble."
        )
        job_context = (
            f"Job: {job_data.get('job_title', 'Software Engineer')} "
            f"at {job_data.get('company', 'a company')}. "
            f"Skills required: {', '.join(job_data.get('required_skills', []))}"
        )
        user_prompt = f"{job_context}\n\nScreening question: {question_text}"

        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": user_prompt, "system": system_prompt, "stream": False},
                timeout=timeout,
            )
            if resp.ok:
                return resp.json().get("response", "").strip()
        except Exception:
            pass

        return (
            "I am a passionate Python developer with 4 years of experience building "
            "scalable backend systems and AI solutions. I am confident my skills align "
            "well with the requirements of this role and I look forward to contributing."
        )

    def _detect_popup(self, driver):
        """Detect application popup/modal after Apply click. Returns WebElement or None."""
        log = logging.getLogger(__name__)

        popup_selectors = [
            "div[class*='apply-popup']",
            "div[class*='applyPopup']",
            "div[role='dialog']",
            "div[class*='chatbot_Questions']",
            "div[class*='bot-container']",
            "div.modal-content",
            "div[class*='modal']",
        ]

        for selector in popup_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.size.get("height", 0) > 50:
                        log.info(f"Popup detected via selector: {selector}")
                        return el
            except Exception:
                continue

        popup_wait = getattr(Config, "POPUP_WAIT_SECONDS", 5)
        try:
            el = WebDriverWait(driver, popup_wait).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div[role='dialog']"))
            )
            log.info("Popup detected via WebDriverWait for div[role='dialog']")
            return el
        except Exception:
            pass

        return None

    def _fill_radio_groups(self, driver, popup, job_data: dict, log) -> None:
        """Find and fill all radio groups inside the popup."""
        try:
            radios = popup.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            groups: dict = {}
            for r in radios:
                name = r.get_attribute("name") or ""
                if name not in groups:
                    groups[name] = []
                groups[name].append(r)

            for name, radio_list in groups.items():
                context_text = name
                try:
                    parent = radio_list[0].find_element(By.XPATH, "./ancestor::div[3]")
                    context_text = parent.text + " " + name
                except Exception:
                    pass

                intent = self._identify_field_intent(context_text, "", name)
                target_value = self.CANDIDATE_ANSWERS.get(intent, "Yes").lower()

                clicked = False
                for radio in radio_list:
                    try:
                        label_text = ""
                        try:
                            rid = radio.get_attribute("id")
                            if rid:
                                label_el = popup.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                label_text = label_el.text.strip().lower()
                        except Exception:
                            pass

                        if not label_text:
                            try:
                                label_text = radio.find_element(
                                    By.XPATH, "./following-sibling::label"
                                ).text.strip().lower()
                            except Exception:
                                pass

                        if target_value in label_text or label_text in target_value:
                            driver.execute_script(
                                "arguments[0].scrollIntoView({block:'center'});", radio
                            )
                            self._highlight(driver, radio, color="#cce5ff", border="2px solid #004085")
                            time.sleep(0.4)
                            try:
                                radio.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", radio)
                            log.info(f"Radio group '{name}': selected '{label_text}' (intent={intent})")
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked and radio_list:
                    try:
                        driver.execute_script("arguments[0].click();", radio_list[0])
                        log.info(f"Radio group '{name}': fallback — clicked first option")
                    except Exception:
                        pass

        except Exception as exc:
            log.warning(f"_fill_radio_groups error: {exc}")

    def _click_submit_button(self, driver, popup, log) -> bool:
        """Attempt to click the submit/apply button inside popup then full page."""
        submit_xpaths = [
            ".//button[@type='submit']",
            ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
            ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'done')]",
            ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
            ".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send application')]",
            ".//button[contains(@class, 'btn-primary')]",
            ".//button[contains(@class, 'sendMail')]",
            ".//button[contains(@class, 'bot-btn')]",
        ]

        for context in [popup, driver]:
            for xp in submit_xpaths:
                try:
                    buttons = context.find_elements(By.XPATH, xp)
                    for btn in buttons:
                        try:
                            if btn.is_displayed() and btn.is_enabled():
                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});", btn
                                )
                                self._highlight(driver, btn, color="#f8d7da", border="3px solid #dc3545")
                                time.sleep(0.6)   # pause so you can see the submit button
                                try:
                                    btn.click()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", btn)
                                log.info(f"Submit button clicked via: {xp}")
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue

        return False

    def _handle_application_popup(self, driver, job_data: dict) -> str:
        """Detect popup, fill all fields, and click Submit. Returns a status string."""
        log = logging.getLogger(__name__)

        popup = self._detect_popup(driver)
        if popup is None:
            log.info("No application popup detected.")
            return "applied_click"

        time.sleep(1)  # Wait for fields to render

        # ── Fill labelled fields ───────────────────────────────────────────────
        try:
            labels = popup.find_elements(By.TAG_NAME, "label")
            for label in labels:
                try:
                    label_text = label.text.strip()
                    if not label_text:
                        continue

                    field_el = None
                    for_attr = label.get_attribute("for")
                    if for_attr:
                        try:
                            field_el = popup.find_element(By.ID, for_attr)
                        except Exception:
                            pass

                    if field_el is None:
                        try:
                            field_el = label.find_element(
                                By.XPATH,
                                "./following-sibling::input | ./following-sibling::textarea | ./following-sibling::select"
                            )
                        except Exception:
                            pass

                    if field_el is None:
                        try:
                            field_el = label.find_element(
                                By.XPATH,
                                "..//input | ..//textarea | ..//select"
                            )
                        except Exception:
                            pass

                    if field_el is None:
                        continue

                    tag        = field_el.tag_name.lower()
                    field_type = (field_el.get_attribute("type") or tag).lower()

                    if field_type in ("radio", "checkbox"):
                        continue  # Handled by _fill_radio_groups

                    placeholder = field_el.get_attribute("placeholder") or ""
                    name_attr   = field_el.get_attribute("name") or ""

                    intent = self._identify_field_intent(label_text, placeholder, name_attr)
                    log.info(f"Field: label='{label_text}' intent={intent} type={field_type}")

                    if intent != "unknown":
                        value = self.CANDIDATE_ANSWERS.get(intent, "")
                        if value:
                            self._fill_field(driver, field_el, value, field_type)
                    elif field_type in ("text", "textarea") and label_text:
                        answer = self._generate_ai_answer(label_text, job_data)
                        self._fill_field(driver, field_el, answer, field_type)

                except Exception as exc:
                    log.warning(f"Field fill error: {exc}")

        except Exception as exc:
            log.warning(f"Label scanning error: {exc}")

        # ── Fill radio groups ──────────────────────────────────────────────────
        self._fill_radio_groups(driver, popup, job_data, log)

        # ── Click submit ───────────────────────────────────────────────────────
        time.sleep(0.5)
        if self._click_submit_button(driver, popup, log):
            time.sleep(2)
            return "applied_submitted"

        return "popup_submit_failed"

    def apply_to_job_url(self, driver, job_url, dry_run=False, job_data=None):
        driver.get(job_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        if dry_run:
            return {"status": "dry_run", "job_url": job_url}

        apply_candidates = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
        ]

        apply_clicked = False
        for xp in apply_candidates:
            buttons = driver.find_elements(By.XPATH, xp)
            for btn in buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(2)
                        apply_clicked = True
                        break
                except Exception:
                    continue
            if apply_clicked:
                break

        if not apply_clicked:
            return {"status": "apply_button_not_found", "job_url": job_url}

        try:
            popup_status = self._handle_application_popup(driver, job_data or {})
            return {"status": popup_status, "job_url": job_url}
        except Exception as exc:
            logging.getLogger(__name__).error(f"Popup handler exception: {exc}", exc_info=True)
            return {"status": "applied_click", "job_url": job_url, "popup_error": str(exc)}

    def batch_apply(self, job_urls, email=None, password=None, dry_run=False):
        driver = self._driver()
        try:
            login_status = self.login(driver, email=email, password=password)
            results = []
            for url in job_urls:
                try:
                    results.append(self.apply_to_job_url(driver, url, dry_run=dry_run))
                except Exception as exc:
                    results.append({"status": "error", "job_url": url, "error": str(exc)})
            return {"login": login_status, "results": results}
        finally:
            driver.quit()

    def _send_email(self, recipient_email, subject, html_content):
        """Send email via SMTP"""
        try:
            sender_email = self.config.SENDER_EMAIL
            sender_password = self.config.SENDER_PASSWORD

            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = sender_email
            message['To'] = recipient_email

            # Attach HTML content
            message.attach(MIMEText(html_content, 'html'))

            # Send email
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(message)

            print(f"Email sent successfully to {recipient_email}")
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            raise
