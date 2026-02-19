"""
Resume knowledge base and skill extraction
"""
from difflib import SequenceMatcher
import json

# Candidate Resume Data (RAG Knowledge Base)
CANDIDATE_RESUME = {
    "name": "MD Aftab Alam",
    "email": "aftab.work86@gmail.com",
    "experience_years": 4,
    "summary": "Experienced Python Developer and AI Engineer with 4+ years of professional experience in backend development, data engineering, and cloud infrastructure. Skilled in building scalable microservices, ETL pipelines, and AI/ML systems.",

    "primary_skills": {
        "programming_languages": ["Python", "JavaScript"],
        "web_frameworks": ["Django", "FastAPI", "Flask"],
        "databases": ["PostgreSQL", "MySQL", "SQL"],
        "aws_services": [
            "Lambda", "EC2", "S3", "RDS", "CloudWatch",
            "Glue", "Athena", "Kinesis", "Firehose",
            "IAM", "VPC", "CloudFormation", "API Gateway",
            "CloudFront", "Aurora"
        ],
        "devops_tools": ["Docker", "Kubernetes", "Jenkins", "GitHub Actions", "Terraform"],
        "data_tools": ["Pandas", "NumPy"],
        "frontend": ["ReactJS"],
        "apis_protocols": ["REST APIs", "JWT", "OAuth2"],
        "message_queues": ["Celery", "Redis"],
        "other_tools": ["Linux", "Git", "CI/CD"]
    },

    "specializations": ["Data Engineering", "ETL Pipelines", "Microservices", "API Integrations"],

    "ai_ml_knowledge": {
        "experience": True,
        "projects": [
            "Log Classification System",
            "Anomaly Detection System"
        ],
        "frameworks": ["Scikit-learn", "TensorFlow basics", "PyTorch basics"]
    },

    "experience_summary": [
        {
            "role": "Python Developer / Backend Engineer",
            "duration": "4+ years",
            "key_responsibilities": [
                "Developed scalable REST APIs using Django and FastAPI",
                "Designed and implemented ETL pipelines using AWS Glue and Athena",
                "Built microservices architecture with Docker and Kubernetes",
                "Implemented data pipelines with Celery and Redis",
                "AWS infrastructure management and optimization"
            ]
        }
    ]
}

class SkillMatcher:
    """
    Intelligent skill matching system for job descriptions vs candidate resume
    """

    def __init__(self, candidate_resume=CANDIDATE_RESUME):
        self.candidate_resume = candidate_resume
        self.all_candidate_skills = self._extract_all_skills()

    def _extract_all_skills(self):
        """Extract all skills from candidate resume"""
        skills = set()

        # Add primary skills
        for category, skill_list in self.candidate_resume["primary_skills"].items():
            if isinstance(skill_list, list):
                skills.update([s.lower() for s in skill_list])

        # Add specializations
        skills.update([s.lower() for s in self.candidate_resume["specializations"]])

        # Add AI/ML frameworks
        if self.candidate_resume["ai_ml_knowledge"]["frameworks"]:
            skills.update([s.lower() for s in self.candidate_resume["ai_ml_knowledge"]["frameworks"]])

        return skills

    def _skill_similarity(self, job_skill, candidate_skills):
        """
        Calculate similarity between job skill and candidate skills
        Returns match percentage (0-100)
        """
        job_skill_lower = job_skill.lower().strip()

        # Exact match
        if job_skill_lower in candidate_skills:
            return 100

        # Fuzzy matching with related skills
        max_similarity = 0
        for candidate_skill in candidate_skills:
            similarity = SequenceMatcher(None, job_skill_lower, candidate_skill).ratio()
            if similarity > max_similarity:
                max_similarity = similarity

        # Keyword-based matching
        if max_similarity < 0.7:
            skill_keywords = {
                "python": ["python", "py"],
                "django": ["django"],
                "fastapi": ["fastapi", "fast-api"],
                "flask": ["flask"],
                "rest api": ["rest", "api", "restful"],
                "aws": ["aws", "amazon"],
                "docker": ["docker"],
                "kubernetes": ["kubernetes", "k8s"],
                "jenkins": ["jenkins"],
                "github actions": ["github", "actions"],
                "terraform": ["terraform"],
                "postgres": ["postgres", "postgresql"],
                "mysql": ["mysql"],
                "sql": ["sql"],
                "redis": ["redis"],
                "celery": ["celery"],
                "pandas": ["pandas"],
                "numpy": ["numpy"],
                "reactjs": ["react", "reactjs"],
                "javascript": ["javascript", "js"],
                "linux": ["linux"],
                "ci/cd": ["ci", "cd", "pipeline"],
                "microservices": ["microservices", "microservice"],
                "etl": ["etl"],
                "ai": ["ai", "artificial intelligence"],
                "machine learning": ["machine learning", "ml"],
                "ml": ["ml", "machine learning"],
                "data engineering": ["data engineering", "data engineer"],
            }

            job_keywords = set(job_skill_lower.split())

            for base_skill, keywords in skill_keywords.items():
                if any(kw in job_skill_lower for kw in keywords):
                    if base_skill in candidate_skills or any(kw in candidate_skills for kw in keywords):
                        max_similarity = max(max_similarity, 0.85)

        return int(max_similarity * 100)

    def _parse_job_description(self, job_description, required_skills=None):
        """
        Parse job description to extract required skills
        """
        if not job_description:
            return required_skills or []

        job_desc_lower = job_description.lower()
        extracted_skills = []

        # Extract from explicit required_skills if provided
        if required_skills:
            extracted_skills.extend(required_skills)

        # Common skill keywords
        skill_keywords = [
            "python", "django", "fastapi", "flask", "rest api", "restful",
            "postgresql", "postgres", "mysql", "sql",
            "aws", "lambda", "ec2", "s3", "rds", "cloudwatch", "glue", "athena",
            "kinesis", "firehose", "iam", "vpc", "cloudformation", "api gateway",
            "docker", "kubernetes", "jenkins", "github actions", "ci/cd", "terraform",
            "celery", "redis", "pandas", "numpy", "reactjs", "react", "javascript",
            "linux", "git", "microservices", "etl", "etl pipeline",
            "ai", "machine learning", "ml", "deep learning", "nlp",
            "data engineering", "data pipeline", "streaming", "api integration",
            "jwt", "oauth", "oauth2", "authentication", "backend", "api development"
        ]

        for keyword in skill_keywords:
            if keyword in job_desc_lower:
                extracted_skills.append(keyword)

        return list(set(extracted_skills))

    def calculate_match_score(self, job_description, required_skills=None, experience_required=None):
        """
        Calculate match score between job and candidate
        Returns: (score 0-100, analysis dict)
        """
        # Extract skills from job description
        job_skills = self._parse_job_description(job_description, required_skills)

        if not job_skills:
            # If no skills found, assume basic match
            return 60, {
                "matched_skills": [],
                "missing_skills": [],
                "candidate_advantages": [],
                "reasoning": "Unable to parse job description skills"
            }

        matched_skills = []
        missing_skills = []
        skill_scores = []

        # Check each job skill against candidate skills
        for skill in job_skills:
            similarity = self._skill_similarity(skill, self.all_candidate_skills)
            skill_scores.append(similarity)

            if similarity >= 70:
                matched_skills.append({
                    "skill": skill,
                    "match_percentage": similarity
                })
            else:
                missing_skills.append({
                    "skill": skill,
                    "match_percentage": similarity
                })

        # Calculate overall match score
        if skill_scores:
            average_match = sum(skill_scores) / len(skill_scores)
        else:
            average_match = 60

        # Check experience level
        experience_bonus = 0
        experience_analysis = ""
        if experience_required:
            try:
                # Extract years from experience string
                import re
                years = re.findall(r'(\d+)', experience_required)
                if years:
                    req_years = int(years[0])
                    if req_years <= 4:
                        experience_bonus = 10
                        experience_analysis = f"Experience matches well ({self.candidate_resume['experience_years']} years available)"
                    elif req_years <= 6:
                        experience_bonus = 5
                        experience_analysis = f"Slightly under experience requirement ({self.candidate_resume['experience_years']} vs {req_years} years)"
                    else:
                        experience_bonus = -10
                        experience_analysis = f"Below experience requirement ({self.candidate_resume['experience_years']} vs {req_years} years)"
            except:
                pass

        # Final score
        final_score = min(100, max(0, average_match + experience_bonus))

        # Identify candidate advantages
        candidate_advantages = []
        if "aws" in [s["skill"] for s in matched_skills]:
            candidate_advantages.append("Strong AWS expertise with multiple services")
        if any(s["skill"] in ["ai", "machine learning", "ml", "deep learning"] for s in matched_skills):
            candidate_advantages.append("AI/ML project experience")
        if "microservices" in [s["skill"] for s in matched_skills]:
            candidate_advantages.append("Microservices and distributed systems experience")
        if "data engineering" in [s["skill"] for s in matched_skills] or "etl" in [s["skill"] for s in matched_skills]:
            candidate_advantages.append("Data engineering and ETL pipeline expertise")

        analysis = {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "candidate_advantages": candidate_advantages,
            "experience_analysis": experience_analysis,
            "reasoning": f"Matched {len(matched_skills)}/{len(job_skills)} required skills. "
                        f"Average skill match: {average_match:.1f}%. "
                        f"{experience_analysis}"
        }

        return int(final_score), analysis

    def get_resume_summary(self):
        """Return candidate resume summary"""
        return {
            "name": self.candidate_resume["name"],
            "email": self.candidate_resume["email"],
            "experience_years": self.candidate_resume["experience_years"],
            "summary": self.candidate_resume["summary"],
            "primary_skills": self.candidate_resume["primary_skills"],
            "specializations": self.candidate_resume["specializations"],
            "ai_ml_knowledge": self.candidate_resume["ai_ml_knowledge"],
        }

