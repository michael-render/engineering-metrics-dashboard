// DORA Metrics Types
export interface DoraMetrics {
  deploymentFrequency: DeploymentFrequency;
  leadTime: LeadTime;
  changeFailureRate: ChangeFailureRate;
  mttr: MTTR;
  period: MetricsPeriod;
  generatedAt: Date;
}

export interface DeploymentFrequency {
  deploymentsPerDay: number;
  deploymentsPerWeek: number;
  totalDeployments: number;
  rating: DoraRating;
}

export interface LeadTime {
  averageHours: number;
  medianHours: number;
  p90Hours: number;
  rating: DoraRating;
}

export interface ChangeFailureRate {
  percentage: number;
  failedDeployments: number;
  totalDeployments: number;
  rating: DoraRating;
}

export interface MTTR {
  averageHours: number;
  medianHours: number;
  incidents: number;
  rating: DoraRating;
}

export type DoraRating = 'elite' | 'high' | 'medium' | 'low';

export interface MetricsPeriod {
  type: 'weekly' | 'monthly';
  startDate: Date;
  endDate: Date;
}

// Data Source Types
export interface DataSourceResult<T> {
  source: 'linear' | 'github' | 'slab';
  data: T;
  fetchedAt: Date;
  error?: string;
}

// GitHub Types
export interface GitHubDeployment {
  id: number;
  sha: string;
  ref: string;
  environment: string;
  createdAt: Date;
  status: 'success' | 'failure' | 'pending' | 'in_progress';
  prNumber?: number;
  prMergedAt?: Date;
}

export interface GitHubPullRequest {
  number: number;
  title: string;
  createdAt: Date;
  mergedAt: Date | null;
  closedAt: Date | null;
  state: 'open' | 'closed' | 'merged';
  commits: number;
  additions: number;
  deletions: number;
  firstCommitAt?: Date;
}

// Linear Types
export interface LinearIssue {
  id: string;
  identifier: string;
  title: string;
  state: string;
  createdAt: Date;
  completedAt: Date | null;
  startedAt: Date | null;
  cycleTime?: number;
  labels: string[];
  priority: number;
  assignee?: string;
}

export interface LinearCycle {
  id: string;
  name: string;
  startDate: Date;
  endDate: Date;
  completedIssues: number;
  totalIssues: number;
}

// Slab Types
export interface SlabDocument {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  type: 'postmortem' | 'runbook' | 'documentation' | 'other';
}

export interface SlabPostmortem {
  id: string;
  title: string;
  incidentDate: Date;
  resolvedAt: Date;
  severity: 'critical' | 'major' | 'minor';
  timeToResolve: number;
}

// Report Types
export interface MetricsReport {
  title: string;
  period: MetricsPeriod;
  metrics: DoraMetrics;
  trends: MetricsTrends;
  highlights: string[];
  recommendations: string[];
  generatedAt: Date;
}

export interface MetricsTrends {
  deploymentFrequencyChange: number;
  leadTimeChange: number;
  changeFailureRateChange: number;
  mttrChange: number;
}

// Workflow Types
export interface WorkflowConfig {
  reportType: 'weekly' | 'monthly';
  dataSources: ('linear' | 'github' | 'slab')[];
  notifications: NotificationConfig;
}

export interface NotificationConfig {
  slack?: {
    webhookUrl: string;
    channel?: string;
  };
  email?: {
    recipients: string[];
  };
}

// API Client Configuration
export interface ClientConfig {
  linear?: {
    apiKey: string;
  };
  github?: {
    token: string;
    org: string;
    repos?: string[];
  };
  slab?: {
    apiToken: string;
    teamId: string;
  };
}
