"""
Advanced scheduler for automated job applications
Can be extended for production use with APScheduler
"""

from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config
from models import db, CandidateProfile, JobListing, DailyApplicationLog
from resume_matcher import SkillMatcher
from job_scraper import JobSearchAPI
from application_engine import ApplicationEngine, EmailNotifier
import logging

logger = logging.getLogger(__name__)

class JobApplicationScheduler:
    """
    Handles scheduled job searching and application submission
    """

    def __init__(self, app=None, config=None):
        self.app = app
        self.config = config or Config()
        self.scheduler = BackgroundScheduler()
        self.job_search_api = JobSearchAPI()
        self.app_engine = ApplicationEngine(self.config)
        self.email_notifier = EmailNotifier(self.config)

    def start(self):
        """Start the scheduler"""
        if self.app:
            self.app.app_context().push()

        # Schedule job search every morning at 9 AM
        self.scheduler.add_job(
            self.daily_job_search,
            CronTrigger(hour=9, minute=0),
            id='daily_job_search',
            name='Daily job search'
        )

        # Schedule automated applications every morning at 10 AM
        self.scheduler.add_job(
            self.process_applications,
            CronTrigger(hour=10, minute=0),
            id='process_applications',
            name='Process applications'
        )

        # Schedule email summary every evening at 6 PM
        self.scheduler.add_job(
            self.send_daily_summary,
            CronTrigger(hour=18, minute=0),
            id='send_daily_summary',
            name='Send daily summary'
        )

        self.scheduler.start()
        logger.info("Job Application Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Job Application Scheduler stopped")

    def daily_job_search(self):
        """Search for jobs daily"""
        logger.info("Starting daily job search...")

        try:
            # Get candidate
            candidate = CandidateProfile.query.filter_by(
                email=self.config.CANDIDATE_EMAIL
            ).first()

            if not candidate:
                logger.error("Candidate not found")
                return

            # Search jobs
            keywords = ' '.join(self.config.PREFERRED_ROLES)
            jobs = self.job_search_api.search_jobs(
                keywords=keywords,
                locations=self.config.PREFERRED_LOCATIONS,
                portals=self.config.JOB_PORTALS
            )

            # Deduplicate
            jobs = self.job_search_api.deduplicate_jobs(jobs)

            # Save to database
            matcher = SkillMatcher()
            jobs_added = 0

            for job_data in jobs:
                # Check if job already exists
                existing = JobListing.query.filter_by(
                    portal_job_id=job_data.get('portal_job_id')
                ).first()

                if not existing:
                    job = JobListing(
                        job_title=job_data.get('job_title'),
                        company=job_data.get('company'),
                        location=job_data.get('location'),
                        portal=job_data.get('portal'),
                        portal_job_id=job_data.get('portal_job_id'),
                        description=job_data.get('description'),
                        required_skills=job_data.get('required_skills', []),
                        experience_required=job_data.get('experience_required'),
                        job_url=job_data.get('job_url')
                    )
                    db.session.add(job)
                    jobs_added += 1

            if jobs_added > 0:
                db.session.commit()

            # Update daily stats
            self.app_engine.update_daily_stats(jobs_scraped=len(jobs))

            logger.info(f"Daily job search completed. Added {jobs_added} new jobs")

        except Exception as e:
            logger.error(f"Error in daily job search: {str(e)}")

    def process_applications(self):
        """Process and apply to matching jobs"""
        logger.info("Starting application processing...")

        try:
            # Get candidate
            candidate = CandidateProfile.query.filter_by(
                email=self.config.CANDIDATE_EMAIL
            ).first()

            if not candidate:
                logger.error("Candidate not found")
                return

            # Get unapplied jobs
            from models import JobApplication
            applied_job_ids = db.session.query(JobApplication.job_id).filter(
                JobApplication.status == 'applied'
            ).all()
            applied_job_ids = [jid[0] for jid in applied_job_ids]

            eligible_jobs = JobListing.query.filter(
                ~JobListing.id.in_(applied_job_ids) if applied_job_ids else True
            ).limit(20).all()  # Limit to top 20 to avoid excessive processing

            # Evaluate and apply
            results = []
            applied_count = 0

            for job in eligible_jobs:
                # Check daily limit
                if not self.app_engine.can_apply_today():
                    logger.info("Daily application limit reached")
                    break

                # Evaluate job
                evaluation = self.app_engine.evaluate_job({
                    'description': job.description,
                    'required_skills': job.required_skills,
                    'experience_required': job.experience_required,
                    'job_url': job.job_url,
                    'portal_job_id': job.portal_job_id
                }, candidate.id)

                if evaluation['decision'] == 'apply':
                    try:
                        # Submit application
                        app = self.app_engine.create_application(
                            job,
                            candidate.id,
                            evaluation['match_score'],
                            evaluation['analysis']
                        )

                        results.append({
                            'job': job,
                            'status': 'applied',
                            'match_score': evaluation['match_score']
                        })
                        applied_count += 1

                        logger.info(f"Applied to {job.job_title} at {job.company}")
                    except Exception as e:
                        logger.error(f"Error applying to job {job.id}: {str(e)}")

            # Update daily stats
            self.app_engine.update_daily_stats(jobs_applied=applied_count)

            logger.info(f"Application processing completed. Applied to {applied_count} jobs")

        except Exception as e:
            logger.error(f"Error in application processing: {str(e)}")

    def send_daily_summary(self):
        """Send daily summary email"""
        logger.info("Sending daily summary email...")

        try:
            from datetime import date

            # Get daily stats
            daily_stats = DailyApplicationLog.query.filter(
                DailyApplicationLog.date == date.today()
            ).first()

            if not daily_stats:
                logger.info("No applications today")
                return

            # Get today's applications
            today_applications = JobListing.query.join(JobApplication).filter(
                db.func.date(JobApplication.application_date) == date.today(),
                JobApplication.status == 'applied'
            ).all()

            # Send email
            candidate = CandidateProfile.query.filter_by(
                email=self.config.CANDIDATE_EMAIL
            ).first()

            if candidate and today_applications:
                self.email_notifier.send_daily_summary(
                    candidate.email,
                    [{'job': app.to_dict(), 'status': 'applied'}
                     for app in today_applications[:10]],  # Limit to 10 for email
                    daily_stats
                )
                logger.info("Daily summary email sent")

        except Exception as e:
            logger.error(f"Error sending daily summary: {str(e)}")


def create_scheduler(app, config=None):
    """Factory function to create and configure scheduler"""
    scheduler = JobApplicationScheduler(app, config)
    return scheduler

