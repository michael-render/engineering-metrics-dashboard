# Engineering Metrics Dashboard

Automated DORA metrics calculation and reporting using **Render Workflows**. Pulls data from Linear, GitHub, and Slab to generate weekly and monthly executive reports with parallel data fetching.

## Render Workflows

This project uses [Render Workflows](https://render.com/docs/workflows) to run data fetching tasks in parallel across separate compute instances. Each `@task` decorated function runs independently, and `asyncio.gather()` coordinates parallel execution.

```python
from render_sdk.workflows import task, start

@task
async def fetch_github_deployments(period: dict) -> list[dict]:
    """Runs in its own compute instance."""
    ...

@task
async def run_metrics_workflow(period_type: str) -> str:
    """Orchestrates parallel fetch tasks."""
    # All four fetches run in parallel
    results = await asyncio.gather(
        fetch_github_deployments(period),
        fetch_github_prs(period),
        fetch_linear_incidents(period),
        fetch_slab_postmortems(period),
    )
    ...
```

## DORA Metrics

This dashboard calculates the four key DORA (DevOps Research and Assessment) metrics:

| Metric | Description | Elite | High | Medium | Low |
|--------|-------------|-------|------|--------|-----|
| **Deployment Frequency** | How often code is deployed | Multiple/day | Daily-Weekly | Weekly-Monthly | < Monthly |
| **Lead Time for Changes** | Time from commit to production | < 1 hour | < 1 day | < 1 week | > 1 week |
| **Change Failure Rate** | % of deployments causing failures | 0-5% | 5-10% | 10-15% | > 15% |
| **Mean Time to Recovery** | Time to restore service | < 1 hour | < 1 day | < 1 week | > 1 week |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Render Workflows                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              run_metrics_workflow (orchestrator)            │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                    │
│              asyncio.gather() - PARALLEL EXECUTION               │
│     ┌───────────┬───────────┼───────────┬───────────┐           │
│     ▼           ▼           ▼           ▼           │           │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │           │
│ │ GitHub │ │ GitHub │ │ Linear │ │  Slab  │        │           │
│ │Deploys │ │  PRs   │ │Incidents│ │Postmort│        │           │
│ │ @task  │ │ @task  │ │ @task  │ │ @task  │        │           │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘        │           │
│      │          │          │          │             │           │
│      └──────────┴──────────┴──────────┘             │           │
│                      │                               │           │
│         ┌────────────▼────────────┐                 │           │
│         │ aggregate_and_calculate │                 │           │
│         │        @task            │                 │           │
│         └────────────┬────────────┘                 │           │
│                      │                               │           │
│         ┌────────────▼────────────┐                 │           │
│         │ generate_and_send_report│                 │           │
│         │        @task            │                 │           │
│         └────────────┬────────────┘                 │           │
│                      │                               │           │
│              ┌───────┴───────┐                      │           │
│              ▼               ▼                      │           │
│         ┌─────────┐    ┌──────────┐                │           │
│         │  Slack  │    │ Console  │                │           │
│         │ Webhook │    │  Output  │                │           │
│         └─────────┘    └──────────┘                │           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

- **GitHub**: Deployments, pull requests, workflow runs
- **Linear**: Issues, cycles, incidents (tagged issues)
- **Slab**: Postmortem documents (optional)

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/michael-render/engineering-metrics-dashboard.git
cd engineering-metrics-dashboard
pip install -r requirements.txt
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

This project includes a `render.yaml` blueprint for deployment:

1. Connect your GitHub repository to Render
2. Create a new Blueprint instance
3. Configure environment variables in the Render dashboard
4. The workflows will be ready to run

## Usage

### Run Locally

```bash
# Run weekly report
REPORT_TYPE=weekly python -m metrics_dashboard.workflow

# Run monthly report
REPORT_TYPE=monthly python -m metrics_dashboard.workflow
```

### Programmatic Usage

```python
from metrics_dashboard import calculate_dora_metrics, DoraMetrics
from metrics_dashboard.models import DataFetchResult, MetricsPeriod

# Create your data
data = DataFetchResult(
    deployments=[...],
    pull_requests=[...],
    incidents=[...],
    postmortems=[...],
)

period = MetricsPeriod(
    type="weekly",
    start_date=start,
    end_date=end,
)

# Calculate metrics
metrics: DoraMetrics = calculate_dora_metrics(data, period)
print(f"Deployment frequency: {metrics.deployment_frequency.deployments_per_day}/day")
```

## Project Structure

```
engineering-metrics-dashboard/
├── metrics_dashboard/
│   ├── __init__.py          # Package exports
│   ├── models.py             # Pydantic data models
│   ├── clients.py            # API clients (GitHub, Linear, Slab)
│   ├── dora.py               # DORA metrics calculation
│   ├── reports.py            # Report generation & formatting
│   └── workflow.py           # Render Workflows tasks
├── tests/
├── render.yaml               # Render deployment blueprint
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Render Workflow Tasks

| Task | Description | Runs In Parallel |
|------|-------------|------------------|
| `fetch_github_deployments` | Fetches deployment data from GitHub | Yes |
| `fetch_github_prs` | Fetches merged PRs from GitHub | Yes |
| `fetch_linear_incidents` | Fetches incident issues from Linear | Yes |
| `fetch_slab_postmortems` | Fetches postmortems from Slab | Yes |
| `aggregate_and_calculate` | Combines data and calculates metrics | No (waits for fetches) |
| `generate_and_send_report` | Generates report and sends notifications | No |

## Customization

### Custom Incident Labels

Modify `metrics_dashboard/clients.py` to recognize your team's incident labels:

```python
async def get_incident_issues(self, period: MetricsPeriod) -> list[LinearIssue]:
    issues = await self.get_completed_issues(period)
    incident_labels = {"bug", "incident", "your-custom-label"}
    return [i for i in issues if any(l.lower() in incident_labels for l in i.labels)]
```

### Custom Report Sections

Extend `metrics_dashboard/reports.py` to add custom sections to your reports.

## License

MIT
