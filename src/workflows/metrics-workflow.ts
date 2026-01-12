import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, subWeeks, subMonths } from 'date-fns';
import 'dotenv/config';

import { createGitHubClient, createLinearClient, createSlabClient } from '../clients/index.js';
import { calculateDoraMetrics, type DoraCalculationInput } from '../metrics/index.js';
import { generateReport, formatReportAsMarkdown, sendNotifications } from '../reports/index.js';
import type {
  MetricsPeriod,
  DataSourceResult,
  GitHubDeployment,
  GitHubPullRequest,
  LinearIssue,
  SlabPostmortem,
} from '../types/index.js';

interface DataFetchResult {
  deployments: GitHubDeployment[];
  pullRequests: GitHubPullRequest[];
  incidents: LinearIssue[];
  postmortems: SlabPostmortem[];
}

type DataSource = 'github-deployments' | 'github-prs' | 'linear-incidents' | 'slab-postmortems';

interface FetchTask {
  source: DataSource;
  fetch: () => Promise<unknown>;
}

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

function getPreviousPeriod(current: MetricsPeriod): MetricsPeriod {
  if (current.type === 'weekly') {
    return {
      type: 'weekly',
      startDate: startOfWeek(subWeeks(current.startDate, 1), { weekStartsOn: 1 }),
      endDate: endOfWeek(subWeeks(current.startDate, 1), { weekStartsOn: 1 }),
    };
  }

  return {
    type: 'monthly',
    startDate: startOfMonth(subMonths(current.startDate, 1)),
    endDate: endOfMonth(subMonths(current.startDate, 1)),
  };
}

/**
 * Fetch data from multiple sources concurrently using .map() for parallel processing
 * This leverages Render Workflows' ability to run parallel tasks
 */
async function fetchDataFromSources(period: MetricsPeriod): Promise<DataFetchResult> {
  console.log(`Fetching data for period: ${period.startDate.toISOString()} - ${period.endDate.toISOString()}`);

  const githubClient = createGitHubClient();
  const linearClient = createLinearClient();
  const slabClient = createSlabClient();

  // Define all fetch tasks
  const fetchTasks: FetchTask[] = [
    {
      source: 'github-deployments',
      fetch: () => githubClient.getDeployments(period),
    },
    {
      source: 'github-prs',
      fetch: () => githubClient.getPullRequests(period),
    },
    {
      source: 'linear-incidents',
      fetch: () => linearClient.getIncidentIssues(period),
    },
    {
      source: 'slab-postmortems',
      fetch: slabClient
        ? () => slabClient.getPostmortems(period)
        : () => Promise.resolve([]),
    },
  ];

  // Execute all fetches in parallel using .map() with Promise.allSettled
  // This is the key pattern for Render Workflows parallel processing
  const results = await Promise.allSettled(
    fetchTasks.map(async (task): Promise<DataSourceResult<unknown>> => {
      console.log(`Starting fetch: ${task.source}`);
      const startTime = Date.now();

      try {
        const data = await task.fetch();
        console.log(`Completed fetch: ${task.source} in ${Date.now() - startTime}ms`);
        return {
          source: task.source.split('-')[0] as 'linear' | 'github' | 'slab',
          data,
          fetchedAt: new Date(),
        };
      } catch (error) {
        console.error(`Failed fetch: ${task.source}`, error);
        return {
          source: task.source.split('-')[0] as 'linear' | 'github' | 'slab',
          data: [],
          fetchedAt: new Date(),
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    })
  );

  // Process results
  const data: DataFetchResult = {
    deployments: [],
    pullRequests: [],
    incidents: [],
    postmortems: [],
  };

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      const sourceResult = result.value;
      switch (fetchTasks[index].source) {
        case 'github-deployments':
          data.deployments = sourceResult.data as GitHubDeployment[];
          break;
        case 'github-prs':
          data.pullRequests = sourceResult.data as GitHubPullRequest[];
          break;
        case 'linear-incidents':
          data.incidents = sourceResult.data as LinearIssue[];
          break;
        case 'slab-postmortems':
          data.postmortems = sourceResult.data as SlabPostmortem[];
          break;
      }
    } else {
      console.error(`Fetch failed for ${fetchTasks[index].source}:`, result.reason);
    }
  });

  return data;
}

async function runMetricsWorkflow(): Promise<void> {
  console.log('Starting Engineering Metrics Workflow');
  console.log('======================================');

  const reportType = (process.env.REPORT_TYPE as 'weekly' | 'monthly') ?? 'weekly';
  console.log(`Report type: ${reportType}`);

  // Get current and previous period for trend comparison
  const currentPeriod = getPeriod(reportType);
  const previousPeriod = getPreviousPeriod(currentPeriod);

  console.log('\n--- Fetching Current Period Data ---');
  // Fetch current and previous period data in parallel
  const [currentData, previousData] = await Promise.all([
    fetchDataFromSources(currentPeriod),
    fetchDataFromSources(previousPeriod),
  ]);

  console.log('\n--- Calculating DORA Metrics ---');

  // Calculate metrics for both periods
  const currentInput: DoraCalculationInput = {
    ...currentData,
    period: currentPeriod,
  };

  const previousInput: DoraCalculationInput = {
    ...previousData,
    period: previousPeriod,
  };

  const currentMetrics = calculateDoraMetrics(currentInput);
  const previousMetrics = calculateDoraMetrics(previousInput);

  console.log('\n--- Generating Report ---');

  // Generate the report with trend comparison
  const report = generateReport({
    currentMetrics,
    previousMetrics,
  });

  // Output the markdown report
  const markdownReport = formatReportAsMarkdown(report);
  console.log('\n');
  console.log(markdownReport);

  // Send notifications
  console.log('\n--- Sending Notifications ---');
  await sendNotifications(report, {
    slackWebhookUrl: process.env.SLACK_WEBHOOK_URL,
  });

  console.log('\n======================================');
  console.log('Engineering Metrics Workflow Complete');
}

// Run the workflow
runMetricsWorkflow().catch(error => {
  console.error('Workflow failed:', error);
  process.exit(1);
});
