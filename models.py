"""
Database models for job application tracking
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class CandidateProfile(db.Model):
    """Candidate profile model"""
    __tablename__ = 'candidate_profile'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    experience_years = db.Column(db.Integer, default=4)
    resume_path = db.Column(db.String(255))
    skills = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'experience_years': self.experience_years,
            'skills': self.skills,
            'created_at': self.created_at.isoformat(),
        }

class JobListing(db.Model):
    """Job listing model"""
    __tablename__ = 'job_listings'

    id = db.Column(db.Integer, primary_key=True)
    job_title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    portal = db.Column(db.String(50), nullable=False)  # naukri, linkedin, monster, indeed
    portal_job_id = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    required_skills = db.Column(db.JSON, default=list)
    experience_required = db.Column(db.String(100))
    salary_range = db.Column(db.String(100))
    job_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'job_title': self.job_title,
            'company': self.company,
            'location': self.location,
            'portal': self.portal,
            'description': self.description,
            'required_skills': self.required_skills,
            'experience_required': self.experience_required,
            'salary_range': self.salary_range,
            'job_url': self.job_url,
            'created_at': self.created_at.isoformat(),
        }

class JobApplication(db.Model):
    """Job application tracking model"""
    __tablename__ = 'job_applications'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_listings.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate_profile.id'), nullable=False)
    match_score = db.Column(db.Float, default=0.0)
    match_analysis = db.Column(db.JSON, default=dict)  # matched_skills, missing_skills, reasoning
    status = db.Column(db.String(50), default='applied')  # applied, skipped, rejected, interview_received
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    resume_version = db.Column(db.String(100))  # track which resume version was used
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = db.relationship('JobListing', backref='applications')
    candidate = db.relationship('CandidateProfile', backref='applications')

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'candidate_id': self.candidate_id,
            'match_score': self.match_score,
            'match_analysis': self.match_analysis,
            'status': self.status,
            'application_date': self.application_date.isoformat(),
            'resume_version': self.resume_version,
            'notes': self.notes,
            'job': self.job.to_dict() if self.job else None,
        }

class DailyApplicationLog(db.Model):
    """Daily application statistics"""
    __tablename__ = 'daily_application_logs'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow, unique=True)
    jobs_scraped = db.Column(db.Integer, default=0)
    jobs_matched = db.Column(db.Integer, default=0)
    jobs_applied = db.Column(db.Integer, default=0)
    interviews_received = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'jobs_scraped': self.jobs_scraped,
            'jobs_matched': self.jobs_matched,
            'jobs_applied': self.jobs_applied,
            'interviews_received': self.interviews_received,
        }

