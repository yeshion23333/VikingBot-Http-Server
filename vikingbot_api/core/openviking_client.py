import httpx
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from vikingbot_api.core.config import get_config
import  logging

OPENVIKING_BASE_URL = get_config("openviking.base_url", "http://localhost:8080")
OPENVIKING_API_KEY = get_config("openviking.api_key", "")
logger = logging.getLogger(__name__)

class OpenVikingClient:
    def __init__(self, base_url: str = OPENVIKING_BASE_URL, api_key: str = OPENVIKING_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict = None,
        json: Dict = None,
        actor_peer_id: str | None = None,
    ) -> Any:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if actor_peer_id:
            headers["X-OpenViking-Actor-Peer"] = actor_peer_id

        url = f"{self.base_url}{path}"

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            detail = e.response.text or str(e)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"OpenViking API request failed: {detail}"
            )
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"OpenViking API request failed: {str(e)}"
            )

    @staticmethod
    def peer_memory_root(peer_id: str) -> str:
        """
        Build the current OpenViking peer memory root for a user-key request.

        In current OpenViking, external users are represented as peers under the
        authenticated OpenViking user, not as OpenViking users.
        """
        peer_id = str(peer_id or "").strip().strip("/")
        if not peer_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        return f"viking://user/peers/{peer_id}/memories/"

    @staticmethod
    def _memory_uri_from_peer_path(peer_id: str, uri: str) -> str:
        uri = str(uri or "").strip()
        if uri.startswith("viking://"):
            return uri

        root = OpenVikingClient.peer_memory_root(peer_id).rstrip("/")
        if not uri:
            return root + "/"
        return f"{root}/{uri.lstrip('/')}"

    async def ls(self, uri: str, actor_peer_id: str | None = None) -> List[Dict]:
        """
        List directory contents
        :param uri: Viking URI (e.g. "/entities")
        :return: List of file/directory items
        """
        params = {
            "uri": uri,
            "recursive": True
        }
        response = await self._request(
            "GET",
            "/api/v1/fs/ls",
            params=params,
            actor_peer_id=actor_peer_id,
        )
        # Extract result from response wrapper
        return response.get("result", [])

    async def read(
        self,
        uri: str,
        level: str = "read",
        actor_peer_id: str | None = None,
    ) -> str:
        """
        Read file content
        :param uri: Viking URI (e.g. "/entities/mem_123.md")
        :return: File content string
        """
        params = {"uri": uri}
        if level == "read":
            response = await self._request(
                "GET",
                "/api/v1/content/read",
                params=params,
                actor_peer_id=actor_peer_id,
            )
        elif level == "abstract":
            response = await self._request(
                "GET",
                "/api/v1/content/abstract",
                params=params,
                actor_peer_id=actor_peer_id,
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid level parameter, must be 'read' or 'abstract'")
        # Handle different response formats - adjust according to actual API response
        if isinstance(response, dict) and "result" in response:
            return response["result"] or ""
        else:
            logger.error(f"Failed to read file content: {response}")
            return ""

    async def remove_user(self, user_id: str) -> bool:
        """
        Remove peer memory and files.
        Kept for backward compatibility with older callers.
        :param user_id: External user ID, used as OpenViking peer ID
        :return: Removal result
        """
        response = await self._request(
            "DELETE",
            "/api/v1/fs",
            params={
                "uri": self.peer_memory_root(user_id),
                "recursive": True,
                "wait": True,
            },
            actor_peer_id=user_id,
        )
        if isinstance(response, dict) and "status" in response:
            return "ok" == response["status"]
        else:
            logger.error(f"Failed to remove peer memory {user_id}: {response}")
            return False

    async def list_user_memory(self, user_id: str) -> List[Dict]:
        """
        List all memory for a peer.
        :param user_id: External user ID, used as OpenViking peer ID
        :return: Hierarchical memory structure
        """
        peer_id = str(user_id).strip().strip("/")
        user_root = self.peer_memory_root(peer_id)
        peer_rel_prefix = f"peers/{peer_id}/memories/"
        canonical_peer_marker = f"/peers/{peer_id}/memories/"

        try:
            # Get all recursive items with single ls call (already recursive=True)
            all_items = await self.ls(user_root, actor_peer_id=peer_id)

            # Build tree structure from flat list
            node_map = {}
            root_nodes = []

            for item in all_items:
                item_uri = str(item.get("uri", "") or "")
                rel_path = str(item.get("rel_path", "") or "")
                if not rel_path and item_uri.startswith(user_root):
                    rel_path = item_uri[len(user_root):].lstrip("/")
                if not rel_path and canonical_peer_marker in item_uri:
                    rel_path = item_uri.split(canonical_peer_marker, 1)[1].lstrip("/")
                if rel_path.startswith(peer_rel_prefix):
                    rel_path = rel_path[len(peer_rel_prefix):].lstrip("/")
                if not rel_path:
                    continue

                # Create node
                node = {
                    "uri": "/" + rel_path,
                    "is_dir": bool(item.get("isDir", item.get("is_dir", False))),
                    "children": [] if item.get("isDir", item.get("is_dir", False)) else None
                }
                node_map[rel_path] = node

                # Find parent path
                path_parts = rel_path.split("/")
                if len(path_parts) == 1:
                    # Root level node
                    root_nodes.append(node)
                else:
                    # Get parent path
                    parent_path = "/".join(path_parts[:-1])
                    if parent_path in node_map:
                        parent_node = node_map[parent_path]
                        if parent_node["children"] is None:
                            parent_node["children"] = []
                        parent_node["children"].append(node)

            # Sort root nodes for consistent order
            root_nodes.sort(key=lambda x: x["uri"])

            return root_nodes
        except HTTPException as e:
            # If peer memory directory doesn't exist, return an empty default tree.
            if e.status_code == 404:
                return [
                    {
                        "uri": "/entities",
                        "is_dir": True,
                        "children": []
                    },
                    {
                        "uri": "/events",
                        "is_dir": True,
                        "children": []
                    },
                    {
                        "uri": "/preferences",
                        "is_dir": True,
                        "children": []
                    },
                    {
                        "uri": "/profile.md",
                        "is_dir": False,
                        "children": None
                    }
                ]
            raise

    async def get_memory_info(self, user_id: str, uri: str, level: str) -> str:
        """
        Get memory content or abstract
        :param user_id: User ID
        :param uri: Memory URI
        :param level: "read" for full content, "abstract" for summary
        :return: Memory content
        """
        full_uri = self._memory_uri_from_peer_path(user_id, uri)
        try:
            return await self.read(full_uri, level, actor_peer_id=user_id)
        except HTTPException as e:
            if e.status_code == 404:
                return ""
            raise

    async def delete_user_memory(self, user_id: str) -> None:
        """
        Delete all memory for a peer.
        :param user_id: External user ID, used as OpenViking peer ID
        :return: Removal result
        """
        try:
            await self.remove_user(user_id)
        except HTTPException as e:
            if e.status_code != 404:
                raise
        return

    async def list_users(
        self,
        limit: int = 100,
        name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[str]:
        """Deprecated: OpenViking user enumeration is not used in user-key mode."""
        return []

    async def register_user(self, user_id: str) -> Dict:
        """Deprecated: peers do not need to be registered as OpenViking users."""
        return {"status": "ok", "result": {"peer_id": user_id}}

    async def check_user_exists(self, user_id: str) -> bool:
        """Deprecated: external users are peers and do not require registration."""
        return bool(str(user_id or "").strip())

    async def ensure_user_exists(self, user_id: str) -> bool:
        """Deprecated: external users are peers and do not require registration."""
        return await self.check_user_exists(user_id)

# Create global client instance
openviking_client = OpenVikingClient()
