import type { SlabDocument, SlabPostmortem, MetricsPeriod } from '../types/index.js';

interface SlabApiResponse<T> {
  data: T[];
  hasMore: boolean;
  cursor?: string;
}

export class SlabClient {
  private apiToken: string;
  private teamId: string;
  private baseUrl = 'https://api.slab.com/v1';

  constructor(apiToken: string, teamId: string) {
    this.apiToken = apiToken;
    this.teamId = teamId;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.apiToken}`,
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`Slab API error: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<T>;
  }

  async getDocuments(period: MetricsPeriod): Promise<SlabDocument[]> {
    const documents: SlabDocument[] = [];

    try {
      const response = await this.fetch<SlabApiResponse<{
        id: string;
        title: string;
        createdAt: string;
        updatedAt: string;
        topics?: { name: string }[];
      }>>(`/teams/${this.teamId}/posts`);

      for (const doc of response.data) {
        const createdAt = new Date(doc.createdAt);
        const updatedAt = new Date(doc.updatedAt);

        if (updatedAt < period.startDate || createdAt > period.endDate) {
          continue;
        }

        const type = this.classifyDocument(doc.title, doc.topics?.map(t => t.name) ?? []);

        documents.push({
          id: doc.id,
          title: doc.title,
          createdAt,
          updatedAt,
          type,
        });
      }
    } catch (error) {
      console.warn('Failed to fetch Slab documents:', error);
    }

    return documents;
  }

  private classifyDocument(title: string, topics: string[]): SlabDocument['type'] {
    const lowerTitle = title.toLowerCase();
    const lowerTopics = topics.map(t => t.toLowerCase());

    if (
      lowerTitle.includes('postmortem') ||
      lowerTitle.includes('post-mortem') ||
      lowerTitle.includes('incident report') ||
      lowerTopics.some(t => t.includes('postmortem') || t.includes('incident'))
    ) {
      return 'postmortem';
    }

    if (
      lowerTitle.includes('runbook') ||
      lowerTitle.includes('playbook') ||
      lowerTopics.some(t => t.includes('runbook') || t.includes('on-call'))
    ) {
      return 'runbook';
    }

    if (
      lowerTitle.includes('doc') ||
      lowerTitle.includes('guide') ||
      lowerTitle.includes('how to') ||
      lowerTopics.some(t => t.includes('documentation') || t.includes('guide'))
    ) {
      return 'documentation';
    }

    return 'other';
  }

  async getPostmortems(period: MetricsPeriod): Promise<SlabPostmortem[]> {
    const documents = await this.getDocuments(period);
    const postmortems: SlabPostmortem[] = [];

    for (const doc of documents) {
      if (doc.type !== 'postmortem') continue;

      const severity = this.extractSeverity(doc.title);

      postmortems.push({
        id: doc.id,
        title: doc.title,
        incidentDate: doc.createdAt,
        resolvedAt: doc.updatedAt,
        severity,
        timeToResolve: (doc.updatedAt.getTime() - doc.createdAt.getTime()) / (1000 * 60 * 60),
      });
    }

    return postmortems;
  }

  private extractSeverity(title: string): SlabPostmortem['severity'] {
    const lowerTitle = title.toLowerCase();

    if (
      lowerTitle.includes('sev0') ||
      lowerTitle.includes('sev 0') ||
      lowerTitle.includes('critical') ||
      lowerTitle.includes('p0')
    ) {
      return 'critical';
    }

    if (
      lowerTitle.includes('sev1') ||
      lowerTitle.includes('sev 1') ||
      lowerTitle.includes('major') ||
      lowerTitle.includes('p1')
    ) {
      return 'major';
    }

    return 'minor';
  }

  async getDocumentationMetrics(period: MetricsPeriod): Promise<{
    totalDocuments: number;
    postmortems: number;
    runbooks: number;
    documentation: number;
  }> {
    const documents = await this.getDocuments(period);

    return {
      totalDocuments: documents.length,
      postmortems: documents.filter(d => d.type === 'postmortem').length,
      runbooks: documents.filter(d => d.type === 'runbook').length,
      documentation: documents.filter(d => d.type === 'documentation').length,
    };
  }
}

export function createSlabClient(): SlabClient | null {
  const apiToken = process.env.SLAB_API_TOKEN;
  const teamId = process.env.SLAB_TEAM_ID;

  if (!apiToken || !teamId) {
    console.warn('SLAB_API_TOKEN and SLAB_TEAM_ID not configured, Slab integration disabled');
    return null;
  }

  return new SlabClient(apiToken, teamId);
}
