import { createServer } from 'http';
import 'dotenv/config';
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, subWeeks, subMonths } from 'date-fns';

import { createGitHubClient, createLinearClient, createSlabClient } from './clients/index.js';
import { calculateDoraMetrics } from './metrics/index.js';
import { generateReport, formatReportAsMarkdown } from './reports/index.js';
import type { MetricsPeriod } from './types/index.js';

const PORT = process.env.PORT ?? 3000;

function getPeriod(type: 'weekly' | 'monthly'): MetricsPeriod {
  const now = new Date();
  if (type === 'weekly') {
    return {
      type: 'weekly',
      startDate: startOfWeek(subWeeks(now, 1), { weekStartsOn: 1 }),
      endDate: endOfWeek(subWeeks(now, 1), { weekStartsOn: 1 }),
    };
  }
  return {
    type: 'monthly',
    startDate: startOfMonth(subMonths(now, 1)),
    endDate: endOfMonth(subMonths(now, 1)),
  };
}

async function fetchMetrics(period: MetricsPeriod) {
  const githubClient = createGitHubClient();
  const linearClient = createLinearClient();
  const slabClient = createSlabClient();

  const [deployments, pullRequests, incidents, postmortems] = await Promise.all([
    githubClient.getDeployments(period),
    githubClient.getPullRequests(period),
    linearClient.getIncidentIssues(period),
    slabClient?.getPostmortems(period) ?? Promise.resolve([]),
  ]);

  return calculateDoraMetrics({
    deployments,
    pullRequests,
    incidents,
    postmortems,
    period,
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`);

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  try {
    if (url.pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'healthy', timestamp: new Date().toISOString() }));
      return;
    }

    if (url.pathname === '/metrics/weekly') {
      const period = getPeriod('weekly');
      const metrics = await fetchMetrics(period);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(metrics, null, 2));
      return;
    }

    if (url.pathname === '/metrics/monthly') {
      const period = getPeriod('monthly');
      const metrics = await fetchMetrics(period);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(metrics, null, 2));
      return;
    }

    if (url.pathname === '/report/weekly') {
      const period = getPeriod('weekly');
      const metrics = await fetchMetrics(period);
      const report = generateReport({ currentMetrics: metrics });
      const markdown = formatReportAsMarkdown(report);
      res.writeHead(200, { 'Content-Type': 'text/markdown' });
      res.end(markdown);
      return;
    }

    if (url.pathname === '/report/monthly') {
      const period = getPeriod('monthly');
      const metrics = await fetchMetrics(period);
      const report = generateReport({ currentMetrics: metrics });
      const markdown = formatReportAsMarkdown(report);
      res.writeHead(200, { 'Content-Type': 'text/markdown' });
      res.end(markdown);
      return;
    }

    if (url.pathname === '/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        name: 'Engineering Metrics Dashboard API',
        version: '1.0.0',
        endpoints: [
          { path: '/health', description: 'Health check' },
          { path: '/metrics/weekly', description: 'Weekly DORA metrics (JSON)' },
          { path: '/metrics/monthly', description: 'Monthly DORA metrics (JSON)' },
          { path: '/report/weekly', description: 'Weekly report (Markdown)' },
          { path: '/report/monthly', description: 'Monthly report (Markdown)' },
        ],
      }, null, 2));
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  } catch (error) {
    console.error('Request error:', error);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error',
    }));
  }
});

server.listen(PORT, () => {
  console.log(`Engineering Metrics Dashboard API running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
});
