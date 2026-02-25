"""
Naukri Auto Apply Pipeline
Searches for jobs matching your resume skills and auto-applies via Selenium.

Can run in two modes:
  1. Standalone (7 AM scheduled): python naukri_auto_apply_pipeline.py
  2. Via Flask SSE endpoint:       /api/auto-apply/stream
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

BASE_DIR   = Path(__file__).parent
LOG_DIR    = BASE_DIR / "logs"
LOG_FILE   = LOG_DIR / "auto_apply.log"
STATUS_FILE = BASE_DIR / ".auto_apply_status.json"

# Job search combinations — covers all your preferred roles × locations
SEARCH_QUERIES = [
    {"role": "Python Developer",         "location": "Hyderabad"},
    {"role": "Python Developer",         "location": "Noida"},
    {"role": "AI Engineer",              "location": "Hyderabad"},
    {"role": "Machine Learning Engineer","location": "Delhi NCR"},
    {"role": "Backend Developer Python", "location": "Gurgaon"},
    {"role": "Generative AI Engineer",   "location": "Hyderabad"},
]

DAILY_LIMIT      = 30
MATCH_THRESHOLD  = 70


class NaukriAutoApplyPipeline:

    def __init__(self, daily_limit=DAILY_LIMIT, match_threshold=MATCH_THRESHOLD,
                 headless=True, dry_run=False):
        self.daily_limit      = daily_limit
        self.match_threshold  = match_threshold
        self.headless         = headless
        self.dry_run          = dry_run
        self.email    = os.getenv("NAUKRI_EMAIL", "")
        self.password = os.getenv("NAUKRI_PASSWORD", "")

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, flask_app, emit):
        """
        Run inside a Flask app context.
        flask_app : the Flask application instance
        emit      : callable(dict) — receives progress / result events
        """
        with flask_app.app_context():
            self._run_impl(flask_app, emit)

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def _run_impl(self, app, emit):
        # Lazy imports — avoid circular dependency with app.py
        from models import db, CandidateProfile, JobListing
        from job_scraper import NaukriLiveScraper, MockJobData
        from application_engine import ApplicationEngine, NaukriAutoApplyAgent

        emit({"type": "progress", "step": "start",
              "message": "Starting Naukri Auto Apply pipeline...", "percent": 0})

        if not self.email or not self.password:
            emit({"type": "error",
                  "message": "NAUKRI_EMAIL / NAUKRI_PASSWORD not set in .env"})
            return

        # ── Step 1: Scrape ────────────────────────────────────────────────────
        all_jobs = []
        n = len(SEARCH_QUERIES)
        for i, q in enumerate(SEARCH_QUERIES):
            pct = 5 + int((i / n) * 35)
            emit({"type": "progress", "step": "scraping",
                  "message": f"Searching {q['role']} in {q['location']}...",
                  "percent": pct})
            try:
                scraper = NaukriLiveScraper(headless=self.headless)
                jobs = scraper.search_jobs(role=q["role"], location=q["location"], limit=15)
                all_jobs.extend(jobs)
                emit({"type": "log",
                      "message": f"Found {len(jobs)} jobs — {q['role']} / {q['location']}"})
            except Exception as exc:
                emit({"type": "warning",
                      "message": f"Scrape error ({q['role']} / {q['location']}): {exc}"})
                fallback = [
                    j for j in MockJobData.get_sample_jobs()
                    if q["role"].lower().split()[0] in j.get("job_title", "").lower()
                ][:5]
                all_jobs.extend(fallback)
                if fallback:
                    emit({"type": "log",
                          "message": f"Using {len(fallback)} fallback jobs"})

        # Deduplicate by portal_job_id
        seen, unique_jobs = set(), []
        for j in all_jobs:
            pid = j.get("portal_job_id")
            if pid and pid not in seen:
                seen.add(pid)
                unique_jobs.append(j)

        emit({"type": "progress", "step": "scraped",
              "message": f"Scraped {len(unique_jobs)} unique jobs total", "percent": 40})

        # Persist new jobs to DB
        for job in unique_jobs:
            pid = job.get("portal_job_id")
            if not pid:
                continue
            if not JobListing.query.filter_by(portal_job_id=pid).first():
                db.session.add(JobListing(
                    job_title=job.get("job_title", "Unknown"),
                    company=job.get("company", "Unknown"),
                    location=job.get("location", "Unknown"),
                    portal=job.get("portal", "naukri"),
                    portal_job_id=pid,
                    description=job.get("description", ""),
                    required_skills=job.get("required_skills", []),
                    experience_required=job.get("experience_required", ""),
                    salary_range=job.get("salary_range", ""),
                    job_url=job.get("job_url", ""),
                ))
        db.session.commit()

        # ── Step 2: Evaluate ──────────────────────────────────────────────────
        emit({"type": "progress", "step": "evaluating",
              "message": f"Evaluating {len(unique_jobs)} jobs against your resume...",
              "percent": 45})

        candidate = CandidateProfile.query.filter_by(
            email=app.config["CANDIDATE_EMAIL"]
        ).first()
        if not candidate:
            emit({"type": "error", "message": "Candidate profile not found in DB"})
            return

        engine = ApplicationEngine(app.config)
        remaining = engine.get_remaining_applications_today()

        if remaining <= 0:
            emit({"type": "warning",
                  "message": "Daily application limit already reached for today."})
            emit({"type": "complete",
                  "summary": {"scraped": len(unique_jobs), "matched": 0,
                               "applied": 0, "reason": "Daily limit reached"}})
            return

        matching_jobs = []
        for job in unique_jobs:
            if engine.check_duplicate_application(job.get("portal_job_id"), candidate.id):
                continue
            ev = engine.evaluate_job(job, candidate.id)
            if ev["match_score"] >= self.match_threshold:
                matching_jobs.append({**job, **ev})

        matching_jobs.sort(key=lambda j: j["match_score"], reverse=True)

        emit({"type": "progress", "step": "evaluated",
              "message": f"Found {len(matching_jobs)} jobs above {self.match_threshold}% match",
              "percent": 55, "matched_count": len(matching_jobs)})

        # ── Step 3: Apply ─────────────────────────────────────────────────────
        limit    = min(remaining, self.daily_limit, len(matching_jobs))
        to_apply = matching_jobs[:limit]

        if not to_apply:
            emit({"type": "warning", "message": "No matching jobs to apply to today."})
            emit({"type": "complete",
                  "summary": {"scraped": len(unique_jobs), "matched": len(matching_jobs),
                               "applied": 0}})
            return

        emit({"type": "progress", "step": "applying",
              "message": f"Preparing to apply to {len(to_apply)} jobs...", "percent": 58})

        applied_count     = 0
        applied_jobs_data = []

        if self.dry_run:
            emit({"type": "log",
                  "message": "DRY RUN — recording applications without submitting"})
            for job in to_apply:
                engine.create_application(
                    job, candidate.id, job["match_score"], job.get("analysis", {})
                )
                applied_count += 1
                data = {
                    "job_title":  job["job_title"],
                    "company":    job["company"],
                    "location":   job.get("location", ""),
                    "match_score": job["match_score"],
                    "status":     "applied (dry run)",
                    "job_url":    job.get("job_url", ""),
                }
                applied_jobs_data.append(data)
                emit({"type": "job_applied", "data": data})

        else:
            # Real Selenium apply
            emit({"type": "progress", "step": "login",
                  "message": "Logging into Naukri...", "percent": 60})

            agent  = NaukriAutoApplyAgent(config=app.config, headless=self.headless)
            driver = agent._driver()

            try:
                agent.login(driver, email=self.email, password=self.password)
                time.sleep(2)

                if "nlogin" in driver.current_url:
                    emit({"type": "error",
                          "message": "Login failed — check credentials in .env"})
                    return

                emit({"type": "progress", "step": "logged_in",
                      "message": "Logged in successfully!", "percent": 63})

                total = len(to_apply)
                for idx, job in enumerate(to_apply):
                    url = job.get("job_url")
                    if not url:
                        continue

                    pct = 65 + int((idx / total) * 30)
                    emit({"type": "progress", "step": "applying_job",
                          "message": f"Applying: {job['job_title']} @ {job['company']} ({idx+1}/{total})",
                          "percent": pct})

                    try:
                        result = agent.apply_to_job_url(driver, url, dry_run=False)
                        status = result.get("status", "")

                        if "applied" in status:
                            engine.create_application(
                                job, candidate.id,
                                job["match_score"], job.get("analysis", {})
                            )
                            applied_count += 1
                            data = {
                                "job_title":   job["job_title"],
                                "company":     job["company"],
                                "location":    job.get("location", ""),
                                "match_score": job["match_score"],
                                "status":      "applied",
                                "job_url":     url,
                            }
                            applied_jobs_data.append(data)
                            emit({"type": "job_applied", "data": data})
                        else:
                            emit({"type": "job_skipped", "data": {
                                "job_title": job["job_title"],
                                "company":   job["company"],
                                "reason":    status,
                            }})
                    except Exception as exc:
                        emit({"type": "warning",
                              "message": f"Error applying to {job['job_title']}: {exc}"})

                    time.sleep(1.5)   # polite delay between applications

            finally:
                driver.quit()

        # ── Finalize ──────────────────────────────────────────────────────────
        engine.update_daily_stats(
            jobs_scraped=len(unique_jobs),
            jobs_matched=len(matching_jobs),
            jobs_applied=applied_count,
        )

        summary = {
            "scraped":       len(unique_jobs),
            "matched":       len(matching_jobs),
            "applied":       applied_count,
            "applied_jobs":  applied_jobs_data,
            "timestamp":     datetime.now().isoformat(),
        }
        STATUS_FILE.write_text(json.dumps(summary, indent=2))

        emit({"type": "complete", "summary": summary})


# ── Standalone runner (for 7 AM launchd schedule) ─────────────────────────────

def _setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Naukri Auto Apply Pipeline")
    parser.add_argument("--dry-run",  action="store_true", help="Don't submit real applications")
    parser.add_argument("--visible",  action="store_true", help="Show browser window")
    parser.add_argument("--limit",    type=int, default=DAILY_LIMIT, help="Max applications")
    parser.add_argument("--threshold",type=int, default=MATCH_THRESHOLD, help="Min match %")
    args = parser.parse_args()

    _setup_logging()
    log = logging.getLogger(__name__)
    log.info("=" * 55)
    log.info("Naukri Auto Apply Pipeline — Standalone Run")
    log.info(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Limit: {args.limit}  Threshold: {args.threshold}%  DryRun: {args.dry_run}")
    log.info("=" * 55)

    # Import Flask app for DB context (lazy to avoid circular imports)
    from app import create_app
    flask_app = create_app()

    def log_emit(event):
        t   = event.get("type", "")
        msg = event.get("message", "")
        if t == "error":
            log.error(msg)
        elif t == "warning":
            log.warning(msg)
        elif t == "complete":
            s = event.get("summary", {})
            log.info(f"DONE — scraped={s.get('scraped',0)}  "
                     f"matched={s.get('matched',0)}  applied={s.get('applied',0)}")
        elif msg:
            log.info(msg)

    pipeline = NaukriAutoApplyPipeline(
        daily_limit=args.limit,
        match_threshold=args.threshold,
        headless=not args.visible,
        dry_run=args.dry_run,
    )
    pipeline.run(flask_app, log_emit)
    log.info("Pipeline finished.")


if __name__ == "__main__":
    main()
