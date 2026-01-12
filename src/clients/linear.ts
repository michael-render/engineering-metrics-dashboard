import { LinearClient as LinearSDK } from '@linear/sdk';
import type { LinearIssue, LinearCycle, MetricsPeriod } from '../types/index.js';

export class LinearClient {
  private client: LinearSDK;

  constructor(apiKey: string) {
    this.client = new LinearSDK({ apiKey });
  }

  async getCompletedIssues(period: MetricsPeriod): Promise<LinearIssue[]> {
    const issues: LinearIssue[] = [];

    const response = await this.client.issues({
      filter: {
        completedAt: {
          gte: period.startDate,
          lte: period.endDate,
        },
      },
      first: 100,
    });

    for (const issue of response.nodes) {
      const state = await issue.state;
      const assignee = await issue.assignee;
      const labels = await issue.labels();

      const startedAt = issue.startedAt ? new Date(issue.startedAt) : null;
      const completedAt = issue.completedAt ? new Date(issue.completedAt) : null;

      let cycleTime: number | undefined;
      if (startedAt && completedAt) {
        cycleTime = (completedAt.getTime() - startedAt.getTime()) / (1000 * 60 * 60);
      }

      issues.push({
        id: issue.id,
        identifier: issue.identifier,
        title: issue.title,
        state: state?.name ?? 'Unknown',
        createdAt: new Date(issue.createdAt),
        completedAt,
        startedAt,
        cycleTime,
        labels: labels.nodes.map(l => l.name),
        priority: issue.priority ?? 0,
        assignee: assignee?.name,
      });
    }

    return issues;
  }

  async getCycles(period: MetricsPeriod): Promise<LinearCycle[]> {
    const cycles: LinearCycle[] = [];

    const teams = await this.client.teams();

    for (const team of teams.nodes) {
      const teamCycles = await team.cycles({
        filter: {
          startsAt: {
            lte: period.endDate,
          },
          endsAt: {
            gte: period.startDate,
          },
        },
      });

      for (const cycle of teamCycles.nodes) {
        const issues = await cycle.issues();
        const completedIssues = issues.nodes.filter(
          i => i.completedAt !== undefined
        ).length;

        cycles.push({
          id: cycle.id,
          name: cycle.name ?? `Cycle ${cycle.number}`,
          startDate: new Date(cycle.startsAt),
          endDate: new Date(cycle.endsAt),
          completedIssues,
          totalIssues: issues.nodes.length,
        });
      }
    }

    return cycles;
  }

  async getBugIssues(period: MetricsPeriod): Promise<LinearIssue[]> {
    const issues = await this.getCompletedIssues(period);
    return issues.filter(issue =>
      issue.labels.some(label =>
        label.toLowerCase().includes('bug') ||
        label.toLowerCase().includes('incident') ||
        label.toLowerCase().includes('hotfix')
      )
    );
  }

  async getIncidentIssues(period: MetricsPeriod): Promise<LinearIssue[]> {
    const issues = await this.getCompletedIssues(period);
    return issues.filter(issue =>
      issue.labels.some(label =>
        label.toLowerCase().includes('incident') ||
        label.toLowerCase().includes('outage') ||
        label.toLowerCase().includes('p0') ||
        label.toLowerCase().includes('sev0') ||
        label.toLowerCase().includes('sev1')
      )
    );
  }

  async getVelocityMetrics(period: MetricsPeriod): Promise<{
    issuesCompleted: number;
    averageCycleTime: number;
    medianCycleTime: number;
  }> {
    const issues = await this.getCompletedIssues(period);
    const cycleTimes = issues
      .filter(i => i.cycleTime !== undefined)
      .map(i => i.cycleTime as number);

    const averageCycleTime = cycleTimes.length > 0
      ? cycleTimes.reduce((a, b) => a + b, 0) / cycleTimes.length
      : 0;

    const sortedCycleTimes = [...cycleTimes].sort((a, b) => a - b);
    const medianCycleTime = sortedCycleTimes.length > 0
      ? sortedCycleTimes[Math.floor(sortedCycleTimes.length / 2)]
      : 0;

    return {
      issuesCompleted: issues.length,
      averageCycleTime,
      medianCycleTime,
    };
  }
}

export function createLinearClient(): LinearClient {
  const apiKey = process.env.LINEAR_API_KEY;

  if (!apiKey) {
    throw new Error('LINEAR_API_KEY environment variable is required');
  }

  return new LinearClient(apiKey);
}
