"""API clients for data sources."""

import os
from datetime import datetime, timezone

import httpx

from metrics_dashboard.models import (
    GitHubDeployment,
    GitHubPullRequest,
    LinearIssue,
    MetricsPeriod,
    SlabPostmortem,
)


class GitHubClient:
    """Client for GitHub API."""

    def __init__(self, token: str, org: str):
        self.token = token
        self.org = org
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_repos(self) -> list[str]:
        """Get all non-archived repos in the organization."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orgs/{self.org}/repos",
                headers=self.headers,
                params={"type": "all", "per_page": 100},
            )
            response.raise_for_status()
            repos = response.json()
            return [r["name"] for r in repos if not r.get("archived", False)]

    async def get_deployments(
        self, repo: str, period: MetricsPeriod
    ) -> list[GitHubDeployment]:
        """Get deployments for a repository within the period."""
        deployments: list[GitHubDeployment] = []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{self.org}/{repo}/deployments",
                headers=self.headers,
                params={"per_page": 100},
            )
            response.raise_for_status()

            for dep in response.json():
                created_at = datetime.fromisoformat(dep["created_at"].replace("Z", "+00:00"))

                if created_at < period.start_date or created_at > period.end_date:
                    continue

                # Get latest status
                status_response = await client.get(
                    f"{self.base_url}/repos/{self.org}/{repo}/deployments/{dep['id']}/statuses",
                    headers=self.headers,
                    params={"per_page": 1},
                )
                status_response.raise_for_status()
                statuses = status_response.json()

                status = "pending"
                if statuses:
                    state = statuses[0].get("state", "pending")
                    if state == "success":
                        status = "success"
                    elif state in ("failure", "error"):
                        status = "failure"
                    elif state in ("in_progress", "queued"):
                        status = "in_progress"

                deployments.append(
                    GitHubDeployment(
                        id=dep["id"],
                        sha=dep["sha"],
                        ref=dep["ref"],
                        environment=dep["environment"],
                        created_at=created_at,
                        status=status,
                    )
                )

        return deployments

    async def get_pull_requests(
        self, repo: str, period: MetricsPeriod
    ) -> list[GitHubPullRequest]:
        """Get merged pull requests for a repository within the period."""
        pull_requests: list[GitHubPullRequest] = []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{self.org}/{repo}/pulls",
                headers=self.headers,
                params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 100},
            )
            response.raise_for_status()

            for pr in response.json():
                if not pr.get("merged_at"):
                    continue

                merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                if merged_at < period.start_date or merged_at > period.end_date:
                    continue

                created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))

                # Get first commit date
                commits_response = await client.get(
                    f"{self.base_url}/repos/{self.org}/{repo}/pulls/{pr['number']}/commits",
                    headers=self.headers,
                    params={"per_page": 1},
                )
                commits_response.raise_for_status()
                commits = commits_response.json()

                first_commit_at = None
                if commits:
                    commit_date = commits[0].get("commit", {}).get("committer", {}).get("date")
                    if commit_date:
                        first_commit_at = datetime.fromisoformat(
                            commit_date.replace("Z", "+00:00")
                        )

                pull_requests.append(
                    GitHubPullRequest(
                        number=pr["number"],
                        title=pr["title"],
                        created_at=created_at,
                        merged_at=merged_at,
                        first_commit_at=first_commit_at,
                    )
                )

        return pull_requests


class LinearClient:
    """Client for Linear API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    def _format_date(self, dt: datetime) -> str:
        """Format datetime for Linear API (ISO 8601 with Z suffix)."""
        # Linear expects format like "2024-01-01T00:00:00.000Z"
        if dt.tzinfo is not None:
            # Convert to UTC and format
            utc_dt = dt.astimezone(timezone.utc)
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    async def get_completed_issues(self, period: MetricsPeriod) -> list[LinearIssue]:
        """Get issues completed within the period."""
        # Note: Linear API uses DateTimeOrDuration type for date filters
        # We pass the dates directly in the filter without variables
        after_date = self._format_date(period.start_date)
        before_date = self._format_date(period.end_date)

        query = f"""
        query CompletedIssues {{
            issues(
                filter: {{
                    completedAt: {{ gte: "{after_date}", lte: "{before_date}" }}
                }}
                first: 100
            ) {{
                nodes {{
                    id
                    identifier
                    title
                    createdAt
                    completedAt
                    startedAt
                    state {{ name }}
                    labels {{ nodes {{ name }} }}
                }}
            }}
        }}
        """

        variables = {}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=self.headers,
                json={"query": query, "variables": variables},
            )

            # Check for GraphQL errors before raising HTTP errors
            if response.status_code == 400:
                error_data = response.json()
                errors = error_data.get("errors", [])
                if errors:
                    error_msg = "; ".join(e.get("message", str(e)) for e in errors)
                    raise ValueError(f"Linear API error: {error_msg}")

            response.raise_for_status()
            data = response.json()

            # Check for GraphQL errors in successful response
            if "errors" in data:
                error_msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
                raise ValueError(f"Linear GraphQL error: {error_msg}")

        issues: list[LinearIssue] = []
        for node in data.get("data", {}).get("issues", {}).get("nodes", []):
            created_at = datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00"))
            completed_at = None
            started_at = None
            cycle_time_hours = None

            if node.get("completedAt"):
                completed_at = datetime.fromisoformat(node["completedAt"].replace("Z", "+00:00"))
            if node.get("startedAt"):
                started_at = datetime.fromisoformat(node["startedAt"].replace("Z", "+00:00"))

            if started_at and completed_at:
                cycle_time_hours = (completed_at - started_at).total_seconds() / 3600

            labels = [label["name"] for label in node.get("labels", {}).get("nodes", [])]

            issues.append(
                LinearIssue(
                    id=node["id"],
                    identifier=node["identifier"],
                    title=node["title"],
                    state=node.get("state", {}).get("name", "Unknown"),
                    created_at=created_at,
                    completed_at=completed_at,
                    started_at=started_at,
                    cycle_time_hours=cycle_time_hours,
                    labels=labels,
                )
            )

        return issues

    async def get_incident_issues(self, period: MetricsPeriod) -> list[LinearIssue]:
        """Get incident-related issues within the period."""
        issues = await self.get_completed_issues(period)
        incident_labels = {"bug", "incident", "outage", "hotfix", "p0", "sev0", "sev1"}

        return [
            issue
            for issue in issues
            if any(label.lower() in incident_labels for label in issue.labels)
        ]


class SlabClient:
    """Client for Slab API."""

    def __init__(self, api_token: str, team_id: str):
        self.api_token = api_token
        self.team_id = team_id
        self.base_url = "https://api.slab.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def get_postmortems(self, period: MetricsPeriod) -> list[SlabPostmortem]:
        """Get postmortem documents within the period."""
        postmortems: list[SlabPostmortem] = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/teams/{self.team_id}/posts",
                    headers=self.headers,
                )
                response.raise_for_status()
                documents = response.json().get("data", [])

                for doc in documents:
                    title = doc.get("title", "").lower()

                    if "postmortem" not in title and "post-mortem" not in title:
                        continue

                    created_at = datetime.fromisoformat(
                        doc["createdAt"].replace("Z", "+00:00")
                    )
                    updated_at = datetime.fromisoformat(
                        doc["updatedAt"].replace("Z", "+00:00")
                    )

                    if updated_at < period.start_date or created_at > period.end_date:
                        continue

                    # Extract severity from title
                    severity = "minor"
                    if any(s in title for s in ["sev0", "sev 0", "critical", "p0"]):
                        severity = "critical"
                    elif any(s in title for s in ["sev1", "sev 1", "major", "p1"]):
                        severity = "major"

                    time_to_resolve = (updated_at - created_at).total_seconds() / 3600

                    postmortems.append(
                        SlabPostmortem(
                            id=doc["id"],
                            title=doc["title"],
                            incident_date=created_at,
                            resolved_at=updated_at,
                            severity=severity,
                            time_to_resolve_hours=time_to_resolve,
                        )
                    )

        except httpx.HTTPError as e:
            print(f"Warning: Failed to fetch Slab postmortems: {e}")

        return postmortems


def create_github_client() -> GitHubClient:
    """Create GitHub client from environment variables."""
    token = os.environ.get("GITHUB_TOKEN")
    org = os.environ.get("GITHUB_ORG")

    if not token or not org:
        raise ValueError("GITHUB_TOKEN and GITHUB_ORG environment variables are required")

    return GitHubClient(token, org)


def create_linear_client() -> LinearClient:
    """Create Linear client from environment variables."""
    api_key = os.environ.get("LINEAR_API_KEY")

    if not api_key:
        raise ValueError("LINEAR_API_KEY environment variable is required")

    return LinearClient(api_key)


def create_slab_client() -> SlabClient | None:
    """Create Slab client from environment variables."""
    api_token = os.environ.get("SLAB_API_TOKEN")
    team_id = os.environ.get("SLAB_TEAM_ID")

    if not api_token or not team_id:
        print("Warning: SLAB_API_TOKEN and SLAB_TEAM_ID not configured, Slab disabled")
        return None

    return SlabClient(api_token, team_id)
