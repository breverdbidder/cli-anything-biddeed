"""
vercel_api.py — DesignWise Vercel API client.
Manages deployments for ZoneWise.AI across lab/preview/production tiers.
All methods are async using httpx.
"""

import os
from typing import Any, Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

VERCEL_BASE_URL = "https://api.vercel.com"
DEFAULT_PROJECT_ID = "prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E"


class VercelClient:
    """
    Async Vercel API client for deployment management.
    Env vars: VERCEL_TOKEN, VERCEL_PROJECT_ID
    """

    def __init__(self, token: Optional[str] = None, project_id: Optional[str] = None):
        self.token = token or os.environ.get("VERCEL_TOKEN", "")
        self.project_id = project_id or os.environ.get("VERCEL_PROJECT_ID", DEFAULT_PROJECT_ID)
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{VERCEL_BASE_URL}{path}"

    async def list_deployments(self, limit: int = 10) -> Dict[str, Any]:
        """GET /v6/deployments — list recent deployments for project."""
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self._url("/v6/deployments"),
                    headers=self._headers,
                    params={"projectId": self.project_id, "limit": limit},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_deployment(self, deploy_id: str) -> Dict[str, Any]:
        """GET /v13/deployments/{id} — get deployment details."""
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self._url(f"/v13/deployments/{deploy_id}"),
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def create_deployment(self, branch: str, git_sha: str) -> Dict[str, Any]:
        """POST /v13/deployments — trigger a new deployment for branch/sha."""
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            payload = {
                "name": self.project_id,
                "gitSource": {
                    "type": "github",
                    "ref": branch,
                    "sha": git_sha,
                },
                "projectId": self.project_id,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._url("/v13/deployments"),
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_preview_url(self, deploy_id: str) -> Optional[str]:
        """Extract preview URL from a deployment."""
        dep = await self.get_deployment(deploy_id)
        if "error" in dep:
            return None
        url = dep.get("url") or dep.get("alias", [None])[0] if dep.get("alias") else None
        if url and not url.startswith("http"):
            url = f"https://{url}"
        return url

    async def promote_to_production(self, deploy_id: str) -> Dict[str, Any]:
        """POST /v13/deployments/{id}/promote — promote deployment to production."""
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._url(f"/v13/deployments/{deploy_id}/promote"),
                    headers=self._headers,
                    json={"projectId": self.project_id},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def rollback(self, deploy_id: str) -> Dict[str, Any]:
        """
        Rollback to a previous deployment by promoting it.
        Uses promote_to_production on the target deploy_id.
        """
        result = await self.promote_to_production(deploy_id)
        return {"action": "rollback", "target_deploy": deploy_id, "result": result}

    async def check_status(self, deploy_id: str) -> Dict[str, Any]:
        """Poll deployment status. Returns {status: str, url: str}."""
        dep = await self.get_deployment(deploy_id)
        if "error" in dep:
            return dep
        return {
            "status": dep.get("readyState", dep.get("state", "UNKNOWN")),
            "url": dep.get("url", ""),
            "id": deploy_id,
        }
