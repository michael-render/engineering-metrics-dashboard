import { Octokit } from '@octokit/rest';
import type { GitHubDeployment, GitHubPullRequest, MetricsPeriod } from '../types/index.js';

export class GitHubClient {
  private octokit: Octokit;
  private org: string;

  constructor(token: string, org: string) {
    this.octokit = new Octokit({ auth: token });
    this.org = org;
  }

  async getDeployments(period: MetricsPeriod, repos?: string[]): Promise<GitHubDeployment[]> {
    const repoList = repos ?? await this.getOrgRepos();
    const deployments: GitHubDeployment[] = [];

    for (const repo of repoList) {
      try {
        const repoDeployments = await this.getRepoDeployments(repo, period);
        deployments.push(...repoDeployments);
      } catch (error) {
        console.warn(`Failed to fetch deployments for ${repo}:`, error);
      }
    }

    return deployments;
  }

  private async getRepoDeployments(repo: string, period: MetricsPeriod): Promise<GitHubDeployment[]> {
    const deployments: GitHubDeployment[] = [];

    const response = await this.octokit.repos.listDeployments({
      owner: this.org,
      repo,
      per_page: 100,
    });

    for (const deployment of response.data) {
      const createdAt = new Date(deployment.created_at);

      if (createdAt < period.startDate || createdAt > period.endDate) {
        continue;
      }

      const statuses = await this.octokit.repos.listDeploymentStatuses({
        owner: this.org,
        repo,
        deployment_id: deployment.id,
        per_page: 1,
      });

      const latestStatus = statuses.data[0];
      const status = this.mapDeploymentStatus(latestStatus?.state);

      deployments.push({
        id: deployment.id,
        sha: deployment.sha,
        ref: deployment.ref,
        environment: deployment.environment,
        createdAt,
        status,
      });
    }

    return deployments;
  }

  private mapDeploymentStatus(state?: string): GitHubDeployment['status'] {
    switch (state) {
      case 'success':
        return 'success';
      case 'failure':
      case 'error':
        return 'failure';
      case 'in_progress':
      case 'queued':
        return 'in_progress';
      default:
        return 'pending';
    }
  }

  async getPullRequests(period: MetricsPeriod, repos?: string[]): Promise<GitHubPullRequest[]> {
    const repoList = repos ?? await this.getOrgRepos();
    const pullRequests: GitHubPullRequest[] = [];

    for (const repo of repoList) {
      try {
        const repoPRs = await this.getRepoPullRequests(repo, period);
        pullRequests.push(...repoPRs);
      } catch (error) {
        console.warn(`Failed to fetch PRs for ${repo}:`, error);
      }
    }

    return pullRequests;
  }

  private async getRepoPullRequests(repo: string, period: MetricsPeriod): Promise<GitHubPullRequest[]> {
    const pullRequests: GitHubPullRequest[] = [];

    const response = await this.octokit.pulls.list({
      owner: this.org,
      repo,
      state: 'closed',
      sort: 'updated',
      direction: 'desc',
      per_page: 100,
    });

    for (const pr of response.data) {
      if (!pr.merged_at) continue;

      const mergedAt = new Date(pr.merged_at);
      if (mergedAt < period.startDate || mergedAt > period.endDate) {
        continue;
      }

      const prDetails = await this.octokit.pulls.get({
        owner: this.org,
        repo,
        pull_number: pr.number,
      });

      const commits = await this.octokit.pulls.listCommits({
        owner: this.org,
        repo,
        pull_number: pr.number,
        per_page: 1,
      });

      const firstCommitAt = commits.data[0]
        ? new Date(commits.data[0].commit.committer?.date ?? pr.created_at)
        : undefined;

      pullRequests.push({
        number: pr.number,
        title: pr.title,
        createdAt: new Date(pr.created_at),
        mergedAt,
        closedAt: pr.closed_at ? new Date(pr.closed_at) : null,
        state: 'merged',
        commits: prDetails.data.commits,
        additions: prDetails.data.additions,
        deletions: prDetails.data.deletions,
        firstCommitAt,
      });
    }

    return pullRequests;
  }

  async getOrgRepos(): Promise<string[]> {
    const response = await this.octokit.repos.listForOrg({
      org: this.org,
      type: 'all',
      per_page: 100,
    });

    return response.data
      .filter(repo => !repo.archived)
      .map(repo => repo.name);
  }

  async getWorkflowRuns(period: MetricsPeriod, repos?: string[]): Promise<{ repo: string; success: number; failure: number }[]> {
    const repoList = repos ?? await this.getOrgRepos();
    const results: { repo: string; success: number; failure: number }[] = [];

    for (const repo of repoList) {
      try {
        const runs = await this.octokit.actions.listWorkflowRunsForRepo({
          owner: this.org,
          repo,
          created: `${period.startDate.toISOString()}..${period.endDate.toISOString()}`,
          per_page: 100,
        });

        const success = runs.data.workflow_runs.filter(r => r.conclusion === 'success').length;
        const failure = runs.data.workflow_runs.filter(r => r.conclusion === 'failure').length;

        results.push({ repo, success, failure });
      } catch (error) {
        console.warn(`Failed to fetch workflow runs for ${repo}:`, error);
      }
    }

    return results;
  }
}

export function createGitHubClient(): GitHubClient {
  const token = process.env.GITHUB_TOKEN;
  const org = process.env.GITHUB_ORG;

  if (!token || !org) {
    throw new Error('GITHUB_TOKEN and GITHUB_ORG environment variables are required');
  }

  return new GitHubClient(token, org);
}
