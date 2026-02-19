# SETUP GUIDE - AI Job Application Automation Agent

## Overview
This guide walks you through setting up the AI Job Application Automation Agent on your system.

## Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- macOS, Linux, or Windows with WSL
- ~2GB free disk space

## Installation Steps

### 1. Navigate to Project Directory
```bash
cd /Users/zafaraftab/NaukriAutoAppplyAI
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
```

### 3. Activate Virtual Environment

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` prefix in your terminal.

### 4. Upgrade pip
```bash
pip install --upgrade pip
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- Flask & Flask-CORS - Web framework
- SQLAlchemy - Database ORM
- Selenium - Browser automation
- BeautifulSoup4 - Web scraping
- APScheduler - Task scheduling
- And more...

### 6. Configure Environment

#### Copy Example Configuration
```bash
cp .env.example .env
```

#### Edit .env File
Open `.env` in your editor and configure:

```env
# Application
FLASK_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key-generate-something-unique

# Database (default SQLite, can use PostgreSQL)
DATABASE_URL=sqlite:///job_application.db

# Email Configuration (for Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password

# Candidate Info
CANDIDATE_NAME=MD Aftab Alam
CANDIDATE_EMAIL=aftab.work86@gmail.com

# Limits
DAILY_APPLICATION_LIMIT=20
MATCH_SCORE_THRESHOLD=70
```

#### Gmail Setup for Emails
1. Enable 2-factor authentication on your Gmail account
2. Generate app password: https://myaccount.google.com/apppasswords
3. Use app password in `SENDER_PASSWORD`

### 7. Initialize Database
```bash
python3 -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

Or run the quickstart script:
```bash
python3 quickstart.py
```

### 8. Run the Application
```bash
python3 app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
 * Press CTRL+C to quit
```

### 9. Open Dashboard
Open your browser to: **http://localhost:5000**

## First Use

### 1. Dashboard Overview
- View statistics for today's applications
- See charts of applications by portal and location
- Check recent applications

### 2. Search for Jobs
1. Go to "Job Search" section
2. Filter by role, location, and minimum match score
3. Click "Search Jobs" button
4. Review matched and skipped jobs
5. Select jobs you want to apply to
6. Click "Apply to Selected Jobs"

### 3. Manage Resume
1. Go to "Resume & Profile" section
2. Upload or view your resume
3. See extracted skills from your resume
4. Update your profile information

### 4. View Applications
1. Go to "Applications" section
2. See all applications with match scores
3. Filter by status, location, or date
4. Click links to view job postings

### 5. Configure Settings
1. Go to "Settings" section
2. Set daily application limit
3. Configure email notifications
4. Select preferred locations
5. Save settings

## Using Sample Data

To test the system without real job scraping:

```python
from job_scraper import MockJobData

# Get 8 sample jobs
jobs = MockJobData.get_sample_jobs()

# Each job includes:
# - Job title, company, location
# - Portal (naukri, linkedin, monster, indeed)
# - Description with required skills
# - Experience level
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| FLASK_ENV | development | Environment (development/production) |
| DEBUG | True | Debug mode |
| DATABASE_URL | sqlite:///job_application.db | Database connection |
| DAILY_APPLICATION_LIMIT | 20 | Max applications per day |
| MATCH_SCORE_THRESHOLD | 70 | Min match score to apply |
| SMTP_SERVER | smtp.gmail.com | Email server |
| SMTP_PORT | 587 | Email port |

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution**: Virtual environment not activated or dependencies not installed
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Address already in use" port 5000
**Solution**: Port already in use, use different port
```bash
python3 app.py
# Then access: http://localhost:5001
```

Or kill the process using port 5000:
```bash
lsof -i :5000
kill -9 <PID>
```

### Issue: Database locked error
**Solution**: Delete the database and reinitialize
```bash
rm job_application.db
python3 -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Issue: Email not working
**Solution**: Check email configuration
1. Verify SMTP settings in `.env`
2. For Gmail: Enable "Less secure app access" or use app-specific password
3. Check email is correct in `CANDIDATE_EMAIL`

### Issue: Charts not showing in dashboard
**Solution**: Clear browser cache or use incognito mode
```bash
# Or in browser console:
# localStorage.clear()
```

## Running Tests

```bash
# Run unit tests
python3 -m unittest test_automation.py -v

# Run specific test
python3 -m unittest test_automation.TestSkillMatcher.test_exact_skill_match -v
```

## Database Operations

### View Database Contents
```python
from app import create_app
from models import db, JobApplication

app = create_app()
with app.app_context():
    apps = JobApplication.query.all()
    for app in apps:
        print(f"{app.job.job_title} at {app.job.company}: {app.match_score}%")
```

### Reset Database
```bash
rm job_application.db
python3 quickstart.py
```

### Backup Database
```bash
cp job_application.db job_application.db.backup
```

## Enabling Scheduler (Advanced)

To enable automatic job search and applications:

Edit `app.py` and uncomment scheduler initialization:

```python
from scheduler import create_scheduler

# In create_app function:
scheduler = create_scheduler(app)
scheduler.start()
```

This will:
- Search jobs daily at 9 AM
- Process applications at 10 AM
- Send email summary at 6 PM

## Production Deployment

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment for Production
```env
FLASK_ENV=production
DEBUG=False
DATABASE_URL=postgresql://user:password@localhost/jobbot
```

## Next Steps

1. **Customize Skills**: Edit resume knowledge base in `resume_matcher.py`
2. **Add Job Portals**: Create scrapers for additional portals
3. **Implement Selenium**: Add browser automation for real applications
4. **Extend Features**: Add cover letter generation, interview scheduling, etc.
5. **Deploy**: Set up on cloud platform (AWS, Heroku, etc.)

## Documentation

- **README.md**: Complete project documentation
- **API Reference**: See app.py for API endpoints
- **Code Comments**: All modules have detailed docstrings

## Support & Help

- Check README.md for full documentation
- Review code comments and docstrings
- Run tests to verify functionality
- Check logs in terminal for errors

## Security Notes

⚠️ **Important for Production**:
- Never commit `.env` file with real credentials
- Change `SECRET_KEY` to a strong random string
- Use HTTPS in production
- Implement authentication/authorization
- Validate all user inputs
- Use environment variables for sensitive data

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|------------|
| Python | 3.8 | 3.10+ |
| RAM | 512MB | 2GB |
| Disk | 500MB | 2GB |
| Internet | Required | High speed |

## Troubleshooting Checklist

- [ ] Python 3.8+ installed?
- [ ] Virtual environment activated?
- [ ] Dependencies installed?
- [ ] .env file created and configured?
- [ ] Database initialized?
- [ ] Port 5000 available?
- [ ] SMTP settings correct (if using email)?

## Success Indicators

✅ Dashboard loads at http://localhost:5000
✅ Can search and view jobs
✅ Can view dashboard statistics
✅ Database operations work
✅ (Optional) Emails send successfully

## Getting Help

1. Check this setup guide
2. Review README.md
3. Check error messages in terminal
4. Review code comments
5. Run tests to diagnose issues

---

**Setup completed!** You're ready to use the AI Job Application Automation Agent. 🚀

