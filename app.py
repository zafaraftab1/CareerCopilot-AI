"""
Flask API for Job Application Automation
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, date
import os
import argparse
import re
import requests
import subprocess

from config import config_by_name
from models import db, CandidateProfile, JobListing, JobApplication, DailyApplicationLog
from resume_matcher import SkillMatcher, CANDIDATE_RESUME
from job_scraper import MockJobData, NaukriLiveScraper
from application_engine import ApplicationEngine, EmailNotifier, NaukriAutoApplyAgent
from rag_service import RagService

# Initialize Flask app
def create_app(config_name='development'):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_by_name.get(config_name, 'development'))
    app.config.setdefault('AI_COPILOT_SETTINGS', {
        'auto_apply_enabled': False,
        'auto_answer_enabled': True,
        'min_match_score': app.config['MATCH_SCORE_THRESHOLD'],
        'max_daily_auto_apply': app.config['DAILY_APPLICATION_LIMIT'],
        'answer_style': 'professional',
        'ollama_enabled': True,
        'ollama_model': app.config.get('OLLAMA_MODEL', 'llama3.2:3b'),
        'ollama_base_url': app.config.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'),
        'last_autopilot_run': None,
        'last_autopilot_summary': None
    })
    app.config.setdefault('AUTOMATION_SETTINGS', {
        'use_live_naukri_scraper': True,
        'naukri_headless': True,
        'auto_apply_dry_run': True,
    })

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

    def _extract_first_int(text):
        match = re.search(r'(\d+)', text or "")
        return int(match.group(1)) if match else None

    def _upsert_jobs(jobs):
        created = 0
        for job in jobs:
            portal_job_id = job.get('portal_job_id')
            if not portal_job_id:
                continue
            existing = JobListing.query.filter_by(portal_job_id=portal_job_id).first()
            if existing:
                existing.job_title = job.get('job_title', existing.job_title)
                existing.company = job.get('company', existing.company)
                existing.location = job.get('location', existing.location)
                existing.description = job.get('description', existing.description)
                existing.required_skills = job.get('required_skills', existing.required_skills)
                existing.experience_required = job.get('experience_required', existing.experience_required)
                existing.salary_range = job.get('salary_range', existing.salary_range)
                existing.job_url = job.get('job_url', existing.job_url)
                continue

            db.session.add(JobListing(
                job_title=job.get('job_title', 'Unknown Role'),
                company=job.get('company', 'Unknown Company'),
                location=job.get('location', 'Unknown'),
                portal=job.get('portal', 'naukri'),
                portal_job_id=portal_job_id,
                description=job.get('description', ''),
                required_skills=job.get('required_skills', []),
                experience_required=job.get('experience_required', ''),
                salary_range=job.get('salary_range', ''),
                job_url=job.get('job_url', '')
            ))
            created += 1
        db.session.commit()
        return created

    def _profile_direct_answer(question, resume_summary):
        """Deterministic answers for common form fields."""
        q = (question or "").lower()
        experience_years = int(resume_summary.get('experience_years', 0))
        preferred_locations = app.config.get('PREFERRED_LOCATIONS', [])
        top_locations = ", ".join(preferred_locations[:4]) if preferred_locations else "Open to multiple locations"

        if "year" in q and "experience" in q:
            req = _extract_first_int(q)
            if req is not None:
                return f"I have {experience_years} years of professional experience, which meets this requirement."
            return f"I have {experience_years} years of professional experience."

        if "location" in q or "relocate" in q:
            return f"My current preferred locations are: {top_locations}. I am open to relocation."

        if "python" in q and "experience" in q:
            return f"I have {experience_years} years of Python development experience in backend APIs, automation, and data workflows."

        if "notice period" in q:
            return "My notice period can be discussed based on role urgency and offer terms."

        if "current ctc" in q or "salary" in q or "expected ctc" in q:
            return "I am open to a market-aligned compensation discussion based on responsibilities and growth scope."

        return None

    def _build_ollama_messages(question, resume_summary, job_context, style, rag_context=""):
        candidate_name = resume_summary.get('name', app.config.get('CANDIDATE_NAME', 'Candidate'))
        experience_years = resume_summary.get('experience_years', 0)
        primary_skills = resume_summary.get('primary_skills', {})
        skill_list = []
        for _, values in primary_skills.items():
            if isinstance(values, list):
                skill_list.extend(values)
        skill_list = list(dict.fromkeys(skill_list))[:25]
        preferred_locations = app.config.get('PREFERRED_LOCATIONS', [])

        job_text = "No specific job context."
        if job_context:
            job_text = (
                f"Role: {job_context.get('job_title', 'N/A')}\n"
                f"Company: {job_context.get('company', 'N/A')}\n"
                f"Required skills: {', '.join(job_context.get('required_skills', [])[:10])}\n"
                f"Experience required: {job_context.get('experience_required', 'N/A')}"
            )

        system_prompt = (
            "You are a job-application assistant writing answers on behalf of the candidate.\n"
            "Rules:\n"
            "1) Never invent facts.\n"
            "2) Keep answer job-relevant and concise (2-4 sentences).\n"
            "3) If data is missing, say it briefly and stay positive.\n"
            "4) Tone style must follow requested style.\n"
            f"Requested style: {style}\n\n"
            f"Candidate name: {candidate_name}\n"
            f"Experience years: {experience_years}\n"
            f"Preferred locations: {', '.join(preferred_locations)}\n"
            f"Skills: {', '.join(skill_list)}\n\n"
            f"Job context:\n{job_text}\n\n"
            f"Retrieved context:\n{rag_context}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

    def _ask_ollama(question, style, resume_summary, job_context=None, rag_context=""):
        settings = app.config['AI_COPILOT_SETTINGS']
        if not settings.get('ollama_enabled', True):
            return None, "Ollama disabled in settings"

        base_url = (settings.get('ollama_base_url') or app.config.get('OLLAMA_BASE_URL')).rstrip('/')
        model = settings.get('ollama_model') or app.config.get('OLLAMA_MODEL', 'llama3.2:3b')
        payload = {
            "model": model,
            "messages": _build_ollama_messages(question, resume_summary, job_context, style, rag_context=rag_context),
            "stream": False,
            "options": {"temperature": 0.2}
        }

        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=45
            )
            response.raise_for_status()
            data = response.json()
            message = (data.get('message') or {}).get('content', '').strip()
            if not message:
                return None, "Empty response from Ollama"
            return message, None
        except Exception as exc:
            # Fallback to CLI mode when API daemon is not reachable.
            prompt = (
                f"{payload['messages'][0]['content']}\n\n"
                f"Question: {question}\n"
                "Answer only with final response text."
            )
            try:
                cli = subprocess.run(
                    ["ollama", "run", model, prompt],
                    capture_output=True,
                    text=True,
                    timeout=90
                )
                if cli.returncode == 0 and cli.stdout.strip():
                    return cli.stdout.strip(), None
                cli_err = cli.stderr.strip() or cli.stdout.strip() or f"ollama run exit {cli.returncode}"
                return None, f"HTTP: {exc}; CLI: {cli_err}"
            except Exception as cli_exc:
                return None, f"HTTP: {exc}; CLI: {cli_exc}"

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

    @app.route('/api/naukri/scrape-live', methods=['POST'])
    def scrape_naukri_live():
        """
        Scrape live jobs from Naukri, score them, persist, and index in vector DB.
        """
        data = request.get_json() or {}
        role = data.get('role') or 'Python Developer'
        location = data.get('location') or 'Hyderabad'
        limit = int(data.get('limit', 20))
        headless = bool(data.get('headless', app.config['AUTOMATION_SETTINGS']['naukri_headless']))

        candidate = CandidateProfile.query.filter_by(email=app.config['CANDIDATE_EMAIL']).first()
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        jobs = []
        scrape_error = None
        used_fallback = False
        try:
            scraper = NaukriLiveScraper(headless=headless)
            jobs = scraper.search_jobs(role=role, location=location, limit=limit)
        except Exception as exc:
            scrape_error = str(exc)

        # Optional fallback so pipeline stays usable even when Naukri blocks scraping.
        if not jobs:
            fallback_jobs = MockJobData.get_sample_jobs()
            jobs = [j for j in fallback_jobs if 'naukri' in (j.get('portal', '')).lower()][:limit]
            used_fallback = True

        engine = ApplicationEngine(app.config)
        evaluated_jobs = []
        matched = 0
        for job in jobs:
            evaluation = engine.evaluate_job(job, candidate.id)
            row = {**job, **evaluation}
            evaluated_jobs.append(row)
            if evaluation.get('passes_threshold'):
                matched += 1

        created = _upsert_jobs(jobs)
        rag = RagService(app.config)
        indexed = rag.index_jobs(jobs)

        return jsonify({
            'jobs': evaluated_jobs,
            'total_scraped': len(jobs),
            'total_matched': matched,
            'db_created': created,
            'rag_indexed': indexed,
            'scrape_error': scrape_error,
            'used_fallback': used_fallback
        })

    @app.route('/api/rag/reindex', methods=['POST'])
    def rag_reindex():
        """Rebuild vector index from stored job listings."""
        job_rows = JobListing.query.order_by(JobListing.created_at.desc()).limit(500).all()
        jobs = [{
            'job_title': j.job_title,
            'company': j.company,
            'location': j.location,
            'portal': j.portal,
            'portal_job_id': j.portal_job_id,
            'description': j.description or '',
            'required_skills': j.required_skills or [],
            'experience_required': j.experience_required or '',
            'salary_range': j.salary_range or '',
            'job_url': j.job_url or '',
        } for j in job_rows]
        rag = RagService(app.config)
        indexed = rag.index_jobs(jobs)
        return jsonify({'indexed': indexed})

    @app.route('/api/rag/query', methods=['POST'])
    def rag_query():
        """Retrieve top similar jobs for a free-text query."""
        data = request.get_json() or {}
        question = data.get('query') or data.get('question') or ''
        top_k = int(data.get('top_k', 5))
        if not question.strip():
            return jsonify({'error': 'query is required'}), 400

        rag = RagService(app.config)
        ranked = rag.query(question, top_k=top_k, doc_type='job')
        results = [{
            'score': round(score, 4),
            'doc': doc.to_dict()
        } for score, doc in ranked]
        return jsonify({'query': question, 'results': results})

    @app.route('/api/naukri/auto-apply', methods=['POST'])
    def naukri_auto_apply():
        """
        Auto-apply on Naukri URLs using Selenium.
        Note: Uses best-effort click flow and does not bypass CAPTCHA.
        """
        data = request.get_json() or {}
        dry_run = bool(data.get('dry_run', app.config['AUTOMATION_SETTINGS']['auto_apply_dry_run']))
        headless = bool(data.get('headless', False))

        job_urls = data.get('job_urls') or []
        job_ids = data.get('portal_job_ids') or []
        if not job_urls and job_ids:
            rows = JobListing.query.filter(JobListing.portal_job_id.in_(job_ids)).all()
            job_urls = [j.job_url for j in rows if j.job_url]

        if not job_urls:
            return jsonify({'error': 'job_urls or portal_job_ids required'}), 400

        agent = NaukriAutoApplyAgent(config=app.config, headless=headless)
        result = agent.batch_apply(
            job_urls=job_urls,
            email=data.get('email'),
            password=data.get('password'),
            dry_run=dry_run
        )
        return jsonify(result)

    @app.route('/api/pipeline/run', methods=['POST'])
    def run_full_pipeline():
        """
        Full automation pipeline:
        1) scrape naukri live
        2) evaluate and persist
        3) index in RAG
        4) auto-apply to top matches
        """
        data = request.get_json() or {}
        role = data.get('role') or 'Python Developer'
        location = data.get('location') or 'Hyderabad'
        limit = int(data.get('limit', 20))
        min_score = int(data.get('min_score', app.config['MATCH_SCORE_THRESHOLD']))
        max_apply = int(data.get('max_apply', 5))
        dry_run = bool(data.get('dry_run', True))

        # reuse scrape endpoint logic
        candidate = CandidateProfile.query.filter_by(email=app.config['CANDIDATE_EMAIL']).first()
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        scraper = NaukriLiveScraper(headless=bool(data.get('headless', True)))
        try:
            jobs = scraper.search_jobs(role=role, location=location, limit=limit)
        except Exception:
            jobs = []
        if not jobs:
            jobs = [j for j in MockJobData.get_sample_jobs() if j.get('portal') == 'naukri'][:limit]

        engine = ApplicationEngine(app.config)
        evaluated = []
        for job in jobs:
            ev = engine.evaluate_job(job, candidate.id)
            evaluated.append({**job, **ev})

        _upsert_jobs(jobs)
        RagService(app.config).index_jobs(jobs)

        shortlist = [j for j in evaluated if j.get('match_score', 0) >= min_score]
        shortlist.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        shortlist = shortlist[:max_apply]
        urls = [j.get('job_url') for j in shortlist if j.get('job_url')]

        apply_result = NaukriAutoApplyAgent(config=app.config, headless=bool(data.get('headless', False))).batch_apply(
            job_urls=urls,
            email=data.get('email'),
            password=data.get('password'),
            dry_run=dry_run
        ) if urls else {"results": [], "login": {"ok": False, "message": "No eligible URLs"}}

        return jsonify({
            'scraped': len(jobs),
            'eligible': len(shortlist),
            'apply_attempted': len(urls),
            'apply': apply_result,
        })

    @app.route('/api/ai/settings', methods=['GET', 'POST'])
    def ai_settings():
        """Get or update AI copilot preferences."""
        settings = app.config['AI_COPILOT_SETTINGS']

        if request.method == 'POST':
            data = request.get_json() or {}
            settings['auto_apply_enabled'] = bool(data.get('auto_apply_enabled', settings['auto_apply_enabled']))
            settings['auto_answer_enabled'] = bool(data.get('auto_answer_enabled', settings['auto_answer_enabled']))
            settings['min_match_score'] = int(data.get('min_match_score', settings['min_match_score']))
            settings['max_daily_auto_apply'] = int(data.get('max_daily_auto_apply', settings['max_daily_auto_apply']))
            settings['answer_style'] = data.get('answer_style', settings['answer_style'])
            settings['ollama_enabled'] = bool(data.get('ollama_enabled', settings.get('ollama_enabled', True)))
            settings['ollama_model'] = data.get('ollama_model', settings.get('ollama_model'))
            settings['ollama_base_url'] = data.get('ollama_base_url', settings.get('ollama_base_url'))

            # Clamp values to safe ranges.
            settings['min_match_score'] = max(0, min(100, settings['min_match_score']))
            settings['max_daily_auto_apply'] = max(1, min(100, settings['max_daily_auto_apply']))

            app.config['AI_COPILOT_SETTINGS'] = settings
            return jsonify(settings)

        return jsonify(settings)

    @app.route('/api/ai/provider-status', methods=['GET'])
    def ai_provider_status():
        """Check local Ollama availability and model presence."""
        settings = app.config['AI_COPILOT_SETTINGS']
        base_url = (settings.get('ollama_base_url') or app.config.get('OLLAMA_BASE_URL')).rstrip('/')
        model = settings.get('ollama_model') or app.config.get('OLLAMA_MODEL', 'llama3.2:3b')

        try:
            response = requests.get(f"{base_url}/api/tags", timeout=10)
            response.raise_for_status()
            payload = response.json()
            models = [m.get('name', '') for m in payload.get('models', [])]
            has_model = any(name == model or name.startswith(f"{model}:") for name in models)
            return jsonify({
                "ok": True,
                "base_url": base_url,
                "configured_model": model,
                "model_available": has_model,
                "models_found": models[:20]
            })
        except Exception as exc:
            # Fallback to CLI check so users can still operate without serve daemon.
            try:
                cli = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                output = cli.stdout or ""
                model_available = model in output
                return jsonify({
                    "ok": cli.returncode == 0,
                    "mode": "cli",
                    "base_url": base_url,
                    "configured_model": model,
                    "model_available": model_available,
                    "warning": "Ollama HTTP API not reachable; using CLI fallback.",
                    "http_error": str(exc)
                }), 200 if cli.returncode == 0 else 503
            except Exception as cli_exc:
                return jsonify({
                    "ok": False,
                    "base_url": base_url,
                    "configured_model": model,
                    "error": str(exc),
                    "cli_error": str(cli_exc)
                }), 503

    @app.route('/api/ai/insights', methods=['GET'])
    def ai_insights():
        """Generate data-driven suggestions for improving application outcomes."""
        total_apps = JobApplication.query.count()
        avg_match = db.session.query(db.func.avg(JobApplication.match_score)).scalar() or 0
        interview_count = JobApplication.query.filter_by(status='interview_received').count()
        success_rate = (interview_count / total_apps * 100) if total_apps else 0

        settings = app.config['AI_COPILOT_SETTINGS']
        suggestions = []

        if avg_match < settings['min_match_score']:
            suggestions.append(
                f"Average match ({avg_match:.1f}%) is below your threshold ({settings['min_match_score']}%). Lower threshold to {max(60, settings['min_match_score'] - 5)}% or widen role filters."
            )
        if total_apps and success_rate < 8:
            suggestions.append("Interview conversion is low. Prioritize roles where Python + AWS skills are explicitly listed.")
        if total_apps == 0:
            suggestions.append("No applications submitted yet. Run AI Autopilot once to seed your pipeline.")
        if not suggestions:
            suggestions.append("Pipeline is healthy. Keep auto-apply enabled and review top 3 matches daily.")

        return jsonify({
            'total_applications': total_apps,
            'average_match_score': round(avg_match, 1),
            'interview_conversion_rate': round(success_rate, 1),
            'suggestions': suggestions
        })

    @app.route('/api/ai/answers', methods=['POST'])
    def ai_answers():
        """Generate AI-style draft answers for common screening questions."""
        data = request.get_json() or {}
        questions = data.get('questions') or [
            "Tell us about yourself.",
            "Why should we hire you for this role?",
            "Describe a project where you used Python and cloud services."
        ]
        target_job_id = data.get('portal_job_id')
        style = data.get('style') or app.config['AI_COPILOT_SETTINGS'].get('answer_style', 'professional')

        resume_summary = SkillMatcher().get_resume_summary()

        job_context = None
        if target_job_id:
            job_context = next(
                (j for j in MockJobData.get_sample_jobs() if j.get('portal_job_id') == target_job_id),
                None
            )

        rag = RagService(app.config)
        rag_hits = rag.query("python backend aws role fit", top_k=3, doc_type='job')
        rag_context = "\n\n".join([doc.content[:1200] for _, doc in rag_hits]) if rag_hits else ""

        generated = []
        provider = "profile"
        provider_errors = []
        for q in questions:
            answer = _profile_direct_answer(q, resume_summary)
            source = "profile"

            if not answer:
                ollama_answer, err = _ask_ollama(
                    q,
                    style,
                    resume_summary,
                    job_context=job_context,
                    rag_context=rag_context
                )
                if ollama_answer:
                    answer = ollama_answer
                    source = "ollama"
                    provider = "ollama"
                else:
                    provider = "fallback"
                    provider_errors.append(err)
                    answer = (
                        "I bring strong Python backend experience, cloud exposure, and a delivery-focused approach. "
                        "I can share specific project details in the next step."
                    )
                    source = "fallback"

            generated.append({'question': q, 'answer': answer, 'source': source})

        return jsonify({
            'answers': generated,
            'style': style,
            'job_context': job_context,
            'provider': provider,
            'provider_errors': provider_errors[:3]
        })

    @app.route('/api/ai/autopilot/run', methods=['POST'])
    def ai_autopilot_run():
        """Run AI autopilot: evaluate jobs and auto-apply to top matches."""
        data = request.get_json() or {}
        settings = app.config['AI_COPILOT_SETTINGS']

        if not settings.get('auto_apply_enabled', False):
            return jsonify({
                'status': 'blocked',
                'message': 'Auto-apply is disabled. Enable it in AI Copilot settings first.'
            }), 400

        role = data.get('role', '')
        location = data.get('location', '')
        min_score = int(data.get('min_match_score', settings['min_match_score']))
        max_apply = int(data.get('max_apply', settings['max_daily_auto_apply']))

        # Candidate context
        candidate = CandidateProfile.query.filter_by(
            email=app.config['CANDIDATE_EMAIL']
        ).first()
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        jobs = MockJobData.get_sample_jobs()
        if role:
            jobs = [j for j in jobs if role.lower() in j.get('job_title', '').lower()]
        if location:
            jobs = [j for j in jobs if location.lower() in j.get('location', '').lower()]

        engine = ApplicationEngine(app.config)
        evaluated = []
        for job in jobs:
            evaluation = engine.evaluate_job(job, candidate.id)
            evaluated.append({**job, **evaluation})

        eligible = [j for j in evaluated if j['match_score'] >= min_score]
        eligible.sort(key=lambda j: j['match_score'], reverse=True)

        to_apply = eligible[:max_apply]
        results = engine.process_job_batch(to_apply, candidate.id)
        applied_count = len([r for r in results if r['status'] == 'applied'])
        skipped_count = len([r for r in results if r['status'] == 'skipped'])
        engine.update_daily_stats(jobs_scraped=len(jobs), jobs_matched=len(eligible), jobs_applied=applied_count)

        summary = {
            'executed_at': datetime.utcnow().isoformat(),
            'scanned_jobs': len(jobs),
            'eligible_jobs': len(eligible),
            'attempted_applications': len(to_apply),
            'applied': applied_count,
            'skipped': skipped_count
        }
        settings['last_autopilot_run'] = summary['executed_at']
        settings['last_autopilot_summary'] = summary
        app.config['AI_COPILOT_SETTINGS'] = settings

        return jsonify({
            'status': 'ok',
            'summary': summary,
            'results': results
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
