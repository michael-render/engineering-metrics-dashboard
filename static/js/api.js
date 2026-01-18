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
