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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        wait.until(EC.presence_of_element_located((By.ID, "usernameField"))).send_keys(email)
        driver.find_element(By.ID, "passwordField").send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(@type,'submit')]").click()
        time.sleep(4)
        return {"mode": "credentials", "ok": True, "message": "Login attempted"}

    def apply_to_job_url(self, driver, job_url, dry_run=False):
        driver.get(job_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        if dry_run:
            return {"status": "dry_run", "job_url": job_url}

        apply_candidates = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
        ]

        for xp in apply_candidates:
            buttons = driver.find_elements(By.XPATH, xp)
            for btn in buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(2)
                        return {"status": "applied_click", "job_url": job_url}
                except Exception:
                    continue

        return {"status": "apply_button_not_found", "job_url": job_url}

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
