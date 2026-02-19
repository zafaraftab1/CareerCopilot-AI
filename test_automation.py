"""
Unit tests for Job Application Automation Agent
"""

import unittest
from datetime import datetime
from app import create_app
from models import db, CandidateProfile, JobListing, JobApplication
from resume_matcher import SkillMatcher
from job_scraper import MockJobData
from application_engine import ApplicationEngine

class TestSkillMatcher(unittest.TestCase):
    """Test skill matching algorithm"""

    def setUp(self):
        self.matcher = SkillMatcher()

    def test_exact_skill_match(self):
        """Test exact skill matching"""
        score, analysis = self.matcher.calculate_match_score(
            job_description="Looking for Python developer with Django and REST API experience",
            required_skills=["Python", "Django", "REST API"]
        )
        self.assertGreaterEqual(score, 70)
        self.assertTrue(len(analysis['matched_skills']) > 0)

    def test_skill_similarity(self):
        """Test fuzzy skill matching"""
        similarity = self.matcher._skill_similarity("Python", self.matcher.all_candidate_skills)
        self.assertEqual(similarity, 100)

    def test_missing_skills(self):
        """Test detection of missing skills"""
        score, analysis = self.matcher.calculate_match_score(
            job_description="Java developer needed with Spring Boot",
            required_skills=["Java", "Spring Boot"]
        )
        self.assertLess(score, 70)
        self.assertTrue(len(analysis['missing_skills']) > 0)

    def test_aws_bonus(self):
        """Test AWS specialization bonus"""
        score1, _ = self.matcher.calculate_match_score(
            job_description="Backend engineer with Python and AWS expertise",
            required_skills=["Python", "AWS", "Lambda", "EC2"]
        )
        self.assertGreater(score1, 80)

    def test_ai_ml_match(self):
        """Test AI/ML project recognition"""
        score, analysis = self.matcher.calculate_match_score(
            job_description="AI Engineer with machine learning and Python",
            required_skills=["Python", "Machine Learning", "AI"]
        )
        self.assertGreater(score, 70)
        self.assertTrue(any('AI' in adv or 'ML' in adv for adv in analysis['candidate_advantages']))


class TestJobScraper(unittest.TestCase):
    """Test job scraping functionality"""

    def test_mock_jobs_available(self):
        """Test mock job data"""
        jobs = MockJobData.get_sample_jobs()
        self.assertGreater(len(jobs), 0)

        # Check job structure
        for job in jobs:
            self.assertIn('job_title', job)
            self.assertIn('company', job)
            self.assertIn('location', job)
            self.assertIn('portal', job)


class TestApplicationEngine(unittest.TestCase):
    """Test application engine"""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test candidate
        self.candidate = CandidateProfile(
            name="Test Candidate",
            email="test@example.com",
            experience_years=4,
            skills=["Python", "Django", "AWS"]
        )
        db.session.add(self.candidate)
        db.session.commit()

        self.engine = ApplicationEngine(self.app.config)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_match_score_calculation(self):
        """Test match score calculation"""
        job_data = {
            'description': "Python developer with Django",
            'required_skills': ["Python", "Django"],
            'experience_required': "4 years"
        }

        result = self.engine.evaluate_job(job_data, self.candidate.id)
        self.assertIn('decision', result)
        self.assertIn('match_score', result)
        self.assertGreater(result['match_score'], 50)

    def test_daily_limit_check(self):
        """Test daily application limit"""
        # Create applications for today
        for i in range(20):
            job = JobListing(
                job_title=f"Job {i}",
                company=f"Company {i}",
                location="Hyderabad",
                portal="test",
                portal_job_id=f"job_{i}",
                description="Test"
            )
            db.session.add(job)

        db.session.commit()

        # Apply to 20 jobs
        from datetime import datetime
        for i in range(20):
            job = JobListing.query.filter_by(portal_job_id=f"job_{i}").first()
            app = JobApplication(
                job_id=job.id,
                candidate_id=self.candidate.id,
                match_score=75,
                match_analysis={},
                status='applied',
                application_date=datetime.utcnow()
            )
            db.session.add(app)

        db.session.commit()

        # Check limit
        can_apply = self.engine.can_apply_today()
        self.assertFalse(can_apply)

    def test_duplicate_check(self):
        """Test duplicate application prevention"""
        # Create a job
        job = JobListing(
            job_title="Test Job",
            company="Test Company",
            location="Hyderabad",
            portal="test",
            portal_job_id="test_job_1",
            description="Test"
        )
        db.session.add(job)
        db.session.commit()

        # Create application
        app = JobApplication(
            job_id=job.id,
            candidate_id=self.candidate.id,
            match_score=75,
            match_analysis={},
            status='applied'
        )
        db.session.add(app)
        db.session.commit()

        # Check duplicate
        is_duplicate = self.engine.check_duplicate_application(job.id, self.candidate.id)
        self.assertTrue(is_duplicate)


class TestDatabase(unittest.TestCase):
    """Test database operations"""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_candidate_creation(self):
        """Test candidate profile creation"""
        candidate = CandidateProfile(
            name="MD Aftab Alam",
            email="aftab@example.com",
            experience_years=4,
            skills=["Python", "Django"]
        )
        db.session.add(candidate)
        db.session.commit()

        retrieved = CandidateProfile.query.filter_by(email="aftab@example.com").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "MD Aftab Alam")

    def test_job_listing_creation(self):
        """Test job listing creation"""
        job = JobListing(
            job_title="Python Developer",
            company="Tech Corp",
            location="Hyderabad",
            portal="naukri",
            portal_job_id="naukri_123",
            description="Senior Python developer",
            required_skills=["Python", "Django"],
            experience_required="4+ years"
        )
        db.session.add(job)
        db.session.commit()

        retrieved = JobListing.query.filter_by(portal_job_id="naukri_123").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_title, "Python Developer")


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()

