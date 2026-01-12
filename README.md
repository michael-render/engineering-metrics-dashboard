# Engineering Metrics Dashboard

Automated DORA metrics calculation and reporting using Render Workflows. Pulls data from Linear, GitHub, and Slab to generate weekly and monthly executive reports.

## DORA Metrics

This dashboard calculates the four key DORA (DevOps Research and Assessment) metrics:

| Metric | Description | Elite | High | Medium | Low |
|--------|-------------|-------|------|--------|-----|
| **Deployment Frequency** | How often code is deployed to production | Multiple/day | Daily-Weekly | Weekly-Monthly | < Monthly |
| **Lead Time for Changes** | Time from first commit to production | < 1 hour | < 1 day | < 1 week | > 1 week |
| **Change Failure Rate** | Percentage of deployments causing failures | 0-5% | 5-10% | 10-15% | > 15% |
| **Mean Time to Recovery** | Time to restore service after an incident | < 1 hour | < 1 day | < 1 week | > 1 week |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Render Workflows                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  GitHub  │  │  Linear  │  │   Slab   │  │ Previous │        │
│  │ API Fetch│  │ API Fetch│  │ API Fetch│  │  Period  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴─────────────┴─────────────┘               │
│                           │                                      │
│              ┌────────────▼────────────┐                        │
│              │   DORA Metrics Calc     │                        │
│              └────────────┬────────────┘                        │
│                           │                                      │
│              ┌────────────▼────────────┐                        │
│              │   Report Generation     │                        │
│              └────────────┬────────────┘                        │
│                           │                                      │
│       ┌───────────────────┼───────────────────┐                 │
│       ▼                   ▼                   ▼                 │
│  ┌─────────┐        ┌──────────┐        ┌──────────┐           │
│  │  Slack  │        │  Console │        │   API    │           │
│  │ Webhook │        │  Output  │        │ Endpoint │           │
│  └─────────┘        └──────────┘        └──────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

- **GitHub**: Deployments, pull requests, workflow runs
- **Linear**: Issues, cycles, incidents (tagged issues)
- **Slab**: Postmortems, runbooks (optional)

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/your-org/engineering-metrics-dashboard.git
cd engineering-metrics-dashboard
npm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

Required variables:
- `LINEAR_API_KEY` - Linear API key
- `GITHUB_TOKEN` - GitHub personal access token with repo access
- `GITHUB_ORG` - GitHub organization name

Optional:
- `SLAB_API_TOKEN` - Slab API token
- `SLAB_TEAM_ID` - Slab team ID
- `SLACK_WEBHOOK_URL` - Slack webhook for notifications

### 3. Deploy to Render

This project includes a `render.yaml` blueprint for easy deployment:

1. Connect your GitHub repository to Render
2. Create a new Blueprint instance
3. Configure environment variables in the Render dashboard
4. The cron jobs will automatically run on schedule

## Usage

### Run Locally

```bash
# Build
npm run build

# Run weekly report
REPORT_TYPE=weekly npm run workflow

# Run monthly report
REPORT_TYPE=monthly npm run workflow

# Start API server
npm start
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /metrics/weekly` | Weekly DORA metrics (JSON) |
| `GET /metrics/monthly` | Monthly DORA metrics (JSON) |
| `GET /report/weekly` | Weekly report (Markdown) |
| `GET /report/monthly` | Monthly report (Markdown) |

## Render Services

The `render.yaml` blueprint deploys:

1. **Weekly Metrics Cron** - Runs every Monday at 9 AM
2. **Monthly Metrics Cron** - Runs on the 1st of each month at 9 AM
3. **Metrics Dashboard API** - Optional web service for on-demand reports

## Parallel Processing

The workflow uses `.map()` with `Promise.allSettled()` to fetch data from all sources concurrently:

```typescript
const results = await Promise.allSettled(
  fetchTasks.map(async (task) => {
    const data = await task.fetch();
    return { source: task.source, data };
  })
);
```

This maximizes throughput when running on Render Workflows.

## Customization

### Adding Custom Labels for Incidents

Modify `src/clients/linear.ts` to recognize your team's incident labels:

```typescript
async getIncidentIssues(period: MetricsPeriod): Promise<LinearIssue[]> {
  const issues = await this.getCompletedIssues(period);
  return issues.filter(issue =>
    issue.labels.some(label =>
      label.toLowerCase().includes('your-custom-label')
    )
  );
}
```

### Custom Report Sections

Extend `src/reports/generator.ts` to add custom sections to your reports.

## License

MIT
