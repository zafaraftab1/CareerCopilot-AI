import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from application_engine import NaukriAutoApplyAgent
from job_scraper import NaukriLiveScraper

PROFILE_PATH = Path("data/naukri_profile_scrape.json")
LOG_PATH = Path("data/naukri_daily_apply_log.json")
RESULT_PATH = Path("data/naukri_apply_result.json")

DAILY_LIMIT = int(os.getenv("NAUKRI_DAILY_LIMIT", "30"))
PER_SEARCH_LIMIT = int(os.getenv("NAUKRI_PER_SEARCH_LIMIT", "20"))
HEADLESS = os.getenv("NAUKRI_HEADLESS", "true").lower() == "true"

ROLES = [
    "Python GenAI Developer",
    "Gen AI Engineer",
    "Python Developer",
    "Backend Developer",
]


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def parse_locations(profile):
    raw = profile.get("preferred_work_location", "")
    out = []
    for part in re.split(r",", raw):
        p = part.strip()
        if not p:
            continue
        p = p.replace("/", " ").strip()
        if p.lower() in {"remote", "india"}:
            continue
        if p not in out:
            out.append(p)
    if not out:
        out = ["Hyderabad", "Mumbai", "Noida", "Gurugram", "Kolkata", "Delhi NCR"]
    return out


def tokenize_skill(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def score_job(job, skills, locations):
    title = (job.get("job_title") or "").lower()
    desc = (job.get("description") or "").lower()
    req = " ".join(job.get("required_skills") or []).lower()
    loc = (job.get("location") or "").lower()
    blob = f"{title} {desc} {req}"

    score = 0
    matches = []

    for s in skills:
        t = tokenize_skill(s)
        if not t:
            continue
        if t in blob:
            score += 4
            matches.append(s)

    priority = ["python", "genai", "generative ai", "llm", "rag", "langchain", "fastapi", "django", "aws", "backend"]
    for kw in priority:
        if kw in blob:
            score += 2

    if any(l.lower() in loc for l in locations):
        score += 3

    exp = (job.get("experience_required") or "").lower()
    if any(x in exp for x in ["3", "4", "5"]):
        score += 1

    return score, sorted(set(matches))


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    profile_obj = load_json(PROFILE_PATH, {})
    profile = profile_obj.get("profile", {})

    if not profile:
        raise SystemExit("Profile data missing. Run profile scrape first.")

    skills = profile.get("skills", [])
    locations = parse_locations(profile)

    log = load_json(LOG_PATH, {"days": {}})
    day = log["days"].get(today, {"attempted": [], "applied": []})
    attempted_today = set(day.get("attempted", []))
    applied_today = set(day.get("applied", []))

    remaining = max(0, DAILY_LIMIT - len(applied_today))
    if remaining == 0:
        result = {
            "date": today,
            "daily_limit": DAILY_LIMIT,
            "already_applied_today": len(applied_today),
            "remaining_capacity": 0,
            "searched_jobs": 0,
            "shortlisted": 0,
            "applied_now": 0,
            "message": "Daily limit reached",
        }
        save_json(RESULT_PATH, result)
        print(json.dumps(result, indent=2))
        return

    scraper = NaukriLiveScraper(headless=HEADLESS)
    seen = set()
    jobs = []

    for role in ROLES:
        for loc in locations:
            try:
                found = scraper.search_jobs(role=role, location=loc, limit=PER_SEARCH_LIMIT)
            except Exception:
                found = []

            for job in found:
                url = (job.get("job_url") or "").strip()
                if not url:
                    continue
                if url in seen:
                    continue
                seen.add(url)
                jobs.append(job)

    scored = []
    for job in jobs:
        url = job.get("job_url")
        if not url or url in attempted_today:
            continue
        score, matched = score_job(job, skills, locations)
        if score < 10:
            continue
        scored.append((score, matched, job))

    scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = scored[:remaining]

    job_urls = [j[2]["job_url"] for j in shortlist]

    apply_result = {"login": {"ok": False, "message": "No jobs shortlisted"}, "results": []}
    if job_urls:
        agent = NaukriAutoApplyAgent(config={}, headless=HEADLESS)
        apply_result = agent.batch_apply(
            job_urls=job_urls,
            email=os.getenv("NAUKRI_EMAIL", ""),
            password=os.getenv("NAUKRI_PASSWORD", ""),
            dry_run=False,
        )

    results = apply_result.get("results", [])
    applied_now_urls = [r.get("job_url") for r in results if r.get("status") == "applied_click" and r.get("job_url")]
    attempted_now_urls = [u for u in job_urls if u]

    day_attempted = sorted(set(day.get("attempted", []) + attempted_now_urls))
    day_applied = sorted(set(day.get("applied", []) + applied_now_urls))

    log["days"][today] = {
        "attempted": day_attempted,
        "applied": day_applied,
        "updated_at": int(time.time()),
    }
    save_json(LOG_PATH, log)

    result = {
        "date": today,
        "daily_limit": DAILY_LIMIT,
        "already_applied_today": len(applied_today),
        "remaining_capacity_before_run": remaining,
        "searched_jobs": len(jobs),
        "shortlisted": len(job_urls),
        "applied_now": len(applied_now_urls),
        "attempted_now": len(attempted_now_urls),
        "roles_used": ROLES,
        "locations_used": locations,
        "shortlist": [
            {
                "score": s,
                "matched_skills": m,
                "job_title": j.get("job_title"),
                "company": j.get("company"),
                "location": j.get("location"),
                "job_url": j.get("job_url"),
            }
            for s, m, j in shortlist
        ],
        "apply": apply_result,
    }
    save_json(RESULT_PATH, result)
    print(json.dumps({
        "searched_jobs": result["searched_jobs"],
        "shortlisted": result["shortlisted"],
        "attempted_now": result["attempted_now"],
        "applied_now": result["applied_now"],
        "date": today,
        "daily_total_after_run": len(day_applied),
    }, indent=2))


if __name__ == "__main__":
    main()
