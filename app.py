"""
Flask API for Job Application Automation
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, date
import os
import argparse
from functools import wraps

from config import config_by_name
from models import db, CandidateProfile, JobListing, JobApplication, DailyApplicationLog
from resume_matcher import SkillMatcher, CANDIDATE_RESUME
from job_scraper import MockJobData
from application_engine import ApplicationEngine, EmailNotifier

# Initialize Flask app
def create_app(config_name='development'):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_by_name.get(config_name, 'development'))

    # Initialize extensions
    db.init_app(app)
    CORS(app)

    # Create database tables
    with app.app_context():
        db.create_all()

        # Initialize default candidate profile if not exists
        candidate = CandidateProfile.query.filter_by(
            email=app.config['CANDIDATE_EMAIL']
        ).first()

        if not candidate:
            candidate = CandidateProfile(
                name=app.config['CANDIDATE_NAME'],
                email=app.config['CANDIDATE_EMAIL'],
                experience_years=4,
                skills=list(SkillMatcher().all_candidate_skills)
            )
            db.session.add(candidate)
            db.session.commit()

    # Routes
    @app.route('/')
    def index():
        """Main dashboard"""
        return render_template('dashboard.html')

    @app.route('/api/candidate-profile', methods=['GET', 'POST'])
    def candidate_profile():
        """Get or update candidate profile"""
        candidate = CandidateProfile.query.filter_by(
            email=app.config['CANDIDATE_EMAIL']
        ).first()

        if request.method == 'POST':
            data = request.get_json()
            if candidate:
                candidate.name = data.get('name', candidate.name)
                candidate.experience_years = data.get('experience_years', candidate.experience_years)
                candidate.updated_at = datetime.utcnow()
                db.session.commit()
            return jsonify(candidate.to_dict())

        return jsonify(candidate.to_dict() if candidate else {})

    @app.route('/api/resume-summary', methods=['GET'])
    def resume_summary():
        """Get candidate resume summary"""
        matcher = SkillMatcher()
        return jsonify(matcher.get_resume_summary())

    @app.route('/api/dashboard-stats', methods=['GET'])
    def dashboard_stats():
        """Get dashboard statistics"""
        today = date.today()

        # Get daily stats
        daily_stats = DailyApplicationLog.query.filter(
            DailyApplicationLog.date == today
        ).first()

        if not daily_stats:
            daily_stats = DailyApplicationLog(date=today)

        # Get application counts
        total_applied = JobApplication.query.filter(
            JobApplication.status == 'applied'
        ).count()

        today_applied = JobApplication.query.filter(
            JobApplication.status == 'applied',
            db.func.date(JobApplication.application_date) == today
        ).count()

        interviews = JobApplication.query.filter(
            JobApplication.status == 'interview_received'
        ).count()

        # Average match score
        avg_match = db.session.query(db.func.avg(JobApplication.match_score)).scalar() or 0

        # Remaining applications for today
        engine = ApplicationEngine(app.config)
        remaining = engine.get_remaining_applications_today()

        return jsonify({
            'today': {
                'jobs_scraped': daily_stats.jobs_scraped,
                'jobs_matched': daily_stats.jobs_matched,
                'jobs_applied': today_applied,
                'remaining_limit': remaining
            },
            'all_time': {
                'total_applied': total_applied,
                'interviews_received': interviews,
                'avg_match_score': round(avg_match, 1)
            }
        })

    @app.route('/api/applications', methods=['GET'])
    def get_applications():
        """Get all job applications with filters"""
        # Get query parameters for filters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status')
        location_filter = request.args.get('location')
        min_score = request.args.get('min_score', 0, type=float)

        # Build query
        query = JobApplication.query

        if status_filter:
            query = query.filter(JobApplication.status == status_filter)

        if location_filter:
            query = query.join(JobListing).filter(
                JobListing.location.ilike(f'%{location_filter}%')
            )

        if min_score > 0:
            query = query.filter(JobApplication.match_score >= min_score)

        # Order by most recent
        query = query.order_by(JobApplication.application_date.desc())

        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        applications = [app.to_dict() for app in paginated.items]

        return jsonify({
            'applications': applications,
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page
        })

    @app.route('/api/search-jobs', methods=['POST'])
    def search_jobs():
        """Search and evaluate jobs"""
        data = request.get_json()

        # Get mock job data (in production, this would scrape real job portals)
        all_jobs = MockJobData.get_sample_jobs()

        # Filter by location if specified
        location = data.get('location')
        if location:
            all_jobs = [j for j in all_jobs if location.lower() in j.get('location', '').lower()]

        # Filter by role if specified
        role = data.get('role')
        if role:
            all_jobs = [j for j in all_jobs if role.lower() in j.get('job_title', '').lower()]

        # Get candidate
        candidate = CandidateProfile.query.filter_by(
            email=app.config['CANDIDATE_EMAIL']
        ).first()

        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        # Evaluate each job
        engine = ApplicationEngine(app.config)
        matcher = SkillMatcher()

        evaluated_jobs = []
        jobs_matched = 0

        for job_data in all_jobs:
            evaluation = engine.evaluate_job(job_data, candidate.id)

            job_with_eval = {
                **job_data,
                'match_score': evaluation['match_score'],
                'decision': evaluation['decision'],
                'analysis': evaluation['analysis']
            }

            evaluated_jobs.append(job_with_eval)

            if evaluation['passes_threshold']:
                jobs_matched += 1

        # Update daily stats
        engine.update_daily_stats(
            jobs_scraped=len(all_jobs),
            jobs_matched=jobs_matched
        )

        return jsonify({
            'jobs': evaluated_jobs,
            'total_scraped': len(all_jobs),
            'total_matched': jobs_matched
        })

    @app.route('/api/apply-jobs', methods=['POST'])
    def apply_jobs():
        """Process and apply to matched jobs"""
        data = request.get_json()
        job_ids = data.get('job_ids', [])

        # Get candidate
        candidate = CandidateProfile.query.filter_by(
            email=app.config['CANDIDATE_EMAIL']
        ).first()

        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        # Get jobs to apply
        jobs_to_apply = []
        for job_data in MockJobData.get_sample_jobs():
            if job_data.get('portal_job_id') in job_ids:
                jobs_to_apply.append(job_data)

        # Process applications
        engine = ApplicationEngine(app.config)
        results = engine.process_job_batch(jobs_to_apply, candidate.id)

        # Count successful applications
        applied_count = len([r for r in results if r['status'] == 'applied'])

        # Update daily stats
        engine.update_daily_stats(jobs_applied=applied_count)

        # Send notification email
        daily_stats = DailyApplicationLog.query.filter(
            DailyApplicationLog.date == date.today()
        ).first()

        if daily_stats and applied_count > 0:
            notifier = EmailNotifier(app.config)
            # notifier.send_daily_summary(candidate.email, results, daily_stats)

        return jsonify({
            'results': results,
            'total_applied': applied_count,
            'total_skipped': len([r for r in results if r['status'] == 'skipped'])
        })

    @app.route('/api/location-stats', methods=['GET'])
    def location_stats():
        """Get application statistics by location"""
        stats = db.session.query(
            JobListing.location,
            db.func.count(JobApplication.id).label('count'),
            db.func.avg(JobApplication.match_score).label('avg_score')
        ).join(JobListing).group_by(JobListing.location).all()

        return jsonify([{
            'location': stat[0],
            'count': stat[1],
            'avg_score': round(stat[2], 1) if stat[2] else 0
        } for stat in stats])

    @app.route('/api/portal-stats', methods=['GET'])
    def portal_stats():
        """Get application statistics by portal"""
        stats = db.session.query(
            JobListing.portal,
            db.func.count(JobApplication.id).label('count'),
            db.func.avg(JobApplication.match_score).label('avg_score')
        ).join(JobListing).group_by(JobListing.portal).all()

        return jsonify([{
            'portal': stat[0],
            'count': stat[1],
            'avg_score': round(stat[2], 1) if stat[2] else 0
        } for stat in stats])

    @app.route('/api/match-score-distribution', methods=['GET'])
    def match_score_distribution():
        """Get distribution of match scores"""
        ranges = [
            {'min': 0, 'max': 30, 'label': '0-30%'},
            {'min': 30, 'max': 50, 'label': '30-50%'},
            {'min': 50, 'max': 70, 'label': '50-70%'},
            {'min': 70, 'max': 85, 'label': '70-85%'},
            {'min': 85, 'max': 100, 'label': '85-100%'},
        ]

        distribution = []
        for range_item in ranges:
            count = JobApplication.query.filter(
                JobApplication.match_score >= range_item['min'],
                JobApplication.match_score < range_item['max']
            ).count()
            distribution.append({
                'label': range_item['label'],
                'count': count
            })

        return jsonify(distribution)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Job Application Automation API server.')
    parser.add_argument('--host', default=os.getenv('HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', 5001)))
    parser.add_argument(
        '--debug',
        action='store_true',
        default=os.getenv('FLASK_DEBUG', '1').lower() in ('1', 'true', 'yes')
    )
    args = parser.parse_args()

    app = create_app('development')
    app.run(debug=args.debug, host=args.host, port=args.port)
