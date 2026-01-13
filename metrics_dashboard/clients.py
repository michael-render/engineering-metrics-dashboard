"""API clients for data sources."""

import os
from datetime import datetime, timezone

import httpx

from metrics_dashboard.models import (
    GitHubDeployment,
    GitHubPullRequest,
    Incident,
    MetricsPeriod,
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
        """Get all non-archived repos in the organization with pagination."""
        repos: list[str] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    f"{self.base_url}/orgs/{self.org}/repos",
                    headers=self.headers,
                    params={"type": "all", "per_page": 100, "page": page},
                )
                response.raise_for_status()
                page_repos = response.json()

                if not page_repos:
                    break

                repos.extend([r["name"] for r in page_repos if not r.get("archived", False)])

                # Check if there are more pages via Link header
                link_header = response.headers.get("Link", "")
                if 'rel="next"' not in link_header:
                    break

                page += 1

        print(f"[GitHub] Found {len(repos)} repos in {self.org}")
        return repos

    async def get_deployments(
        self, repo: str, period: MetricsPeriod
    ) -> list[GitHubDeployment]:
        """Get deployments for a repository within the period."""
        deployments: list[GitHubDeployment] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Paginate through deployments
            page = 1
            while True:
                response = await client.get(
                    f"{self.base_url}/repos/{self.org}/{repo}/deployments",
                    headers=self.headers,
                    params={"per_page": 100, "page": page},
                )
                response.raise_for_status()
                page_deployments = response.json()

                if not page_deployments:
                    break

                for dep in page_deployments:
                    created_at = datetime.fromisoformat(dep["created_at"].replace("Z", "+00:00"))

                    # Stop if we've gone past our period
                    if created_at < period.start_date:
                        break

                    if created_at > period.end_date:
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

                # Check if we should continue
                if 'rel="next"' not in response.headers.get("Link", ""):
                    break
                page += 1

        return deployments

    async def get_pull_requests(
        self, repo: str, period: MetricsPeriod
    ) -> list[GitHubPullRequest]:
        """Get merged pull requests for a repository within the period."""
        pull_requests: list[GitHubPullRequest] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            page = 1
            while True:
                response = await client.get(
                    f"{self.base_url}/repos/{self.org}/{repo}/pulls",
                    headers=self.headers,
                    params={
                        "state": "closed",
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": 100,
                        "page": page,
                    },
                )
                response.raise_for_status()
                page_prs = response.json()

                if not page_prs:
                    break

                found_in_period = False
                for pr in page_prs:
                    if not pr.get("merged_at"):
                        continue

                    merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))

                    # Skip if before our period
                    if merged_at < period.start_date:
                        continue

                    # Skip if after our period
                    if merged_at > period.end_date:
                        continue

                    found_in_period = True
                    created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))

                    # Get first commit date for lead time calculation
                    first_commit_at = None
                    try:
                        commits_response = await client.get(
                            f"{self.base_url}/repos/{self.org}/{repo}/pulls/{pr['number']}/commits",
                            headers=self.headers,
                            params={"per_page": 1},
                        )
                        commits_response.raise_for_status()
                        commits = commits_response.json()

                        if commits:
                            commit_date = commits[0].get("commit", {}).get("committer", {}).get("date")
                            if commit_date:
                                first_commit_at = datetime.fromisoformat(
                                    commit_date.replace("Z", "+00:00")
                                )
                    except Exception as e:
                        print(f"[GitHub] Warning: Could not get commits for PR #{pr['number']}: {e}")

                    pull_requests.append(
                        GitHubPullRequest(
                            number=pr["number"],
                            title=pr["title"],
                            created_at=created_at,
                            merged_at=merged_at,
                            first_commit_at=first_commit_at,
                        )
                    )

                # Stop paginating if we're not finding PRs in period anymore
                if not found_in_period:
                    break

                if 'rel="next"' not in response.headers.get("Link", ""):
                    break
                page += 1

        return pull_requests


class IncidentIOClient:
    """Client for incident.io API.

    Used to fetch incidents for Change Failure Rate and MTTR calculations.
    Only counts incidents that were caused by changes (deployments).
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.incident.io/v2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def get_incidents(self, period: MetricsPeriod) -> list[Incident]:
        """Get incidents within the period.

        For DORA metrics, we're interested in incidents that:
        - Were caused by a change (deployment)
        - Have been resolved (so we can calculate MTTR)
        """
        incidents: list[Incident] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch incidents with pagination
            after_cursor: str | None = None

            while True:
                params: dict = {"page_size": 100}
                if after_cursor:
                    params["after"] = after_cursor

                response = await client.get(
                    f"{self.base_url}/incidents",
                    headers=self.headers,
                    params=params,
                )

                if response.status_code == 400:
                    error_data = response.json()
                    raise ValueError(f"incident.io API error: {error_data}")

                response.raise_for_status()
                data = response.json()

                for inc in data.get("incidents", []):
                    created_at = datetime.fromisoformat(
                        inc["created_at"].replace("Z", "+00:00")
                    )

                    # Filter by period
                    if created_at < period.start_date or created_at > period.end_date:
                        continue

                    # Parse resolved time if available
                    resolved_at = None
                    if inc.get("resolved_at"):
                        resolved_at = datetime.fromisoformat(
                            inc["resolved_at"].replace("Z", "+00:00")
                        )

                    # Calculate time to resolve
                    time_to_resolve_hours = None
                    if resolved_at:
                        time_to_resolve_hours = (
                            resolved_at - created_at
                        ).total_seconds() / 3600

                    # Get severity
                    severity = "minor"
                    severity_data = inc.get("severity", {})
                    if severity_data:
                        sev_name = severity_data.get("name", "").lower()
                        if any(s in sev_name for s in ["critical", "sev0", "sev 0", "p0"]):
                            severity = "critical"
                        elif any(s in sev_name for s in ["major", "sev1", "sev 1", "p1"]):
                            severity = "major"

                    # Check if incident was caused by a change
                    # incident.io may have custom fields or incident types for this
                    # We look for common indicators:
                    # - incident type contains "change" or "deployment"
                    # - custom field indicates change-related
                    # - or we assume all incidents in a deployment-heavy org are change-related
                    is_change_related = self._is_change_related(inc)

                    incidents.append(
                        Incident(
                            id=inc["id"],
                            name=inc.get("name", "Unknown"),
                            status=inc.get("status", {}).get("category", "open"),
                            severity=severity,
                            created_at=created_at,
                            resolved_at=resolved_at,
                            time_to_resolve_hours=time_to_resolve_hours,
                            is_change_related=is_change_related,
                        )
                    )

                # Handle pagination
                pagination = data.get("pagination_meta", {})
                after_cursor = pagination.get("after")
                if not after_cursor:
                    break

        print(f"[incident.io] Found {len(incidents)} incidents in period")
        return incidents

    def _is_change_related(self, incident: dict) -> bool:
        """Determine if an incident was caused by a change/deployment.

        This checks various fields that might indicate a change-related incident.
        Customize this based on how your team tags change-related incidents.
        """
        # Check incident type
        inc_type = incident.get("incident_type", {})
        if inc_type:
            type_name = inc_type.get("name", "").lower()
            if any(kw in type_name for kw in ["change", "deploy", "release", "rollout"]):
                return True

        # Check custom fields for change-related indicators
        custom_fields = incident.get("custom_field_entries", [])
        for field in custom_fields:
            field_name = field.get("custom_field", {}).get("name", "").lower()
            field_value = str(field.get("value", "")).lower()

            # Look for fields like "cause", "root_cause", "trigger"
            if any(kw in field_name for kw in ["cause", "trigger", "source"]):
                if any(kw in field_value for kw in ["change", "deploy", "release", "code", "pr"]):
                    return True

        # Check if name/summary mentions deployment/change
        name = incident.get("name", "").lower()
        summary = incident.get("summary", "").lower()
        change_keywords = ["deploy", "release", "rollout", "change", "update", "migration"]

        if any(kw in name or kw in summary for kw in change_keywords):
            return True

        # Default: assume it's change-related for DORA purposes
        # This is a conservative assumption - you may want to change this to False
        # if your org has many non-change-related incidents
        return True

    async def get_change_related_incidents(self, period: MetricsPeriod) -> list[Incident]:
        """Get only incidents that were caused by changes."""
        all_incidents = await self.get_incidents(period)
        return [inc for inc in all_incidents if inc.is_change_related]


def create_github_client() -> GitHubClient:
    """Create GitHub client from environment variables."""
    token = os.environ.get("GITHUB_TOKEN")
    org = os.environ.get("GITHUB_ORG")

    if not token or not org:
        raise ValueError("GITHUB_TOKEN and GITHUB_ORG environment variables are required")

    return GitHubClient(token, org)


def create_incident_io_client() -> IncidentIOClient | None:
    """Create incident.io client from environment variables."""
    api_key = os.environ.get("INCIDENT_IO_API_KEY")

    if not api_key:
        print("Warning: INCIDENT_IO_API_KEY not configured, incident.io disabled")
        return None

    return IncidentIOClient(api_key)
