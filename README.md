# Engineering Metrics Dashboard

Automated DORA metrics calculation and reporting using **[Render Workflows](https://render.com/docs/workflows)**. Pulls data from Linear, GitHub, and Slab to generate weekly and monthly executive reports with parallel data fetching.

## Render Workflows

This project uses the Render Workflows SDK to run data fetching tasks in parallel across separate compute instances. Each `@task` decorated function runs independently, and `asyncio.gather()` coordinates parallel execution of subtasks.

```python
from render_sdk.workflows import task

@task
async def fetch_github_deployments(period: dict) -> list[dict]:
    """Runs in its own compute instance."""
    ...

@task
async def run_metrics_pipeline(period_type: str) -> str:
    """Orchestrates parallel fetch tasks."""
    # All four fetches run IN PARALLEL - each in its own compute instance
    results = await asyncio.gather(
        fetch_github_deployments(period),
        fetch_github_pull_requests(period),
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
│  │           run_metrics_pipeline (orchestrator)               │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                    │
│              asyncio.gather() - PARALLEL EXECUTION               │
│     ┌───────────┬───────────┼───────────┬───────────┐           │
│     ▼           ▼           ▼           ▼                       │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                    │
│ │ GitHub │ │ GitHub │ │ Linear │ │  Slab  │  ← Each runs in    │
│ │Deploys │ │  PRs   │ │Incidents│ │Postmort│    its own compute │
│ │ @task  │ │ @task  │ │ @task  │ │ @task  │    instance         │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘                    │
│      └──────────┴──────────┴──────────┘                         │
│                      │                                           │
│         ┌────────────▼────────────┐                             │
│         │   calculate_metrics     │                             │
│         │        @task            │                             │
│         └────────────┬────────────┘                             │
│                      │                                           │
│         ┌────────────▼────────────┐                             │
│         │  generate_and_notify    │                             │
│         │        @task            │                             │
│         └────────────┬────────────┘                             │
│                      │                                           │
│              ┌───────┴───────┐                                  │
│              ▼               ▼                                  │
│         ┌─────────┐    ┌──────────┐                            │
│         │  Slack  │    │ Console  │                            │
│         │ Webhook │    │  Output  │                            │
│         └─────────┘    └──────────┘                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

- **GitHub**: Deployments, pull requests
- **Linear**: Issues tagged as incidents/bugs
- **Slab**: Postmortem documents (optional)

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/michael-render/engineering-metrics-dashboard.git
cd engineering-metrics-dashboard
pip install -r requirements.txt
```

### 2. Deploy the Workflow to Render

Render Workflows are created via the Dashboard (not via render.yaml):

1. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Workflow**
2. Link this GitHub repository
3. Configure:
   - **Language**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
4. Set environment variables:
   - `LINEAR_API_KEY` - Linear API key
   - `GITHUB_TOKEN` - GitHub personal access token
   - `GITHUB_ORG` - GitHub organization name
   - `SLAB_API_TOKEN` - (optional) Slab API token
   - `SLAB_TEAM_ID` - (optional) Slab team ID
   - `SLACK_WEBHOOK_URL` - (optional) Slack webhook
5. Click **Deploy Workflow**

### 3. Run the Workflow

After deployment, you can run the workflow:

**Via Dashboard:**
1. Go to your workflow's **Tasks** page
2. Select `run_metrics_pipeline`
3. Click **Run Task**
4. Enter arguments: `["weekly"]` or `["monthly"]`

**Via API/SDK:**
```python
from render_sdk.client import Client

async with Client() as client:
    task_run = await client.workflows.run_task(
        "engineering-metrics-dashboard/run_metrics_pipeline",
        ["weekly"]
    )
    result = await task_run
    print(result.output)
```

### 4. Schedule Regular Reports (Optional)

Deploy the cron jobs from `render.yaml` to trigger the workflow on a schedule:

1. Go to Render Dashboard → **Blueprints**
2. Connect this repository
3. Set environment variables:
   - `RENDER_API_KEY` - Your Render API key
   - `WORKFLOW_SERVICE_ID` - Your workflow's service slug

## Local Development

Use the [Render CLI](https://render.com/docs/cli) for local testing:

```bash
# Install Render CLI
brew install render

# Start local task server
render workflows dev --start-command "python main.py"

# In another terminal, run a task
render workflows run run_metrics_pipeline --input '["weekly"]'
```

## Project Structure

```
engineering-metrics-dashboard/
├── main.py                    # Entry point - calls start()
├── metrics_dashboard/
│   ├── __init__.py
│   ├── tasks.py               # Render Workflow @task definitions
│   ├── clients.py             # API clients (GitHub, Linear, Slab)
│   ├── dora.py                # DORA metrics calculation
│   ├── models.py              # Pydantic data models
│   └── reports.py             # Report generation
├── scripts/
│   └── trigger_workflow.py    # Script to trigger workflow via API
├── render.yaml                # Cron jobs for scheduled triggers
├── requirements.txt
└── pyproject.toml
```

## Workflow Tasks

| Task | Description | Parallel |
|------|-------------|----------|
| `fetch_github_deployments` | Fetches deployment data from GitHub | ✅ |
| `fetch_github_pull_requests` | Fetches merged PRs from GitHub | ✅ |
| `fetch_linear_incidents` | Fetches incident issues from Linear | ✅ |
| `fetch_slab_postmortems` | Fetches postmortems from Slab | ✅ |
| `calculate_metrics` | Computes DORA metrics from data | ❌ |
| `generate_and_notify` | Generates report, sends Slack | ❌ |
| `run_metrics_pipeline` | **Orchestrator** - coordinates all tasks | - |

## Customization

### Custom Incident Labels

Edit `metrics_dashboard/clients.py`:

```python
async def get_incident_issues(self, period: MetricsPeriod) -> list[LinearIssue]:
    issues = await self.get_completed_issues(period)
    incident_labels = {"bug", "incident", "your-custom-label"}
    return [i for i in issues if any(l.lower() in incident_labels for l in i.labels)]
```

## Resources

- [Render Workflows Documentation](https://render.com/docs/workflows)
- [Workflows SDK for Python](https://render.com/docs/workflows-sdk-python)
- [Your First Workflow Tutorial](https://render.com/docs/workflows-tutorial)
- [Render Workflows Examples](https://github.com/render-examples/render-workflows-examples)

## License

MIT
