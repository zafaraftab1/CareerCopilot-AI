/* =================================================================
   AI Job Application Tracker - Dashboard JavaScript
   ================================================================= */

// Global state
const state = {
    currentSection: 'dashboard',
    applications: [],
    searchResults: [],
    selectedJobs: new Set(),
    charts: {},
    aiSettings: null,
    lastScrape: null
};

// ===========================
// Initialization
// ===========================

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboardData();
    loadApplications();
    loadResumeSummary();
    loadAISettings();
    loadAIInsights();
});

function initializeEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.getAttribute('data-section');
            switchSection(section);
        });
    });

    // Menu toggle (mobile)
    document.getElementById('menuToggle').addEventListener('click', () => {
        document.querySelector('.sidebar').classList.toggle('open');
    });

    // Filter controls
    document.getElementById('score-filter').addEventListener('input', (e) => {
        document.getElementById('score-value').textContent = e.target.value + '%';
    });

    document.getElementById('search-btn').addEventListener('click', searchJobs);
    document.getElementById('apply-selected-btn').addEventListener('click', applyToSelectedJobs);
    document.getElementById('live-scrape-btn')?.addEventListener('click', liveScrapeNaukriFromJobsSection);

    // Resume upload
    const uploadArea = document.getElementById('upload-area');
    const resumeFile = document.getElementById('resume-file');
    const uploadBtn = document.getElementById('upload-btn');

    uploadArea.addEventListener('click', () => resumeFile.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#667eea';
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = '#667eea';
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        handleFileUpload(e.dataTransfer.files);
    });

    resumeFile.addEventListener('change', (e) => {
        handleFileUpload(e.target.files);
    });

    uploadBtn.addEventListener('click', () => resumeFile.click());

    // Notification button
    document.querySelector('.notification-btn').addEventListener('click', () => {
        showToast('You have 3 new notifications', 'info');
    });

    // AI Copilot actions
    document.getElementById('run-autopilot-btn')?.addEventListener('click', runAIAutopilot);
    document.getElementById('generate-answers-btn')?.addEventListener('click', generateAIAutoAnswers);
    document.getElementById('ai-auto-apply-toggle')?.addEventListener('change', saveAISettings);
    document.getElementById('ai-auto-answer-toggle')?.addEventListener('change', saveAISettings);
    document.getElementById('ai-min-match-score')?.addEventListener('change', saveAISettings);
    document.getElementById('ai-max-auto-apply')?.addEventListener('change', saveAISettings);
    document.getElementById('ai-answer-style')?.addEventListener('change', saveAISettings);
    document.getElementById('ollama-enabled')?.addEventListener('change', saveAISettings);
    document.getElementById('ollama-model')?.addEventListener('change', saveAISettings);
    document.getElementById('ollama-base-url')?.addEventListener('change', saveAISettings);
    document.getElementById('test-ollama-btn')?.addEventListener('click', checkOllamaConnection);
    document.getElementById('scrape-naukri-btn')?.addEventListener('click', scrapeNaukriLive);
    document.getElementById('query-rag-btn')?.addEventListener('click', testRagQuery);
    document.getElementById('run-full-pipeline-btn')?.addEventListener('click', runFullPipeline);

    // Auto Apply section
    document.getElementById('run-auto-apply-btn')?.addEventListener('click', runAutoApplyPipeline);
    document.getElementById('stop-auto-apply-btn')?.addEventListener('click', stopAutoApplyPipeline);
}

// ===========================
// Auto Apply Pipeline
// ===========================

// Module-level state for auto-apply
const autoApplyState = {
    eventSource: null,
    appliedCount: 0,
    scrapedCount: 0,
    matchedCount: 0,
    running: false
};

async function loadLastAutoApplyStatus() {
    try {
        const res  = await fetch('/api/auto-apply/status');
        const data = await res.json();
        if (data.timestamp) {
            const ts = new Date(data.timestamp).toLocaleString();
            const el = document.getElementById('aa-last-run');
            if (el) el.textContent =
                `Last run: ${ts}  |  Applied: ${data.applied || 0}  Matched: ${data.matched || 0}  Scraped: ${data.scraped || 0}`;
        }
    } catch (_) {}
}

function runAutoApplyPipeline() {
    if (autoApplyState.running) return;

    const threshold  = document.getElementById('aa-threshold')?.value  || 70;
    const limit      = document.getElementById('aa-limit')?.value       || 30;
    const dryRun     = document.getElementById('aa-dry-run')?.checked   || false;

    // Reset UI
    autoApplyState.appliedCount = 0;
    autoApplyState.scrapedCount = 0;
    autoApplyState.matchedCount = 0;
    autoApplyState.running      = true;

    document.getElementById('run-auto-apply-btn').disabled = true;
    document.getElementById('run-auto-apply-btn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
    document.getElementById('stop-auto-apply-btn').style.display = 'inline-flex';

    const progressCard  = document.getElementById('aa-progress-card');
    const resultsArea   = document.getElementById('aa-results-area');
    const liveLog       = document.getElementById('aa-live-log');
    const tbody         = document.getElementById('aa-applied-jobs-tbody');
    const spinner       = document.getElementById('aa-spinner');

    if (progressCard) progressCard.style.display = '';
    if (resultsArea)  resultsArea.style.display  = '';
    if (liveLog)      liveLog.innerHTML = '';
    if (tbody)        tbody.innerHTML   =
        '<tr id="aa-no-jobs-row"><td colspan="4" style="text-align:center;color:#999;padding:20px;">Waiting for first application...</td></tr>';

    _aaSetProgress(0, 'Starting pipeline...');
    _aaUpdateStats(0, 0, 0);

    const url = `/api/auto-apply/stream?dry_run=${dryRun}&daily_limit=${limit}&match_threshold=${threshold}&headless=true`;
    autoApplyState.eventSource = new EventSource(url);

    autoApplyState.eventSource.onmessage = (e) => {
        let event;
        try { event = JSON.parse(e.data); } catch { return; }

        switch (event.type) {
            case 'progress':
                _aaSetProgress(event.percent || 0, event.message || '');
                if (event.matched_count != null)
                    autoApplyState.matchedCount = event.matched_count;
                _aaUpdateStats(autoApplyState.scrapedCount,
                               autoApplyState.matchedCount,
                               autoApplyState.appliedCount);
                _aaLog('info', event.message);
                break;

            case 'log':
                _aaLog('info', event.message);
                break;

            case 'scrape_result':
                autoApplyState.scrapedCount += (event.count || 0);
                _aaUpdateStats(autoApplyState.scrapedCount,
                               autoApplyState.matchedCount,
                               autoApplyState.appliedCount);
                _aaLog('info', event.message || `Found ${event.count} jobs`);
                break;

            case 'job_applied':
                autoApplyState.appliedCount++;
                _aaUpdateStats(autoApplyState.scrapedCount,
                               autoApplyState.matchedCount,
                               autoApplyState.appliedCount);
                _aaAddAppliedJobRow(event.data);
                _aaLog('success', `Applied: ${event.data.job_title} @ ${event.data.company}`);
                break;

            case 'job_skipped':
                _aaLog('warn', `Skipped: ${event.data.job_title} (${event.data.reason})`);
                break;

            case 'warning':
                _aaLog('warn', event.message);
                break;

            case 'error':
                _aaLog('error', event.message);
                _aaFinish(false, event.message);
                break;

            case 'complete':
            case 'done':
                const s = event.summary || {};
                _aaSetProgress(100, `Done! Applied to ${s.applied || 0} jobs`);
                _aaUpdateStats(s.scraped || 0, s.matched || 0, s.applied || 0);
                _aaFinish(true, `Applied to ${s.applied || 0} jobs | Matched ${s.matched || 0} | Scraped ${s.scraped || 0}`);
                loadDashboardData();
                loadApplications();
                break;

            case 'heartbeat':
                // keep-alive — no action
                break;
        }
    };

    autoApplyState.eventSource.onerror = () => {
        if (autoApplyState.running) {
            _aaLog('error', 'Connection lost or pipeline error');
            _aaFinish(false, 'Pipeline connection error');
        }
    };
}

function stopAutoApplyPipeline() {
    if (autoApplyState.eventSource) {
        autoApplyState.eventSource.close();
        autoApplyState.eventSource = null;
    }
    _aaFinish(false, 'Stopped by user');
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _aaSetProgress(pct, msg) {
    const fill = document.getElementById('aa-progress-fill');
    const msgEl = document.getElementById('aa-progress-msg');
    const pctEl = document.getElementById('aa-progress-pct');
    if (fill)  fill.style.width  = pct + '%';
    if (msgEl) msgEl.textContent = msg || '';
    if (pctEl) pctEl.textContent = Math.round(pct) + '%';
}

function _aaUpdateStats(scraped, matched, applied) {
    const s = document.getElementById('aa-stat-scraped');
    const m = document.getElementById('aa-stat-matched');
    const a = document.getElementById('aa-stat-applied');
    if (s) s.textContent = scraped;
    if (m) m.textContent = matched;
    if (a) a.textContent = applied;
}

function _aaLog(level, msg) {
    if (!msg) return;
    const log = document.getElementById('aa-live-log');
    if (!log) return;
    const icons = { info: '→', success: '✓', warn: '⚠', error: '✗' };
    const colors = { info: '#555', success: '#27ae60', warn: '#e67e22', error: '#e74c3c' };
    const line = document.createElement('div');
    line.className = 'aa-log-line';
    line.style.color = colors[level] || '#555';
    line.textContent = `${icons[level] || '·'} ${msg}`;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

function _aaAddAppliedJobRow(job) {
    const tbody = document.getElementById('aa-applied-jobs-tbody');
    if (!tbody) return;

    // Remove "waiting" placeholder
    const placeholder = document.getElementById('aa-no-jobs-row');
    if (placeholder) placeholder.remove();

    const score = Number(job.match_score || 0).toFixed(0);
    let cls = score >= 85 ? 'high' : score >= 70 ? 'medium' : 'low';

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><strong>${job.job_title}</strong></td>
        <td>${job.company}</td>
        <td><span class="match-score-badge ${cls}">${score}%</span></td>
        <td>
            <span class="status-badge applied">
                ${job.status === 'applied' ? '✓ Applied' : job.status}
            </span>
        </td>
    `;
    tbody.prepend(tr);   // newest first

    const countEl = document.getElementById('aa-applied-count');
    if (countEl) countEl.textContent = `(${autoApplyState.appliedCount})`;
}

function _aaFinish(success, message) {
    autoApplyState.running = false;
    if (autoApplyState.eventSource) {
        autoApplyState.eventSource.close();
        autoApplyState.eventSource = null;
    }

    const runBtn  = document.getElementById('run-auto-apply-btn');
    const stopBtn = document.getElementById('stop-auto-apply-btn');
    const spinner = document.getElementById('aa-spinner');

    if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="fas fa-play"></i> Run Now';
    }
    if (stopBtn) stopBtn.style.display = 'none';
    if (spinner) { spinner.classList.remove('fa-spin'); spinner.classList.remove('fa-spinner'); spinner.classList.add('fa-check-circle'); }

    showToast(message, success ? 'success' : 'error');
    loadLastAutoApplyStatus();
}

// ===========================
// Section Navigation
// ===========================

function switchSection(section) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(s => {
        s.classList.remove('active');
    });

    // Show selected section
    const sectionElement = document.getElementById(section + '-section');
    if (sectionElement) {
        sectionElement.classList.add('active');
    }

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-section') === section) {
            item.classList.add('active');
        }
    });

    // Update title
    const titles = {
        'dashboard':    'Dashboard',
        'auto-apply':   'Auto Apply',
        'jobs':         'Job Search',
        'applications': 'Applications',
        'resume':       'Resume & Profile',
        'settings':     'Settings'
    };
    document.getElementById('section-title').textContent = titles[section] || 'Dashboard';

    state.currentSection = section;

    // Load section-specific data
    if (section === 'applications') {
        loadApplications();
    }
    if (section === 'auto-apply') {
        loadLastAutoApplyStatus();
    }
}

// ===========================
// Dashboard Data
// ===========================

async function loadDashboardData() {
    try {
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();

        // Update stat cards
        document.getElementById('today-applied').textContent = data.today.jobs_applied;
        document.getElementById('daily-limit').textContent = data.today.remaining_limit + data.today.jobs_applied;
        document.getElementById('jobs-matched').textContent = data.today.jobs_matched;
        document.getElementById('jobs-scraped').textContent = data.today.jobs_scraped;
        document.getElementById('avg-match-score').textContent = data.all_time.avg_match_score.toFixed(1) + '%';

        // Update remaining counter
        document.getElementById('daily-limit').textContent = data.today.remaining_limit;

        // Load charts
        loadPortalStats();
        loadLocationStats();
        loadScoreDistribution();
        loadRecentApplications();
        loadAIInsights();
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showToast('Failed to load dashboard data', 'error');
    }
}

async function loadApplications() {
    try {
        const statusFilter = document.getElementById('status-filter')?.value || '';
        const dateFilter = document.getElementById('date-filter')?.value || '';

        const params = new URLSearchParams();
        if (statusFilter) params.append('status', statusFilter);
        if (dateFilter) params.append('date', dateFilter);

        const response = await fetch(`/api/applications?${params}`);
        const data = await response.json();

        state.applications = data.applications;
        renderApplicationsTable(data.applications);
        renderPagination(data);
    } catch (error) {
        console.error('Error loading applications:', error);
        showToast('Failed to load applications', 'error');
    }
}

async function loadResumeSummary() {
    try {
        const response = await fetch('/api/resume-summary');
        const resume = await response.json();

        // Display skills
        const skillsContainer = document.getElementById('skills-container');
        if (skillsContainer && resume.primary_skills) {
            const allSkills = [];
            for (const category in resume.primary_skills) {
                const skills = resume.primary_skills[category];
                if (Array.isArray(skills)) {
                    allSkills.push(...skills);
                }
            }

            skillsContainer.innerHTML = allSkills.map(skill =>
                `<div class="skill-item"><i class="fas fa-check"></i> ${skill}</div>`
            ).join('');
        }
    } catch (error) {
        console.error('Error loading resume:', error);
    }
}

// ===========================
// Job Search & Evaluation
// ===========================

async function searchJobs() {
    const role = document.getElementById('role-filter').value;
    const location = document.getElementById('location-filter').value;
    const minScore = document.getElementById('score-filter').value;

    const resultsContainer = document.getElementById('jobs-container');
    resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><i class="fas fa-spinner fa-spin"></i> Searching jobs...</div>';

    try {
        const response = await fetch('/api/search-jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, location })
        });

        const data = await response.json();
        state.searchResults = data.jobs;

        // Filter by minimum score
        const filtered = data.jobs.filter(j => j.match_score >= minScore);

        resultsContainer.innerHTML = '';
        if (filtered.length === 0) {
            resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p>No jobs found matching your criteria</p></div>';
            return;
        }

        filtered.forEach(job => {
            const card = createJobCard(job);
            resultsContainer.appendChild(card);
        });

        // Show apply button
        document.getElementById('apply-selected-btn').style.display =
            filtered.length > 0 ? 'flex' : 'none';

        showToast(`Found ${data.total_scraped} jobs, ${data.total_matched} matches above 70%`, 'success');
    } catch (error) {
        console.error('Error searching jobs:', error);
        showToast('Failed to search jobs', 'error');
        resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p>Error searching jobs</p></div>';
    }
}

async function liveScrapeNaukriFromJobsSection() {
    const role = document.getElementById('role-filter').value || 'Python Developer';
    const location = document.getElementById('location-filter').value || 'Hyderabad';
    const minScore = Number(document.getElementById('score-filter').value || 70);
    const resultsContainer = document.getElementById('jobs-container');
    const statusEl = document.getElementById('scrape-status-content');
    const button = document.getElementById('live-scrape-btn');

    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scraping...';
    }
    if (resultsContainer) {
        resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><i class="fas fa-spinner fa-spin"></i> Running live Naukri scrape...</div>';
    }
    if (statusEl) statusEl.textContent = 'Scraping Naukri live...';

    try {
        const response = await fetch('/api/naukri/scrape-live', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, location, limit: 20, headless: true })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Live scrape failed');

        state.searchResults = data.jobs || [];
        state.lastScrape = data;

        const filtered = (data.jobs || []).filter(j => (j.match_score || 0) >= minScore);
        resultsContainer.innerHTML = '';
        if (filtered.length === 0) {
            resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p>No live jobs matched current score filter.</p></div>';
        } else {
            filtered.forEach(job => {
                const card = createJobCard(job);
                resultsContainer.appendChild(card);
            });
        }

        document.getElementById('apply-selected-btn').style.display = filtered.length > 0 ? 'flex' : 'none';

        if (statusEl) {
            statusEl.innerHTML = `
                <strong>Last run:</strong> ${new Date().toLocaleString()}<br>
                <strong>Role:</strong> ${role} | <strong>Location:</strong> ${location}<br>
                <strong>Scraped:</strong> ${data.total_scraped || 0},
                <strong>Matched:</strong> ${data.total_matched || 0},
                <strong>Indexed:</strong> ${data.rag_indexed || 0}<br>
                <strong>Source:</strong> ${data.used_fallback ? 'Fallback (mock data)' : 'Live Naukri'}<br>
                ${data.scrape_error ? `<strong>Scrape Note:</strong> ${data.scrape_error}` : ''}
            `;
        }

        showToast(`Live scrape complete: ${data.total_scraped || 0} jobs`, 'success');
    } catch (error) {
        if (statusEl) statusEl.textContent = `Live scrape error: ${error.message}`;
        resultsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p>Live scrape failed.</p></div>';
        showToast('Live scrape failed', 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-spider"></i> Live Scrape Naukri';
        }
    }
}

function createJobCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.dataset.jobId = job.portal_job_id;

    const matchPercentage = job.match_score || 0;
    let matchClass = 'low';
    if (matchPercentage >= 85) matchClass = 'high';
    else if (matchPercentage >= 70) matchClass = 'medium';

    const analysis = job.analysis || {};
    const matchedSkills = (analysis.matched_skills || []).map(s => s.skill);
    const missingSkills = (analysis.missing_skills || []).map(s => s.skill);

    const skillsHtml = `
        <div class="job-card-skills">
            <p>Matched Skills: ${matchedSkills.length}/${matchedSkills.length + missingSkills.length}</p>
            <div class="skills-list">
                ${matchedSkills.map(s => `<span class="skill-tag matched">${s}</span>`).join('')}
                ${missingSkills.slice(0, 3).map(s => `<span class="skill-tag missing">${s}</span>`).join('')}
                ${missingSkills.length > 3 ? `<span class="skill-tag missing">+${missingSkills.length - 3} more</span>` : ''}
            </div>
        </div>
    `;

    const candidateAdvantages = (analysis.candidate_advantages || []).join('; ');
    const analysisHtml = candidateAdvantages ?
        `<div class="job-card-analysis"><strong>Your Strengths:</strong> ${candidateAdvantages}</div>` : '';

    card.innerHTML = `
        <div class="job-card-header">
            <div>
                <div class="job-card-title">${job.job_title}</div>
                <div class="job-card-company">${job.company}</div>
                <div class="job-card-location">
                    <i class="fas fa-map-marker-alt"></i>
                    ${job.location}
                </div>
            </div>
            <div class="checkbox-wrapper">
                <input type="checkbox" class="job-select-checkbox">
            </div>
        </div>

        <div class="match-score-large ${matchClass}">
            ${matchPercentage.toFixed(0)}%
        </div>

        ${skillsHtml}
        ${analysisHtml}

        <div class="job-card-footer">
            <button class="btn btn-primary job-details-btn">
                <i class="fas fa-external-link-alt"></i> View Details
            </button>
        </div>
    `;

    // Event listeners
    const checkbox = card.querySelector('.job-select-checkbox');
    checkbox.addEventListener('change', (e) => {
        const jobId = card.dataset.jobId;
        if (e.target.checked) {
            state.selectedJobs.add(jobId);
            card.classList.add('selected');
        } else {
            state.selectedJobs.delete(jobId);
            card.classList.remove('selected');
        }
    });

    card.querySelector('.job-details-btn').addEventListener('click', () => {
        window.open(job.job_url, '_blank');
    });

    return card;
}

async function applyToSelectedJobs() {
    if (state.selectedJobs.size === 0) {
        showToast('Please select at least one job to apply', 'info');
        return;
    }

    const button = document.getElementById('apply-selected-btn');
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';

    try {
        const response = await fetch('/api/apply-jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_ids: Array.from(state.selectedJobs) })
        });

        const data = await response.json();

        // Clear selection
        state.selectedJobs.clear();
        document.querySelectorAll('.job-select-checkbox').forEach(cb => {
            cb.checked = false;
        });

        showToast(`Successfully applied to ${data.total_applied} jobs!`, 'success');

        // Reload dashboard data
        loadDashboardData();
    } catch (error) {
        console.error('Error applying to jobs:', error);
        showToast('Failed to apply to jobs', 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-paper-plane"></i> Apply to Selected Jobs';
    }
}

// ===========================
// Applications Table
// ===========================

function renderApplicationsTable(applications) {
    const tbody = document.getElementById('applications-list');
    if (!tbody) return;

    if (applications.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 40px;">No applications yet</td></tr>`;
        return;
    }

    tbody.innerHTML = applications.map(app => {
        const job = app.job;
        const dateApplied = new Date(app.application_date).toLocaleDateString();
        const matchScore = app.match_score.toFixed(0);

        let matchBadgeClass = 'low';
        if (matchScore >= 85) matchBadgeClass = 'high';
        else if (matchScore >= 70) matchBadgeClass = 'medium';

        let statusBadgeClass = 'applied';
        if (app.status === 'skipped') statusBadgeClass = 'skipped';
        if (app.status === 'interview_received') statusBadgeClass = 'interview';

        return `
            <tr>
                <td><strong>${job.job_title}</strong></td>
                <td>${job.company}</td>
                <td>${job.location}</td>
                <td><span style="background: #f5f7fa; padding: 4px 8px; border-radius: 4px;">${job.portal}</span></td>
                <td><span class="match-score-badge ${matchBadgeClass}">${matchScore}%</span></td>
                <td>${dateApplied}</td>
                <td><span class="status-badge ${statusBadgeClass}">${app.status.replace('_', ' ')}</span></td>
                <td>
                    <a href="${job.job_url}" target="_blank" style="color: #667eea; text-decoration: none;">
                        <i class="fas fa-external-link-alt"></i>
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

function renderPagination(data) {
    const pagination = document.getElementById('applications-pagination');
    if (!pagination) return;

    pagination.innerHTML = '';
    for (let i = 1; i <= data.pages; i++) {
        const button = document.createElement('button');
        button.textContent = i;
        button.className = i === data.current_page ? 'active' : '';
        button.addEventListener('click', () => {
            // Load page (would require pagination in API)
            loadApplications();
        });
        pagination.appendChild(button);
    }
}

function renderApplicationsTable(applications) {
    const tbody = document.getElementById('applications-list');
    const recent = document.getElementById('recent-applications');

    const targetTbody = tbody || recent;
    if (!targetTbody) return;

    if (!applications || applications.length === 0) {
        targetTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 40px;">No applications yet</td></tr>`;
        return;
    }

    targetTbody.innerHTML = applications.slice(0, tbody ? applications.length : 5).map(app => {
        const job = app.job || {};
        const dateApplied = new Date(app.application_date).toLocaleDateString();
        const matchScore = app.match_score.toFixed(0);

        let matchBadgeClass = 'low';
        if (matchScore >= 85) matchBadgeClass = 'high';
        else if (matchScore >= 70) matchBadgeClass = 'medium';

        let statusBadgeClass = 'applied';
        if (app.status === 'skipped') statusBadgeClass = 'skipped';
        if (app.status === 'interview_received') statusBadgeClass = 'interview';

        return `
            <tr>
                <td><strong>${job.job_title || 'N/A'}</strong></td>
                <td>${job.company || 'N/A'}</td>
                <td>${job.location || 'N/A'}</td>
                <td><span style="background: #f5f7fa; padding: 4px 8px; border-radius: 4px;">${job.portal || 'N/A'}</span></td>
                <td><span class="match-score-badge ${matchBadgeClass}">${matchScore}%</span></td>
                <td>${dateApplied}</td>
                <td><span class="status-badge ${statusBadgeClass}">${app.status.replace('_', ' ')}</span></td>
                <td>
                    ${job.job_url ? `<a href="${job.job_url}" target="_blank" style="color: #667eea; text-decoration: none;"><i class="fas fa-external-link-alt"></i></a>` : 'N/A'}
                </td>
            </tr>
        `;
    }).join('');
}

// ===========================
// Load Recent Applications
// ===========================

async function loadRecentApplications() {
    try {
        const response = await fetch('/api/applications?per_page=5');
        const data = await response.json();
        renderApplicationsTable(data.applications);
    } catch (error) {
        console.error('Error loading recent applications:', error);
    }
}

// ===========================
// Charts
// ===========================

async function loadPortalStats() {
    try {
        const response = await fetch('/api/portal-stats');
        const data = await response.json();

        const ctx = document.getElementById('portal-chart');
        if (!ctx) return;

        if (state.charts.portal) {
            state.charts.portal.destroy();
        }

        state.charts.portal = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.portal),
                datasets: [{
                    data: data.map(d => d.count),
                    backgroundColor: ['#667eea', '#764ba2', '#3498db', '#27ae60'],
                    borderColor: '#fff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading portal stats:', error);
    }
}

async function loadLocationStats() {
    try {
        const response = await fetch('/api/location-stats');
        const data = await response.json();

        const ctx = document.getElementById('location-chart');
        if (!ctx) return;

        if (state.charts.location) {
            state.charts.location.destroy();
        }

        state.charts.location = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.location),
                datasets: [{
                    label: 'Applications',
                    data: data.map(d => d.count),
                    backgroundColor: '#667eea',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading location stats:', error);
    }
}

async function loadScoreDistribution() {
    try {
        const response = await fetch('/api/match-score-distribution');
        const data = await response.json();

        const ctx = document.getElementById('score-distribution-chart');
        if (!ctx) return;

        if (state.charts.distribution) {
            state.charts.distribution.destroy();
        }

        state.charts.distribution = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    label: 'Count',
                    data: data.map(d => d.count),
                    backgroundColor: ['#e74c3c', '#f39c12', '#3498db', '#27ae60', '#667eea'],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading score distribution:', error);
    }
}

// ===========================
// File Upload
// ===========================

function handleFileUpload(files) {
    if (files.length === 0) return;

    const file = files[0];
    if (!file.name.match(/\.(pdf|doc|docx)$/i)) {
        showToast('Please upload a valid resume file (PDF, DOC, DOCX)', 'error');
        return;
    }

    showToast(`Resume uploaded: ${file.name}`, 'success');
    console.log('File uploaded:', file);
}

// ===========================
// Utilities
// ===========================

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Refresh data periodically
setInterval(() => {
    if (state.currentSection === 'dashboard') {
        loadDashboardData();
    }
}, 60000); // Refresh every minute

// ===========================
// AI Copilot
// ===========================

async function loadAISettings() {
    try {
        const response = await fetch('/api/ai/settings');
        const settings = await response.json();
        state.aiSettings = settings;
        applyAISettingsToUI(settings);
    } catch (error) {
        console.error('Error loading AI settings:', error);
    }
}

function applyAISettingsToUI(settings) {
    const autoApply = document.getElementById('ai-auto-apply-toggle');
    const autoAnswer = document.getElementById('ai-auto-answer-toggle');
    const minScore = document.getElementById('ai-min-match-score');
    const maxApply = document.getElementById('ai-max-auto-apply');
    const style = document.getElementById('ai-answer-style');
    const ollamaEnabled = document.getElementById('ollama-enabled');
    const ollamaModel = document.getElementById('ollama-model');
    const ollamaBaseUrl = document.getElementById('ollama-base-url');

    if (autoApply) autoApply.checked = !!settings.auto_apply_enabled;
    if (autoAnswer) autoAnswer.checked = !!settings.auto_answer_enabled;
    if (minScore) minScore.value = settings.min_match_score ?? 70;
    if (maxApply) maxApply.value = settings.max_daily_auto_apply ?? 10;
    if (style) style.value = settings.answer_style ?? 'professional';
    if (ollamaEnabled) ollamaEnabled.checked = settings.ollama_enabled !== false;
    if (ollamaModel) ollamaModel.value = settings.ollama_model ?? 'llama3.2:3b';
    if (ollamaBaseUrl) ollamaBaseUrl.value = settings.ollama_base_url ?? 'http://127.0.0.1:11434';
}

async function saveAISettings() {
    try {
        const payload = {
            auto_apply_enabled: !!document.getElementById('ai-auto-apply-toggle')?.checked,
            auto_answer_enabled: !!document.getElementById('ai-auto-answer-toggle')?.checked,
            min_match_score: Number(document.getElementById('ai-min-match-score')?.value || 70),
            max_daily_auto_apply: Number(document.getElementById('ai-max-auto-apply')?.value || 10),
            answer_style: document.getElementById('ai-answer-style')?.value || 'professional',
            ollama_enabled: !!document.getElementById('ollama-enabled')?.checked,
            ollama_model: document.getElementById('ollama-model')?.value || 'llama3.2:3b',
            ollama_base_url: document.getElementById('ollama-base-url')?.value || 'http://127.0.0.1:11434'
        };

        const response = await fetch('/api/ai/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const settings = await response.json();
        state.aiSettings = settings;
        showToast('AI Copilot settings updated', 'success');
    } catch (error) {
        console.error('Error saving AI settings:', error);
        showToast('Failed to save AI settings', 'error');
    }
}

async function checkOllamaConnection() {
    await saveAISettings();

    const status = document.getElementById('ollama-status');
    const button = document.getElementById('test-ollama-btn');
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    }

    try {
        const response = await fetch('/api/ai/provider-status');
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'Ollama is not reachable');
        }

        if (status) {
            status.textContent = data.model_available
                ? `Connected. Model "${data.configured_model}" is available.`
                : `Connected, but model "${data.configured_model}" was not found. Pull it in Ollama first.`;
        }
        showToast('Ollama check completed', 'success');
    } catch (error) {
        if (status) status.textContent = `Connection failed: ${error.message}`;
        showToast('Ollama connection failed', 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-plug"></i> Test Ollama Connection';
        }
    }
}

async function loadAIInsights() {
    const container = document.getElementById('ai-insights-list');
    if (!container) return;

    try {
        const response = await fetch('/api/ai/insights');
        const data = await response.json();
        container.innerHTML = (data.suggestions || [])
            .map(item => `<div class="ai-insight-item"><i class="fas fa-lightbulb"></i> ${item}</div>`)
            .join('');
    } catch (error) {
        console.error('Error loading AI insights:', error);
        container.innerHTML = '<p>Unable to load AI insights.</p>';
    }
}

async function runAIAutopilot() {
    await saveAISettings();

    const status = document.getElementById('autopilot-status');
    const button = document.getElementById('run-autopilot-btn');
    if (!button) return;

    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
    if (status) status.textContent = 'AI Autopilot is scanning jobs and applying to best matches...';

    try {
        const payload = {
            min_match_score: Number(document.getElementById('ai-min-match-score')?.value || 70),
            max_apply: Number(document.getElementById('ai-max-auto-apply')?.value || 10),
            role: document.getElementById('role-filter')?.value || '',
            location: document.getElementById('location-filter')?.value || ''
        };

        const response = await fetch('/api/ai/autopilot/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || data.error || 'Autopilot run failed');
        }

        const summary = data.summary || {};
        if (status) {
            status.textContent = `Done. Scanned ${summary.scanned_jobs || 0}, eligible ${summary.eligible_jobs || 0}, applied ${summary.applied || 0}.`;
        }

        showToast(`AI Autopilot applied to ${summary.applied || 0} jobs`, 'success');
        loadDashboardData();
        loadApplications();
    } catch (error) {
        console.error('Error running AI autopilot:', error);
        if (status) status.textContent = `Autopilot error: ${error.message}`;
        showToast(error.message || 'Failed to run AI autopilot', 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-rocket"></i> Run AI Autopilot Now';
    }
}

function getAIContextJobId() {
    if (state.selectedJobs.size > 0) {
        return Array.from(state.selectedJobs)[0];
    }
    if (state.searchResults.length > 0) {
        return state.searchResults[0].portal_job_id;
    }
    return null;
}

async function generateAIAutoAnswers() {
    if (!document.getElementById('ai-auto-answer-toggle')?.checked) {
        showToast('Enable Auto Answers first', 'info');
        return;
    }

    await saveAISettings();

    const container = document.getElementById('ai-answers-container');
    const jobId = getAIContextJobId();
    const style = document.getElementById('ai-answer-style')?.value || 'professional';
    const rawQuestions = document.getElementById('ai-questions-input')?.value || '';
    const parsedQuestions = rawQuestions
        .split('\n')
        .map(q => q.trim())
        .filter(Boolean);
    const questions = parsedQuestions.length > 0 ? parsedQuestions : [
        'Tell us about yourself.',
        'How many years of Python experience do you have?',
        'What is your current/preferred location?'
    ];
    if (container) container.innerHTML = '<p><i class="fas fa-spinner fa-spin"></i> Generating answers...</p>';

    try {
        const response = await fetch('/api/ai/answers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                portal_job_id: jobId,
                style,
                questions
            })
        });
        const data = await response.json();

        if (!container) return;
        container.innerHTML = (data.answers || []).map(item => `
            <div class="ai-answer-card">
                <div class="question">${item.question} <span style="font-size:12px;color:#667eea;">(${item.source || data.provider || 'ai'})</span></div>
                <div class="answer">${item.answer}</div>
            </div>
        `).join('');

        showToast('AI answers generated', 'success');
    } catch (error) {
        console.error('Error generating AI answers:', error);
        if (container) container.innerHTML = '<p>Failed to generate answers.</p>';
        showToast('Failed to generate AI answers', 'error');
    }
}

function getPipelineInputs() {
    return {
        role: document.getElementById('pipeline-role')?.value || 'Python Developer',
        location: document.getElementById('pipeline-location')?.value || 'Hyderabad',
        minScore: Number(document.getElementById('pipeline-min-score')?.value || 70),
        ragQuery: document.getElementById('rag-query-input')?.value || 'python backend aws',
        dryRun: !!document.getElementById('pipeline-dry-run')?.checked,
        headless: !!document.getElementById('pipeline-headless')?.checked
    };
}

function renderPipelineOutput(title, payload) {
    const out = document.getElementById('pipeline-output');
    if (!out) return;
    out.innerHTML = `
        <div class="ai-answer-card">
            <div class="question">${title}</div>
            <div class="answer"><pre style="white-space:pre-wrap;margin:0;">${JSON.stringify(payload, null, 2)}</pre></div>
        </div>
    `;
}

async function scrapeNaukriLive() {
    const status = document.getElementById('pipeline-status');
    const { role, location, headless } = getPipelineInputs();
    if (status) status.textContent = 'Scraping live Naukri jobs...';
    try {
        const response = await fetch('/api/naukri/scrape-live', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, location, limit: 20, headless })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Scrape failed');
        if (status) status.textContent = `Scraped ${data.total_scraped}, matched ${data.total_matched}, indexed ${data.rag_indexed}.`;
        renderPipelineOutput('Naukri Scrape Result', data);
        loadDashboardData();
    } catch (error) {
        if (status) status.textContent = `Scrape error: ${error.message}`;
        showToast('Naukri scrape failed', 'error');
    }
}

async function testRagQuery() {
    const status = document.getElementById('pipeline-status');
    const { ragQuery } = getPipelineInputs();
    if (status) status.textContent = 'Running RAG retrieval...';
    try {
        const response = await fetch('/api/rag/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: ragQuery, top_k: 5 })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'RAG query failed');
        if (status) status.textContent = `Retrieved ${data.results?.length || 0} results from vector DB.`;
        renderPipelineOutput('RAG Query Result', data);
    } catch (error) {
        if (status) status.textContent = `RAG error: ${error.message}`;
        showToast('RAG query failed', 'error');
    }
}

async function runFullPipeline() {
    const status = document.getElementById('pipeline-status');
    const { role, location, minScore, dryRun, headless } = getPipelineInputs();
    if (status) status.textContent = 'Running full pipeline...';
    try {
        const response = await fetch('/api/pipeline/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                role,
                location,
                min_score: minScore,
                max_apply: 5,
                dry_run: dryRun,
                headless
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Pipeline run failed');
        if (status) status.textContent = `Pipeline done. Scraped ${data.scraped}, eligible ${data.eligible}, attempted ${data.apply_attempted}.`;
        renderPipelineOutput('Full Pipeline Result', data);
        loadDashboardData();
        loadApplications();
    } catch (error) {
        if (status) status.textContent = `Pipeline error: ${error.message}`;
        showToast('Pipeline run failed', 'error');
    }
}
