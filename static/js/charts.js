/**
 * Chart.js configurations for DORA metrics
 */

let trendsChart = null;

const chartColors = {
    deploymentFrequency: '#22c55e',
    leadTime: '#3b82f6',
    changeFailureRate: '#f59e0b',
    mttr: '#ef4444',
};

/**
 * Initialize or update the trends chart
 * @param {Object} trendsData - Trends API response
 */
function updateTrendsChart(trendsData) {
    const ctx = document.getElementById('trendsChart').getContext('2d');

    const labels = trendsData.trends.map(t => {
        const date = new Date(t.period_start);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const data = {
        labels,
        datasets: [
            {
                label: 'Deployment Frequency (per day)',
                data: trendsData.trends.map(t => t.deployment_frequency),
                borderColor: chartColors.deploymentFrequency,
                backgroundColor: chartColors.deploymentFrequency + '20',
                tension: 0.3,
                yAxisID: 'y',
            },
            {
                label: 'Lead Time (hours)',
                data: trendsData.trends.map(t => t.lead_time_hours),
                borderColor: chartColors.leadTime,
                backgroundColor: chartColors.leadTime + '20',
                tension: 0.3,
                yAxisID: 'y1',
            },
            {
                label: 'Change Failure Rate (%)',
                data: trendsData.trends.map(t => t.change_failure_rate),
                borderColor: chartColors.changeFailureRate,
                backgroundColor: chartColors.changeFailureRate + '20',
                tension: 0.3,
                yAxisID: 'y2',
            },
            {
                label: 'MTTR (hours)',
                data: trendsData.trends.map(t => t.mttr_hours),
                borderColor: chartColors.mttr,
                backgroundColor: chartColors.mttr + '20',
                tension: 0.3,
                yAxisID: 'y1',
            },
        ],
    };

    const config = {
        type: 'line',
        data,
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#e2e8f0',
                        padding: 20,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#e2e8f0',
                    bodyColor: '#e2e8f0',
                    borderColor: '#334155',
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    grid: {
                        color: '#334155',
                    },
                    ticks: {
                        color: '#94a3b8',
                    },
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Deployments/day',
                        color: '#94a3b8',
                    },
                    grid: {
                        color: '#334155',
                    },
                    ticks: {
                        color: '#94a3b8',
                    },
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Hours',
                        color: '#94a3b8',
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#94a3b8',
                    },
                },
                y2: {
                    type: 'linear',
                    display: false,
                    position: 'right',
                    min: 0,
                    max: 100,
                },
            },
        },
    };

    if (trendsChart) {
        trendsChart.destroy();
    }

    trendsChart = new Chart(ctx, config);
}

/**
 * Get color class for a rating
 * @param {string} rating - elite, high, medium, low
 * @returns {string} CSS class name
 */
function getRatingClass(rating) {
    return rating.toLowerCase();
}

/**
 * Format a rating for display
 * @param {string} rating - elite, high, medium, low
 * @returns {string} Formatted rating text
 */
function formatRating(rating) {
    const labels = {
        elite: 'Elite',
        high: 'High',
        medium: 'Medium',
        low: 'Low',
    };
    return labels[rating.toLowerCase()] || rating;
}
