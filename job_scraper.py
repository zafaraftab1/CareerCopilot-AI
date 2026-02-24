"""
Job scraping and discovery from various portals
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class JobScraper:
    """
    Base class for job scraping from different portals
    """

    def __init__(self, portal_name):
        self.portal_name = portal_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_jobs(self, keywords, location, experience_level=None):
        """
        Search for jobs based on keywords and location
        Should be implemented by subclasses
        """
        raise NotImplementedError

    def parse_job_listing(self, job_html):
        """
        Parse individual job listing HTML
        Should be implemented by subclasses
        """
        raise NotImplementedError


class NaukriScraper(JobScraper):
    """
    Naukri.com job scraper
    """

    def __init__(self):
        super().__init__('naukri')
        self.base_url = 'https://www.naukri.com'
        self.search_url = 'https://www.naukri.com/search?'

    def search_jobs(self, keywords, location, experience_level=None):
        """
        Search jobs on Naukri
        Note: This is a template. Actual implementation requires handling dynamic content
        """
        params = {
            'k': keywords,
            'l': location,
            'experience': experience_level or ''
        }

        jobs = []
        try:
            # In production, use Selenium for dynamic content
            response = self.session.get(self.search_url, params=params, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Parse job listings (implementation depends on Naukri's HTML structure)
                job_cards = soup.find_all('article', class_='jobTuple')

                for card in job_cards:
                    job = self._extract_job_info(card)
                    if job:
                        job['portal'] = 'naukri'
                        jobs.append(job)
        except Exception as e:
            print(f"Error scraping Naukri: {str(e)}")

        return jobs

    def _extract_job_info(self, job_card):
        """Extract job information from Naukri job card"""
        try:
            job = {}

            # Title
            title_elem = job_card.find('a', class_='jobCardImg')
            if title_elem:
                job['title'] = title_elem.get('title', '')

            # Company
            company_elem = job_card.find('a', class_='subTitle-container')
            if company_elem:
                job['company'] = company_elem.text.strip()

            # Location
            location_elem = job_card.find('span', class_='locSpan')
            if location_elem:
                job['location'] = location_elem.text.strip()

            # Experience
            exp_elem = job_card.find('span', class_='expwdth')
            if exp_elem:
                job['experience_required'] = exp_elem.text.strip()

            # Job URL
            url_elem = job_card.find('a', class_='jobCardImg')
            if url_elem and url_elem.get('href'):
                job['url'] = self.base_url + url_elem.get('href')

            # Portal ID
            if 'url' in job:
                job['portal_job_id'] = job['url'].split('/')[-1]

            return job if job else None
        except Exception as e:
            print(f"Error extracting job info: {str(e)}")
            return None


class LinkedInScraper(JobScraper):
    """
    LinkedIn job scraper
    """

    def __init__(self):
        super().__init__('linkedin')
        self.base_url = 'https://www.linkedin.com'

    def search_jobs(self, keywords, location, experience_level=None):
        """
        Search jobs on LinkedIn
        Note: LinkedIn has anti-scraping measures. Use official API or Selenium with authentication
        """
        jobs = []
        # LinkedIn requires authentication and has strict policies
        # Implementation would use LinkedIn API or official job search
        print("LinkedIn scraping requires API access or Selenium with authentication")
        return jobs


class JobSearchAPI:
    """
    Unified job search interface that aggregates from multiple sources
    """

    def __init__(self):
        self.scrapers = {
            'naukri': NaukriScraper(),
            # 'linkedin': LinkedInScraper(),
            # Add more as needed
        }

    def search_jobs(self, keywords, locations, experience_level=None, portals=None):
        """
        Search jobs across multiple portals
        """
        all_jobs = []
        portals_to_search = portals or list(self.scrapers.keys())

        for portal in portals_to_search:
            if portal in self.scrapers:
                for location in locations:
                    try:
                        jobs = self.scrapers[portal].search_jobs(
                            keywords,
                            location,
                            experience_level
                        )
                        all_jobs.extend(jobs)
                    except Exception as e:
                        print(f"Error searching {portal} for {location}: {str(e)}")

        return all_jobs

    def deduplicate_jobs(self, jobs):
        """
        Remove duplicate job postings
        """
        seen = set()
        unique_jobs = []

        for job in jobs:
            # Create unique key based on job title, company, and location
            key = f"{job.get('title', '')}_{job.get('company', '')}_{job.get('location', '')}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        return unique_jobs


class NaukriLiveScraper:
    """
    Live scraper for Naukri using Selenium.
    """

    def __init__(self, headless=True):
        self.headless = headless

    def _build_driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,1000")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Chrome(options=options)

    def _build_search_url(self, role, location):
        role_q = quote_plus(role or "Python Developer")
        loc_q = quote_plus(location or "")
        return f"https://www.naukri.com/{role_q.replace('+', '-')}-jobs?k={role_q}&l={loc_q}"

    def _extract_cards(self, driver, limit=20):
        jobs = []
        cards = driver.find_elements(By.CSS_SELECTOR, "article.jobTuple, .srp-jobtuple-wrapper, .cust-job-tuple")
        for idx, card in enumerate(cards[:limit]):
            try:
                title_elem = None
                for sel in ["a.title", "a[title][href*='job']", ".title a"]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        title_elem = elems[0]
                        break

                company_elem = None
                for sel in [".comp-name", "a.comp-name", ".companyInfo .subTitle"]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        company_elem = elems[0]
                        break

                location_elem = None
                for sel in [".locWdth", ".location", ".loc-wrap span"]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        location_elem = elems[0]
                        break

                experience_elem = None
                for sel in [".expwdth", ".exp-wrap span", ".exp"]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        experience_elem = elems[0]
                        break

                skills_elems = card.find_elements(By.CSS_SELECTOR, ".tags-gt li, .skill-tag, .tags li")
                skills = [e.text.strip() for e in skills_elems if e.text.strip()][:15]

                title = title_elem.text.strip() if title_elem else ""
                url = title_elem.get_attribute("href") if title_elem else ""
                if not title or not url:
                    continue

                company = company_elem.text.strip() if company_elem else "Unknown Company"
                location = location_elem.text.strip() if location_elem else "Unknown"
                experience_required = experience_elem.text.strip() if experience_elem else ""

                desc = ""
                desc_elems = card.find_elements(By.CSS_SELECTOR, ".job-desc, .job-description, .job-desc-n")
                if desc_elems:
                    desc = desc_elems[0].text.strip()

                portal_job_id = f"naukri_live_{abs(hash(url))}"
                jobs.append({
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "portal": "naukri",
                    "portal_job_id": portal_job_id,
                    "description": desc,
                    "required_skills": skills,
                    "experience_required": experience_required,
                    "salary_range": "",
                    "job_url": url
                })
            except Exception:
                continue
        return jobs

    def search_jobs(self, role, location, limit=20):
        driver = self._build_driver()
        try:
            url = self._build_search_url(role, location)
            driver.get(url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)
            return self._extract_cards(driver, limit=limit)
        finally:
            driver.quit()


class MockJobData:
    """
    Mock job data for testing and demonstration
    """

    @staticmethod
    def get_sample_jobs():
        """Get sample job listings for testing"""
        return [
            {
                "job_title": "Senior Python Developer",
                "company": "TechCorp India",
                "location": "Hyderabad",
                "portal": "naukri",
                "portal_job_id": "naukri_12345",
                "description": "Looking for experienced Python developer with 4+ years of experience in backend development, REST APIs, and microservices. Experience with Django, FastAPI, and AWS is highly desirable. Must have strong understanding of databases (PostgreSQL, MySQL). Microservices architecture and Docker knowledge required.",
                "required_skills": ["Python", "Django", "FastAPI", "REST API", "PostgreSQL", "AWS", "Docker", "Microservices"],
                "experience_required": "4-6 years",
                "salary_range": "12-18 LPA",
                "job_url": "https://www.naukri.com/job-12345",
            },
            {
                "job_title": "AI/ML Engineer",
                "company": "DataSystems Ltd",
                "location": "Gurgaon",
                "portal": "linkedin",
                "portal_job_id": "linkedin_67890",
                "description": "Seeking AI Engineer with expertise in machine learning, deep learning, and natural language processing. 3-5 years of experience required. Strong Python programming skills, experience with TensorFlow, PyTorch. Data engineering and ETL pipeline experience is a plus.",
                "required_skills": ["Python", "Machine Learning", "TensorFlow", "Deep Learning", "Data Engineering", "ETL"],
                "experience_required": "3-5 years",
                "salary_range": "15-22 LPA",
                "job_url": "https://www.linkedin.com/jobs/67890",
            },
            {
                "job_title": "Backend Engineer",
                "company": "CloudNative Solutions",
                "location": "Noida",
                "portal": "naukri",
                "portal_job_id": "naukri_11111",
                "description": "Backend Engineer with expertise in Python, AWS, and microservices architecture. Must have experience with Lambda, EC2, RDS, S3. CI/CD pipelines (Jenkins, GitHub Actions) and container orchestration (Docker, Kubernetes) knowledge essential. 4+ years of experience.",
                "required_skills": ["Python", "AWS", "Lambda", "EC2", "S3", "Docker", "Kubernetes", "CI/CD"],
                "experience_required": "4+ years",
                "salary_range": "14-20 LPA",
                "job_url": "https://www.naukri.com/job-11111",
            },
            {
                "job_title": "Data Engineer",
                "company": "AnalyticsHub",
                "location": "Mumbai",
                "portal": "indeed",
                "portal_job_id": "indeed_22222",
                "description": "Data Engineer with expertise in ETL pipelines, data warehousing, and cloud platforms. Must have experience with AWS Glue, Athena, Kinesis. Python programming required. Pandas, NumPy, SQL expertise needed.",
                "required_skills": ["Python", "ETL", "AWS Glue", "Athena", "SQL", "Data Engineering", "Pandas"],
                "experience_required": "3-5 years",
                "salary_range": "13-19 LPA",
                "job_url": "https://www.indeed.com/job-22222",
            },
            {
                "job_title": "Python Developer (Django)",
                "company": "WebSystems India",
                "location": "Delhi NCR",
                "portal": "naukri",
                "portal_job_id": "naukri_33333",
                "description": "Django developer with 2+ years of experience. REST API development, PostgreSQL database design, and Docker containerization experience required. Redis and Celery knowledge is a plus.",
                "required_skills": ["Python", "Django", "REST API", "PostgreSQL", "Docker", "Redis"],
                "experience_required": "2+ years",
                "salary_range": "8-12 LPA",
                "job_url": "https://www.naukri.com/job-33333",
            },
            {
                "job_title": "AWS Solutions Architect",
                "company": "CloudExperts",
                "location": "Gurgaon",
                "portal": "linkedin",
                "portal_job_id": "linkedin_44444",
                "description": "AWS Solutions Architect with expertise in designing scalable cloud infrastructure. Must have deep knowledge of AWS services including EC2, RDS, Lambda, CloudFormation, VPC, IAM. 5+ years of AWS experience required.",
                "required_skills": ["AWS", "EC2", "RDS", "Lambda", "CloudFormation", "VPC", "IAM"],
                "experience_required": "5+ years",
                "salary_range": "18-28 LPA",
                "job_url": "https://www.linkedin.com/jobs/44444",
            },
            {
                "job_title": "DevOps Engineer",
                "company": "PipelineWorks",
                "location": "Hyderabad",
                "portal": "naukri",
                "portal_job_id": "naukri_55555",
                "description": "DevOps Engineer with expertise in CI/CD pipelines, infrastructure as code, and containerization. Must have experience with Docker, Kubernetes, Jenkins, Terraform, GitHub Actions. AWS or GCP experience preferred. 3+ years of experience.",
                "required_skills": ["Docker", "Kubernetes", "Jenkins", "Terraform", "GitHub Actions", "CI/CD", "AWS"],
                "experience_required": "3+ years",
                "salary_range": "11-16 LPA",
                "job_url": "https://www.naukri.com/job-55555",
            },
            {
                "job_title": "ReactJS Developer",
                "company": "FrontendCreative",
                "location": "Kolkata",
                "portal": "indeed",
                "portal_job_id": "indeed_66666",
                "description": "ReactJS developer with 2+ years of experience. JavaScript, HTML, CSS required. API integration with REST APIs. Experience with Redux, React Hooks, and responsive design. Nice to have: TypeScript, testing frameworks.",
                "required_skills": ["ReactJS", "JavaScript", "HTML", "CSS", "REST API"],
                "experience_required": "2+ years",
                "salary_range": "8-13 LPA",
                "job_url": "https://www.indeed.com/job-66666",
            },
        ]
