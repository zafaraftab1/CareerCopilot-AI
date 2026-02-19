/* =================================================================
   AI Job Application Tracker - Dashboard JavaScript
   ================================================================= */

// Global state
const state = {
    currentSection: 'dashboard',
    applications: [],
    searchResults: [],
    selectedJobs: new Set(),
    charts: {}
};

// ===========================
// Initialization
// ===========================

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboardData();
    loadApplications();
    loadResumeSummary();
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
        'dashboard': 'Dashboard',
        'jobs': 'Job Search',
        'applications': 'Applications',
        'resume': 'Resume & Profile',
        'settings': 'Settings'
    };
    document.getElementById('section-title').textContent = titles[section] || 'Dashboard';

    state.currentSection = section;

    // Load section-specific data
    if (section === 'applications') {
        loadApplications();
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

