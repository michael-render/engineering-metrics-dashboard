/**
 * Main dashboard logic
 */

// Current state
let currentPeriodType = 'weekly';
let currentPeriods = 12;

/**
 * Initialize the dashboard
 */
async function initDashboard() {
    // Get initial values from controls
    currentPeriodType = document.getElementById('periodType').value;
    currentPeriods = parseInt(document.getElementById('periods').value);

    // Add event listeners
    document.getElementById('periodType').addEventListener('change', (e) => {
        currentPeriodType = e.target.value;
        refreshData();
    });

    document.getElementById('periods').addEventListener('change', (e) => {
        currentPeriods = parseInt(e.target.value);
        refreshData();
    });

    // Load initial data
    await refreshData();
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', initDashboard);
