/**
 * Main dashboard logic
 */

// Current state
let currentPeriodType = 'weekly';
let currentPeriods = 12;

// Backfill state
let backfillStatusInterval = null;
let currentPreview = null;

/**
 * Initialize the dashboard
 */
async function initDashboard() {
    // Get initial values from controls
    currentPeriodType = document.getElementById('periodType').value;
    currentPeriods = parseInt(document.getElementById('periods').value);

    // Add event listeners for dashboard controls
    document.getElementById('periodType').addEventListener('change', (e) => {
        currentPeriodType = e.target.value;
        refreshData();
    });

    document.getElementById('periods').addEventListener('change', (e) => {
        currentPeriods = parseInt(e.target.value);
        refreshData();
    });

    document.getElementById('refreshBtn').addEventListener('click', () => {
        refreshData();
    });

    // Load initial data
    await refreshData();
}

/**
 * Initialize backfill modal and form
 */
function initBackfillModal() {
    const modal = document.getElementById('backfillModal');
    const openBtn = document.getElementById('backfillBtn');
    const closeBtn = document.getElementById('closeBackfillModal');

    // Set default dates
    const today = new Date();
    const twoYearsAgo = new Date(today);
    twoYearsAgo.setFullYear(today.getFullYear() - 2);

    document.getElementById('backfillStartDate').value = twoYearsAgo.toISOString().split('T')[0];
    document.getElementById('backfillEndDate').value = today.toISOString().split('T')[0];

    // Modal open/close handlers
    openBtn.addEventListener('click', () => {
        modal.classList.add('active');
        checkBackfillStatus();
    });

    closeBtn.addEventListener('click', () => {
        modal.classList.remove('active');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });

    // Escape key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            modal.classList.remove('active');
        }
    });

    // Backfill action handlers
    document.getElementById('previewBackfillBtn').addEventListener('click', handlePreviewBackfill);
    document.getElementById('startBackfillBtn').addEventListener('click', handleStartBackfill);
    document.getElementById('stopBackfillBtn').addEventListener('click', handleStopBackfill);

    // Reset preview when parameters change
    const formFields = ['backfillStartDate', 'backfillEndDate', 'backfillPeriodType', 'backfillDelay'];
    formFields.forEach(id => {
        document.getElementById(id).addEventListener('change', resetBackfillPreview);
    });
}

/**
 * Refresh all dashboard data
 */
async function refreshData() {
    const container = document.querySelector('.container');
    container.classList.add('loading');

    try {
        // Fetch latest metrics and trends in parallel
        const [latestMetrics, trends] = await Promise.all([
            fetchLatestMetrics(currentPeriodType).catch(() => null),
            fetchMetricsTrends(currentPeriods, currentPeriodType).catch(() => null),
        ]);

        if (latestMetrics) {
            updateMetricsCards(latestMetrics);
            updateOverallRating(latestMetrics);
        } else {
            showNoDataMessage();
        }

        if (trends && trends.trends && trends.trends.length > 0) {
            updateTrendsChart(trends);
            updateSummary(trends);
            document.getElementById('summary-section').style.display = 'block';
        } else {
            document.getElementById('summary-section').style.display = 'none';
        }

    } catch (error) {
        console.error('Error loading data:', error);
        showError(error.message);
    } finally {
        container.classList.remove('loading');
    }
}

/**
 * Update metrics cards with latest data
 * @param {Object} metrics - Metrics snapshot
 */
function updateMetricsCards(metrics) {
    const m = metrics.metrics;

    // Deployment Frequency
    updateCard('df', {
        value: m.deployment_frequency.deployments_per_day.toFixed(2),
        rating: m.deployment_frequency.rating,
    });

    // Lead Time
    updateCard('lt', {
        value: m.lead_time.median_hours.toFixed(1),
        rating: m.lead_time.rating,
    });

    // Change Failure Rate
    updateCard('cfr', {
        value: m.change_failure_rate.percentage.toFixed(1),
        rating: m.change_failure_rate.rating,
    });

    // MTTR
    updateCard('mttr', {
        value: m.mttr.median_hours.toFixed(1),
        rating: m.mttr.rating,
    });
}

/**
 * Update a single metric card
 * @param {string} prefix - Card ID prefix (df, lt, cfr, mttr)
 * @param {Object} data - Value and rating
 */
function updateCard(prefix, data) {
    document.getElementById(`${prefix}-value`).textContent = data.value;

    const ratingBadge = document.getElementById(`${prefix}-rating`);
    ratingBadge.textContent = formatRating(data.rating);
    ratingBadge.className = `rating-badge ${getRatingClass(data.rating)}`;
}

/**
 * Update overall rating display
 * @param {Object} metrics - Metrics snapshot
 */
function updateOverallRating(metrics) {
    const rating = metrics.overall_rating;
    const ratingEl = document.getElementById('overall-rating');
    ratingEl.textContent = formatRating(rating);
    ratingEl.className = getRatingClass(rating);

    // Update period info
    const period = metrics.period;
    const startDate = new Date(period.start_date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
    const endDate = new Date(period.end_date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
    document.getElementById('period-info').textContent =
        `${period.type.charAt(0).toUpperCase() + period.type.slice(1)} Report: ${startDate} - ${endDate}`;
}

/**
 * Update summary section with trend data
 * @param {Object} trends - Trends API response
 */
function updateSummary(trends) {
    const summary = trends.summary;

    document.getElementById('avg-df').textContent = summary.avg_deployment_frequency.toFixed(2);
    document.getElementById('avg-lt').textContent = summary.avg_lead_time.toFixed(1);
    document.getElementById('avg-cfr').textContent = summary.avg_cfr.toFixed(1);
    document.getElementById('avg-mttr').textContent = summary.avg_mttr.toFixed(1);

    const trendDirection = document.getElementById('trend-direction');
    trendDirection.textContent = summary.trend_direction.charAt(0).toUpperCase() +
        summary.trend_direction.slice(1);
    trendDirection.className = summary.trend_direction;
}

/**
 * Show no data message
 */
function showNoDataMessage() {
    document.getElementById('df-value').textContent = '-';
    document.getElementById('lt-value').textContent = '-';
    document.getElementById('cfr-value').textContent = '-';
    document.getElementById('mttr-value').textContent = '-';
    document.getElementById('overall-rating').textContent = 'No Data';
    document.getElementById('period-info').textContent =
        'No metrics data available. Run the workflow to collect data.';
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    console.error(message);
    document.getElementById('period-info').textContent = `Error: ${message}`;
}

// ========== Backfill Functions ==========

/**
 * Reset backfill preview when parameters change
 */
function resetBackfillPreview() {
    currentPreview = null;
    document.getElementById('startBackfillBtn').disabled = true;
    document.getElementById('backfillPreview').classList.remove('active');
}

/**
 * Handle preview backfill button click
 */
async function handlePreviewBackfill() {
    const startDate = document.getElementById('backfillStartDate').value;
    const endDate = document.getElementById('backfillEndDate').value;
    const periodType = document.getElementById('backfillPeriodType').value;
    const delay = parseFloat(document.getElementById('backfillDelay').value);

    if (!startDate || !endDate) {
        alert('Please select start and end dates');
        return;
    }

    const previewBtn = document.getElementById('previewBackfillBtn');
    previewBtn.disabled = true;
    previewBtn.textContent = 'Loading...';

    try {
        const preview = await previewBackfill(
            `${startDate}T00:00:00Z`,
            `${endDate}T23:59:59Z`,
            periodType,
            delay
        );

        currentPreview = preview;
        showBackfillPreview(preview);
        document.getElementById('startBackfillBtn').disabled = false;
    } catch (error) {
        alert(`Preview failed: ${error.message}`);
    } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = 'Preview';
    }
}

/**
 * Show backfill preview
 * @param {Object} preview - Preview data from API
 */
function showBackfillPreview(preview) {
    document.getElementById('previewPeriods').textContent = preview.total_periods;
    document.getElementById('previewTime').textContent = `~${preview.estimated_minutes} min`;

    const periodsList = document.getElementById('previewPeriodsList');
    periodsList.innerHTML = '';

    preview.periods.forEach((p) => {
        const start = new Date(p.start_date).toLocaleDateString();
        const end = new Date(p.end_date).toLocaleDateString();
        periodsList.innerHTML += `<span class="period-chip">${start} - ${end}</span>`;
    });

    if (preview.total_periods > preview.periods.length) {
        periodsList.innerHTML += `<span class="period-chip more">+${preview.total_periods - preview.periods.length} more</span>`;
    }

    document.getElementById('backfillPreview').classList.add('active');
}

/**
 * Handle start backfill button click
 */
async function handleStartBackfill() {
    if (!currentPreview) {
        alert('Please preview first');
        return;
    }

    const confirmed = confirm(
        `This will backfill ${currentPreview.total_periods} periods.\n` +
        `Estimated time: ~${currentPreview.estimated_minutes} minutes.\n\n` +
        `Continue?`
    );

    if (!confirmed) return;

    const startDate = document.getElementById('backfillStartDate').value;
    const endDate = document.getElementById('backfillEndDate').value;
    const periodType = document.getElementById('backfillPeriodType').value;
    const delay = parseFloat(document.getElementById('backfillDelay').value);

    try {
        await startBackfill(
            `${startDate}T00:00:00Z`,
            `${endDate}T23:59:59Z`,
            periodType,
            delay
        );

        showBackfillRunning();
        startStatusPolling();
    } catch (error) {
        alert(`Failed to start backfill: ${error.message}`);
    }
}

/**
 * Handle stop backfill button click
 */
async function handleStopBackfill() {
    try {
        await stopBackfill();
        alert('Stop requested. Current period will complete.');
    } catch (error) {
        alert(`Failed to stop: ${error.message}`);
    }
}

/**
 * Show backfill running state
 */
function showBackfillRunning() {
    document.getElementById('previewBackfillBtn').disabled = true;
    document.getElementById('startBackfillBtn').style.display = 'none';
    document.getElementById('stopBackfillBtn').style.display = 'inline-block';
    document.getElementById('backfillStatus').classList.add('active');
}

/**
 * Show backfill idle state
 */
function showBackfillIdle() {
    document.getElementById('previewBackfillBtn').disabled = false;
    document.getElementById('startBackfillBtn').style.display = 'inline-block';
    document.getElementById('startBackfillBtn').disabled = true;
    document.getElementById('stopBackfillBtn').style.display = 'none';
    document.getElementById('backfillStatus').classList.remove('active');
    currentPreview = null;
}

/**
 * Start polling for backfill status
 */
function startStatusPolling() {
    if (backfillStatusInterval) {
        clearInterval(backfillStatusInterval);
    }

    backfillStatusInterval = setInterval(async () => {
        await checkBackfillStatus();
    }, 3000);
}

/**
 * Check current backfill status
 */
async function checkBackfillStatus() {
    try {
        const status = await getBackfillStatus();

        if (status.running) {
            showBackfillRunning();
            updateBackfillProgress(status);
        } else {
            if (backfillStatusInterval) {
                clearInterval(backfillStatusInterval);
                backfillStatusInterval = null;
            }

            if (status.error) {
                showBackfillError(status.error);
            } else if (status.results && status.results.length > 0) {
                showBackfillComplete(status);
                refreshData();
            }

            showBackfillIdle();
        }
    } catch (error) {
        console.error('Failed to check backfill status:', error);
    }
}

/**
 * Update backfill progress display
 * @param {Object} status - Status from API
 */
function updateBackfillProgress(status) {
    document.getElementById('backfillProgress').textContent = status.progress || '0/?';

    // Parse progress for progress bar
    const progressMatch = (status.progress || '0/1').match(/(\d+)\/(\d+)/);
    if (progressMatch) {
        const current = parseInt(progressMatch[1]);
        const total = parseInt(progressMatch[2]);
        const percent = total > 0 ? (current / total) * 100 : 0;
        document.getElementById('progressFill').style.width = `${percent}%`;
    }

    // Show recent results
    const resultsEl = document.getElementById('backfillResults');
    if (status.results && status.results.length > 0) {
        const recent = status.results.slice(-3).reverse();
        resultsEl.innerHTML = recent.map(r =>
            `<div class="result-item">
                <span class="result-period">${new Date(r.period_start).toLocaleDateString()} - ${new Date(r.period_end).toLocaleDateString()}</span>
                <span class="result-stats">${r.deployments} deploys, ${r.pull_requests} PRs, ${r.incidents} incidents</span>
            </div>`
        ).join('');
    }
}

/**
 * Show backfill complete message
 * @param {Object} status - Final status
 */
function showBackfillComplete(status) {
    const resultsEl = document.getElementById('backfillResults');
    resultsEl.innerHTML = `<div class="result-complete">Backfill complete! Processed ${status.results.length} periods.</div>`;
    document.getElementById('backfillProgress').textContent = 'Complete';
    document.getElementById('progressFill').style.width = '100%';
}

/**
 * Show backfill error message
 * @param {string} error - Error message
 */
function showBackfillError(error) {
    const resultsEl = document.getElementById('backfillResults');
    resultsEl.innerHTML = `<div class="result-error">Error: ${error}</div>`;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    initBackfillModal();
});
