/**
 * API client for Engineering Metrics Dashboard
 */

const API_BASE = '/api/v1';

/**
 * Fetch the latest metrics snapshot
 * @param {string} periodType - 'weekly' or 'monthly'
 * @returns {Promise<Object>} Metrics snapshot
 */
async function fetchLatestMetrics(periodType = null) {
    const params = periodType ? `?period_type=${periodType}` : '';
    const response = await fetch(`${API_BASE}/metrics/latest${params}`);

    if (!response.ok) {
        if (response.status === 404) {
            throw new Error('No metrics data available yet. Run the workflow to collect data.');
        }
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

/**
 * Fetch metrics trends for historical analysis
 * @param {number} periods - Number of periods to fetch
 * @param {string} periodType - 'weekly' or 'monthly'
 * @returns {Promise<Object>} Trends data
 */
async function fetchMetricsTrends(periods = 12, periodType = 'weekly') {
    const response = await fetch(
        `${API_BASE}/metrics/trends?periods=${periods}&period_type=${periodType}`
    );

    if (!response.ok) {
        if (response.status === 404) {
            throw new Error('No trend data available yet. Run the workflow multiple times to collect historical data.');
        }
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

/**
 * Fetch raw deployments data
 * @param {string} startDate - ISO date string
 * @param {string} endDate - ISO date string
 * @param {string} status - Optional status filter
 * @param {number} limit - Max records
 * @returns {Promise<Array>} Deployments
 */
async function fetchDeployments(startDate, endDate, status = null, limit = 100) {
    let url = `${API_BASE}/raw/deployments?start_date=${startDate}&end_date=${endDate}&limit=${limit}`;
    if (status) {
        url += `&status=${status}`;
    }

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

/**
 * Fetch raw incidents data
 * @param {string} startDate - ISO date string
 * @param {string} endDate - ISO date string
 * @param {string} severity - Optional severity filter
 * @param {number} limit - Max records
 * @returns {Promise<Array>} Incidents
 */
async function fetchIncidents(startDate, endDate, severity = null, limit = 100) {
    let url = `${API_BASE}/raw/incidents?start_date=${startDate}&end_date=${endDate}&limit=${limit}`;
    if (severity) {
        url += `&severity=${severity}`;
    }

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

/**
 * Preview backfill periods without starting
 * @param {string} startDate - ISO date string
 * @param {string} endDate - ISO date string
 * @param {string} periodType - 'weekly' or 'monthly'
 * @param {number} delaySeconds - Delay between API calls
 * @returns {Promise<Object>} Preview data
 */
async function previewBackfill(startDate, endDate, periodType = 'weekly', delaySeconds = 2.0) {
    const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        period_type: periodType,
        delay_seconds: delaySeconds.toString(),
    });

    const response = await fetch(`${API_BASE}/backfill/preview?${params}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `API error: ${response.status}`);
    }
    return response.json();
}

/**
 * Start a backfill job
 * @param {string} startDate - ISO date string
 * @param {string} endDate - ISO date string
 * @param {string} periodType - 'weekly' or 'monthly'
 * @param {number} delaySeconds - Delay between API calls
 * @returns {Promise<Object>} Start response
 */
async function startBackfill(startDate, endDate, periodType = 'weekly', delaySeconds = 2.0) {
    const response = await fetch(`${API_BASE}/backfill/start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            start_date: startDate,
            end_date: endDate,
            period_type: periodType,
            delay_seconds: delaySeconds,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `API error: ${response.status}`);
    }
    return response.json();
}

/**
 * Get current backfill job status
 * @returns {Promise<Object>} Status data
 */
async function getBackfillStatus() {
    const response = await fetch(`${API_BASE}/backfill/status`);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}

/**
 * Request to stop current backfill job
 * @returns {Promise<Object>} Stop response
 */
async function stopBackfill() {
    const response = await fetch(`${API_BASE}/backfill/stop`, {
        method: 'POST',
    });
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}
