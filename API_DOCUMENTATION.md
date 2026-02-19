# API Documentation - AI Job Application Automation Agent

## Base URL
```
http://localhost:5000/api
```

## Authentication
Currently no authentication required. Implement JWT/OAuth2 for production.

---

## Endpoints

### Dashboard Statistics

#### GET `/api/dashboard-stats`
Get dashboard statistics and counters.

**Response:**
```json
{
  "today": {
    "jobs_scraped": 15,
    "jobs_matched": 8,
    "jobs_applied": 5,
    "remaining_limit": 15
  },
  "all_time": {
    "total_applied": 42,
    "interviews_received": 2,
    "avg_match_score": 73.5
  }
}
```

---

### Candidate Profile

#### GET `/api/candidate-profile`
Get candidate profile information.

**Response:**
```json
{
  "id": 1,
  "name": "MD Aftab Alam",
  "email": "aftab.work86@gmail.com",
  "experience_years": 4,
  "skills": ["Python", "Django", "AWS", "..."],
  "created_at": "2024-01-01T10:00:00"
}
```

#### POST `/api/candidate-profile`
Update candidate profile.

**Request Body:**
```json
{
  "name": "MD Aftab Alam",
  "experience_years": 4
}
```

**Response:** Updated candidate profile (same as GET)

---

### Resume

#### GET `/api/resume-summary`
Get candidate resume summary with all skills.

**Response:**
```json
{
  "name": "MD Aftab Alam",
  "email": "aftab.work86@gmail.com",
  "experience_years": 4,
  "summary": "Experienced Python Developer...",
  "primary_skills": {
    "programming_languages": ["Python", "JavaScript"],
    "web_frameworks": ["Django", "FastAPI", "Flask"],
    "databases": ["PostgreSQL", "MySQL"],
    "aws_services": ["Lambda", "EC2", "S3", "..."],
    "devops_tools": ["Docker", "Kubernetes", "..."],
    "data_tools": ["Pandas", "NumPy"],
    "frontend": ["ReactJS"],
    "apis_protocols": ["REST APIs", "JWT", "OAuth2"],
    "message_queues": ["Celery", "Redis"]
  },
  "specializations": ["Data Engineering", "ETL Pipelines", "..."],
  "ai_ml_knowledge": {
    "experience": true,
    "projects": ["Log Classification", "Anomaly Detection"],
    "frameworks": ["Scikit-learn", "TensorFlow"]
  }
}
```

---

### Job Search

#### POST `/api/search-jobs`
Search and evaluate jobs from all portals.

**Request Body:**
```json
{
  "role": "Python Developer",
  "location": "Hyderabad"
}
```

**Response:**
```json
{
  "jobs": [
    {
      "portal_job_id": "naukri_12345",
      "job_title": "Senior Python Developer",
      "company": "TechCorp",
      "location": "Hyderabad",
      "portal": "naukri",
      "match_score": 85.0,
      "decision": "apply",
      "analysis": {
        "matched_skills": [
          {"skill": "Python", "match_percentage": 100},
          {"skill": "Django", "match_percentage": 100}
        ],
        "missing_skills": [
          {"skill": "Kubernetes", "match_percentage": 45}
        ],
        "candidate_advantages": [
          "Strong AWS expertise",
          "Microservices experience"
        ],
        "reasoning": "Matched 8/10 required skills..."
      }
    }
  ],
  "total_scraped": 25,
  "total_matched": 12
}
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| role | string | Job role to search (optional) |
| location | string | Location to search (optional) |

---

### Applications

#### GET `/api/applications`
Get all job applications with pagination and filters.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page |
| status | string | - | Filter by status (applied/skipped/interview_received) |
| location | string | - | Filter by location |
| min_score | float | 0 | Minimum match score |

**Response:**
```json
{
  "applications": [
    {
      "id": 1,
      "job_id": 1,
      "candidate_id": 1,
      "match_score": 85.0,
      "match_analysis": {
        "matched_skills": [...],
        "missing_skills": [...]
      },
      "status": "applied",
      "application_date": "2024-01-15T10:00:00",
      "resume_version": "latest",
      "job": {
        "id": 1,
        "job_title": "Python Developer",
        "company": "TechCorp",
        "location": "Hyderabad",
        "portal": "naukri"
      }
    }
  ],
  "total": 42,
  "pages": 3,
  "current_page": 1
}
```

#### POST `/api/apply-jobs`
Apply to selected jobs.

**Request Body:**
```json
{
  "job_ids": [
    "naukri_12345",
    "linkedin_67890",
    "indeed_11111"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "job": { /* job object */ },
      "status": "applied",
      "match_score": 85.0,
      "application_id": 1,
      "analysis": { /* analysis object */ }
    },
    {
      "job": { /* job object */ },
      "status": "skipped",
      "reason": "Below match threshold (65%)",
      "match_score": 65.0
    }
  ],
  "total_applied": 2,
  "total_skipped": 1
}
```

---

### Statistics

#### GET `/api/location-stats`
Get application statistics grouped by location.

**Response:**
```json
[
  {
    "location": "Hyderabad",
    "count": 15,
    "avg_score": 75.5
  },
  {
    "location": "Mumbai",
    "count": 12,
    "avg_score": 72.3
  }
]
```

#### GET `/api/portal-stats`
Get application statistics grouped by portal.

**Response:**
```json
[
  {
    "portal": "naukri",
    "count": 20,
    "avg_score": 76.2
  },
  {
    "portal": "linkedin",
    "count": 15,
    "avg_score": 74.8
  }
]
```

#### GET `/api/match-score-distribution`
Get distribution of match scores.

**Response:**
```json
[
  {
    "label": "0-30%",
    "count": 2
  },
  {
    "label": "30-50%",
    "count": 5
  },
  {
    "label": "50-70%",
    "count": 8
  },
  {
    "label": "70-85%",
    "count": 18
  },
  {
    "label": "85-100%",
    "count": 12
  }
]
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource not found |
| 500 | Server Error - Internal error |

---

## Example Usage

### Using cURL

```bash
# Get dashboard stats
curl http://localhost:5000/api/dashboard-stats

# Get resume summary
curl http://localhost:5000/api/resume-summary

# Search jobs
curl -X POST http://localhost:5000/api/search-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Python Developer",
    "location": "Hyderabad"
  }'

# Get all applications
curl "http://localhost:5000/api/applications?page=1&status=applied"

# Apply to jobs
curl -X POST http://localhost:5000/api/apply-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_ids": ["naukri_12345", "linkedin_67890"]
  }'
```

### Using Python Requests

```python
import requests

API_BASE = "http://localhost:5000/api"

# Get stats
response = requests.get(f"{API_BASE}/dashboard-stats")
print(response.json())

# Search jobs
response = requests.post(
    f"{API_BASE}/search-jobs",
    json={
        "role": "Python Developer",
        "location": "Hyderabad"
    }
)
jobs = response.json()

# Apply to jobs
selected_jobs = [job['portal_job_id'] for job in jobs['jobs'][:5]]
response = requests.post(
    f"{API_BASE}/apply-jobs",
    json={"job_ids": selected_jobs}
)
result = response.json()
print(f"Applied to {result['total_applied']} jobs")
```

### Using JavaScript Fetch

```javascript
const API_BASE = "http://localhost:5000/api";

// Get dashboard stats
fetch(`${API_BASE}/dashboard-stats`)
  .then(r => r.json())
  .then(data => console.log(data));

// Search jobs
fetch(`${API_BASE}/search-jobs`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    role: 'Python Developer',
    location: 'Hyderabad'
  })
})
.then(r => r.json())
.then(data => console.log(`Found ${data.jobs.length} jobs`));

// Apply to jobs
fetch(`${API_BASE}/apply-jobs`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    job_ids: ['naukri_12345', 'linkedin_67890']
  })
})
.then(r => r.json())
.then(data => console.log(`Applied to ${data.total_applied} jobs`));
```

---

## Error Handling

All error responses follow this format:

```json
{
  "error": "Error message",
  "status": 400,
  "timestamp": "2024-01-15T10:00:00"
}
```

**Common Errors:**

```json
{
  "error": "Candidate not found",
  "status": 404
}
```

```json
{
  "error": "Invalid job ID",
  "status": 400
}
```

---

## Rate Limiting

- No rate limiting in development
- Implement rate limiting in production:
  - 100 requests per minute per IP
  - 1000 requests per hour per IP

---

## Pagination

Most list endpoints support pagination:

```
GET /api/applications?page=2&per_page=50
```

**Response includes:**
- `total` - Total items
- `pages` - Total pages
- `current_page` - Current page number
- Items array

---

## WebSocket Events (Optional Enhancement)

For real-time updates, add WebSocket support:

```javascript
const ws = new WebSocket('ws://localhost:5000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'job_applied') {
    console.log(`Applied to: ${data.job_title}`);
  }
};
```

---

## Versioning

Current API version: `v1`

Future endpoint pattern: `/api/v2/...`

---

## Changelog

### v1.0.0 (Current)
- Initial API implementation
- Dashboard statistics
- Job search and evaluation
- Application tracking
- Resume management

---

**Last Updated**: February 2024

