import { differenceInDays, differenceInHours } from 'date-fns';
import type {
  DoraMetrics,
  DeploymentFrequency,
  LeadTime,
  ChangeFailureRate,
  MTTR,
  DoraRating,
  MetricsPeriod,
  GitHubDeployment,
  GitHubPullRequest,
  LinearIssue,
  SlabPostmortem,
} from '../types/index.js';

export interface DoraCalculationInput {
  deployments: GitHubDeployment[];
  pullRequests: GitHubPullRequest[];
  incidents: LinearIssue[];
  postmortems: SlabPostmortem[];
  period: MetricsPeriod;
}

export function calculateDoraMetrics(input: DoraCalculationInput): DoraMetrics {
  const { deployments, pullRequests, incidents, postmortems, period } = input;

  return {
    deploymentFrequency: calculateDeploymentFrequency(deployments, period),
    leadTime: calculateLeadTime(pullRequests),
    changeFailureRate: calculateChangeFailureRate(deployments, incidents),
    mttr: calculateMTTR(incidents, postmortems),
    period,
    generatedAt: new Date(),
  };
}

function calculateDeploymentFrequency(
  deployments: GitHubDeployment[],
  period: MetricsPeriod
): DeploymentFrequency {
  const successfulDeployments = deployments.filter(d => d.status === 'success');
  const totalDeployments = successfulDeployments.length;

  const days = differenceInDays(period.endDate, period.startDate) || 1;
  const deploymentsPerDay = totalDeployments / days;
  const deploymentsPerWeek = deploymentsPerDay * 7;

  const rating = getDeploymentFrequencyRating(deploymentsPerDay);

  return {
    deploymentsPerDay,
    deploymentsPerWeek,
    totalDeployments,
    rating,
  };
}

function getDeploymentFrequencyRating(deploymentsPerDay: number): DoraRating {
  // Elite: Multiple deploys per day
  if (deploymentsPerDay >= 1) return 'elite';
  // High: Between once per day and once per week
  if (deploymentsPerDay >= 1 / 7) return 'high';
  // Medium: Between once per week and once per month
  if (deploymentsPerDay >= 1 / 30) return 'medium';
  // Low: Less than once per month
  return 'low';
}

function calculateLeadTime(pullRequests: GitHubPullRequest[]): LeadTime {
  const leadTimes: number[] = [];

  for (const pr of pullRequests) {
    if (!pr.mergedAt) continue;

    const startTime = pr.firstCommitAt ?? pr.createdAt;
    const hours = differenceInHours(pr.mergedAt, startTime);
    leadTimes.push(hours);
  }

  if (leadTimes.length === 0) {
    return {
      averageHours: 0,
      medianHours: 0,
      p90Hours: 0,
      rating: 'low',
    };
  }

  const sortedLeadTimes = [...leadTimes].sort((a, b) => a - b);
  const averageHours = leadTimes.reduce((a, b) => a + b, 0) / leadTimes.length;
  const medianHours = sortedLeadTimes[Math.floor(sortedLeadTimes.length / 2)];
  const p90Index = Math.floor(sortedLeadTimes.length * 0.9);
  const p90Hours = sortedLeadTimes[p90Index] ?? medianHours;

  const rating = getLeadTimeRating(medianHours);

  return {
    averageHours,
    medianHours,
    p90Hours,
    rating,
  };
}

function getLeadTimeRating(medianHours: number): DoraRating {
  // Elite: Less than one hour
  if (medianHours < 1) return 'elite';
  // High: Less than one day
  if (medianHours < 24) return 'high';
  // Medium: Less than one week
  if (medianHours < 168) return 'medium';
  // Low: More than one week
  return 'low';
}

function calculateChangeFailureRate(
  deployments: GitHubDeployment[],
  incidents: LinearIssue[]
): ChangeFailureRate {
  const successfulDeployments = deployments.filter(d => d.status === 'success');
  const failedDeployments = deployments.filter(d => d.status === 'failure');
  const totalDeployments = successfulDeployments.length + failedDeployments.length;

  // Count incidents that occurred after deployments as change failures
  const deploymentFailures = failedDeployments.length + incidents.length;

  const percentage = totalDeployments > 0
    ? (deploymentFailures / totalDeployments) * 100
    : 0;

  const rating = getChangeFailureRateRating(percentage);

  return {
    percentage,
    failedDeployments: deploymentFailures,
    totalDeployments,
    rating,
  };
}

function getChangeFailureRateRating(percentage: number): DoraRating {
  // Elite: 0-5%
  if (percentage <= 5) return 'elite';
  // High: 5-10%
  if (percentage <= 10) return 'high';
  // Medium: 10-15%
  if (percentage <= 15) return 'medium';
  // Low: More than 15%
  return 'low';
}

function calculateMTTR(
  incidents: LinearIssue[],
  postmortems: SlabPostmortem[]
): MTTR {
  const resolutionTimes: number[] = [];

  // Use incident cycle times from Linear
  for (const incident of incidents) {
    if (incident.cycleTime !== undefined) {
      resolutionTimes.push(incident.cycleTime);
    }
  }

  // Also use postmortem resolution times from Slab
  for (const postmortem of postmortems) {
    resolutionTimes.push(postmortem.timeToResolve);
  }

  if (resolutionTimes.length === 0) {
    return {
      averageHours: 0,
      medianHours: 0,
      incidents: 0,
      rating: 'elite', // No incidents is elite
    };
  }

  const sortedTimes = [...resolutionTimes].sort((a, b) => a - b);
  const averageHours = resolutionTimes.reduce((a, b) => a + b, 0) / resolutionTimes.length;
  const medianHours = sortedTimes[Math.floor(sortedTimes.length / 2)];

  const rating = getMTTRRating(medianHours);

  return {
    averageHours,
    medianHours,
    incidents: incidents.length + postmortems.length,
    rating,
  };
}

function getMTTRRating(medianHours: number): DoraRating {
  // Elite: Less than one hour
  if (medianHours < 1) return 'elite';
  // High: Less than one day
  if (medianHours < 24) return 'high';
  // Medium: Less than one week
  if (medianHours < 168) return 'medium';
  // Low: More than one week
  return 'low';
}

export function getOverallRating(metrics: DoraMetrics): DoraRating {
  const ratings = [
    metrics.deploymentFrequency.rating,
    metrics.leadTime.rating,
    metrics.changeFailureRate.rating,
    metrics.mttr.rating,
  ];

  const ratingValues: Record<DoraRating, number> = {
    elite: 4,
    high: 3,
    medium: 2,
    low: 1,
  };

  const averageValue = ratings.reduce((sum, r) => sum + ratingValues[r], 0) / ratings.length;

  if (averageValue >= 3.5) return 'elite';
  if (averageValue >= 2.5) return 'high';
  if (averageValue >= 1.5) return 'medium';
  return 'low';
}

export function formatRating(rating: DoraRating): string {
  const labels: Record<DoraRating, string> = {
    elite: 'Elite Performer',
    high: 'High Performer',
    medium: 'Medium Performer',
    low: 'Low Performer',
  };
  return labels[rating];
}
