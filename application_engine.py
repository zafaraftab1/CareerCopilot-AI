"""
Application automation engine for job applications
"""
from datetime import datetime, date
from models import db, JobApplication, DailyApplicationLog
from resume_matcher import SkillMatcher
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

class ApplicationEngine:
    """
    Handles job application automation and tracking
    """

    def __init__(self, config=None):
        self.config = config or Config()
        self.skill_matcher = SkillMatcher()
        self.daily_limit = self.config.DAILY_APPLICATION_LIMIT
        self.match_threshold = self.config.MATCH_SCORE_THRESHOLD

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

    def create_application(self, job, candidate_id, match_score, analysis, status='applied'):
        """Create a job application record"""
        application = JobApplication(
            job_id=job.id,
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

    def check_duplicate_application(self, job_id, candidate_id):
        """Check if candidate already applied to this job"""
        existing = JobApplication.query.filter(
            JobApplication.job_id == job_id,
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
            if self.check_duplicate_application(job_data.get('id'), candidate_id):
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

