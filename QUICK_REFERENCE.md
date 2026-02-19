# QUICK REFERENCE GUIDE

## 🚀 Get Started in 5 Minutes

### 1. Setup (Terminal)
```bash
cd /Users/zafaraftab/NaukriAutoAppplyAI
source .venv/bin/activate  # or: pip install -r requirements.txt first
python app.py
```

### 2. Open Dashboard
```
http://localhost:5000
```

### 3. Features to Try
- **Search Jobs**: Go to "Job Search" tab, filter, and search
- **View Stats**: Check "Dashboard" for real-time statistics
- **Check Skills**: View "Resume" to see extracted skills
- **Configure**: Adjust settings in "Settings" tab

---

## 📋 Important Directories & Files

```
/Users/zafaraftab/NaukriAutoAppplyAI/
├── app.py                    ← Run this to start
├── requirements.txt          ← Dependencies
├── .env.example             ← Copy to .env and configure
├── models.py                ← Database definitions
├── resume_matcher.py        ← Skill matching logic
├── job_scraper.py          ← Job data sources
├── application_engine.py    ← Application workflow
├── templates/dashboard.html ← Frontend UI
├── static/css/dashboard.css ← Styling
└── static/js/dashboard.js   ← Interactivity
```

---

## 🎛️ Configuration

### Edit `.env` File
```env
CANDIDATE_NAME=MD Aftab Alam
CANDIDATE_EMAIL=aftab.work86@gmail.com
DAILY_APPLICATION_LIMIT=20
MATCH_SCORE_THRESHOLD=70

# Gmail for notifications (optional)
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
```

---

## 📊 Dashboard Sections

### Dashboard
- View statistics for today
- See application charts
- Recent applications

### Job Search
- Filter by role & location
- Set minimum match score
- Select & batch apply

### Applications
- View all applications
- Filter by status/location
- Track match scores

### Resume
- Upload resume
- See extracted skills
- Update profile

### Settings
- Configure limits
- Email preferences
- Location preferences

---

## 💻 API Examples

### Get Dashboard Stats
```bash
curl http://localhost:5000/api/dashboard-stats
```

### Search Jobs
```bash
curl -X POST http://localhost:5000/api/search-jobs \
  -H "Content-Type: application/json" \
  -d '{"role":"Python Developer","location":"Hyderabad"}'
```

### Apply to Jobs
```bash
curl -X POST http://localhost:5000/api/apply-jobs \
  -H "Content-Type: application/json" \
  -d '{"job_ids":["naukri_12345"]}'
```

---

## 🐛 Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| Port 5000 in use | Kill: `lsof -i :5000 \| grep LISTEN \| awk '{print $2}' \| xargs kill -9` |
| Module not found | Activate venv: `source .venv/bin/activate` |
| Database error | Reset: `rm job_application.db && python quickstart.py` |
| No jobs found | Check filter settings and job data |
| Email not working | Verify SMTP settings in .env |

---

## 🧪 Testing

```bash
# Run all tests
python -m unittest test_automation.py -v

# Run specific test
python -m unittest test_automation.TestSkillMatcher -v
```

---

## 📈 Key Metrics

- **Match Score**: 0-100% (70+ to apply)
- **Daily Limit**: 20 applications/day
- **Duplicate Check**: Prevents duplicate applications
- **Success Rate**: Based on match score accuracy

---

## 🔧 Development Tips

### Add a New Job Portal
1. Create scraper in `job_scraper.py`
2. Register in `JobSearchAPI.scrapers`
3. Test with mock data

### Extend Skill Matcher
1. Edit `CANDIDATE_RESUME` in `resume_matcher.py`
2. Add skills to categories
3. Update skill keywords

### Customize Dashboard
1. Edit `templates/dashboard.html` for layout
2. Update `static/css/dashboard.css` for styles
3. Modify `static/js/dashboard.js` for behavior

---

## 📞 Documentation

- **README.md** - Full project overview
- **SETUP_GUIDE.md** - Detailed installation
- **API_DOCUMENTATION.md** - API reference
- **PROJECT_SUMMARY.md** - Architecture & features

---

## 🎯 Job Application Workflow

```
1. Search jobs on portals
   ↓
2. Extract required skills
   ↓
3. Compare with your resume
   ↓
4. Calculate match score
   ↓
5. If score >= 70% → APPLY
   If score < 70% → SKIP
   ↓
6. Record in database
   ↓
7. Send email notification
```

---

## 💡 Pro Tips

1. **Update Resume**: Edit `resume_matcher.py` to add new skills
2. **Track Progress**: Check dashboard for real-time updates
3. **Filter Jobs**: Use role/location filters to narrow search
4. **Batch Apply**: Select multiple jobs and apply at once
5. **Check Emails**: Enable notifications for summary emails
6. **Monitor Scores**: Review match scores before applying

---

## 🚀 Next Steps

1. **Install**: Follow SETUP_GUIDE.md
2. **Configure**: Edit .env file
3. **Explore**: Try all dashboard features
4. **Search**: Run first job search
5. **Apply**: Batch apply to matched jobs
6. **Track**: Monitor applications
7. **Extend**: Add custom features

---

## 📱 Responsive Design

Dashboard works on:
- ✅ Desktop (1920+px)
- ✅ Laptop (1024+px)
- ✅ Tablet (768+px)
- ✅ Mobile (480+px)

---

## 🔐 Security

- ✅ Never commit .env with credentials
- ✅ Use app-specific passwords for Gmail
- ✅ All inputs validated
- ✅ SQL injection protected
- ✅ Environment-based configuration

---

## 📊 Sample Skills

Your profile includes expertise in:

```
Backend:    Python, Django, FastAPI, Flask
Cloud:      AWS (Lambda, EC2, S3, RDS, etc.)
DevOps:     Docker, Kubernetes, Jenkins, Terraform
Data:       Pandas, NumPy, ETL, Data Engineering
AI/ML:      Machine Learning, Anomaly Detection
Frontend:   ReactJS, JavaScript
Databases:  PostgreSQL, MySQL
APIs:       REST, JWT, OAuth2
```

---

## ✨ Features Highlight

✅ **Smart Matching** - 70%+ threshold for quality applications  
✅ **Batch Processing** - Apply to 20 jobs per day  
✅ **Progress Tracking** - See all applications in dashboard  
✅ **Email Notifications** - Daily summary emails  
✅ **Modern UI** - Responsive & beautiful dashboard  
✅ **Full API** - 14 RESTful endpoints  
✅ **Well Documented** - Complete guides & examples  

---

## 🎓 Learning Resources

- **Skill Matching**: See `resume_matcher.py` for algorithm details
- **Database**: Review `models.py` for schema
- **API**: Check `app.py` for endpoint implementations
- **Frontend**: Study `dashboard.html/css/js` for UI patterns

---

## 📞 Support

Stuck? Check:
1. SETUP_GUIDE.md (installation issues)
2. API_DOCUMENTATION.md (API usage)
3. README.md (features)
4. Code comments (implementation)

---

## 🎉 You're All Set!

Everything is ready to go. Start by:
```bash
python app.py
```

Then open: http://localhost:5000

Enjoy automated job hunting! 🚀

---

**Version**: 1.0.0  
**Last Updated**: February 18, 2026

