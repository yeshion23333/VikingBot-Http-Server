import httpx
from typing import List, Dict, Any, Optional, Set
from fastapi import HTTPException
from vikingbot_api.core.config import get_config
import  logging

# OpenViking API configuration loaded from config.json
OPENVIKING_BASE_URL = get_config("openviking.base_url", "http://localhost:8080")
OPENVIKING_API_KEY = get_config("openviking.api_key", "")
OPENVIKING_ACCOUNT_ID = get_config("openviking.account_id", "default")

# Cache for existing users to avoid frequent API calls
_existing_users: Set[str] = set()
logger = logging.getLogger(__name__)

class OpenVikingClient:
    def __init__(self, base_url: str = OPENVIKING_BASE_URL, api_key: str = OPENVIKING_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, method: str, path: str, params: Dict = None, json: Dict = None) -> Any:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

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
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"OpenViking API request failed: {str(e)}"
            )

    async def ls(self, uri: str) -> List[Dict]:
        """
        List directory contents
        :param uri: Viking URI (e.g. "/entities")
        :return: List of file/directory items
        """
        params = {
            "uri": uri,
            "recursive": True
        }
        response = await self._request("GET", "/api/v1/fs/ls", params=params)
        # Extract result from response wrapper
        return response.get("result", [])

    async def read(self, uri: str, level: str = "read") -> str:
        """
        Read file content
        :param uri: Viking URI (e.g. "/entities/mem_123.md")
        :return: File content string
        """
        params = {"uri": uri}
        if level == "read":
            response = await self._request("GET", "/api/v1/content/read", params=params)
        elif level == "abstract":
            response = await self._request("GET", "/api/v1/content/abstract", params=params)
        else:
            raise HTTPException(status_code=400, detail="Invalid level parameter, must be 'read' or 'abstract'")
        # Handle different response formats - adjust according to actual API response
        if isinstance(response, dict) and "result" in response:
            return response["result"]
        else:
            logger.error(f"Failed to read file content: {response}")
            return ""

    async def remove_user(self, user_id: str) -> bool:
        """
        Remove user memory and files
        :param user_id: User ID
        :return: Removal result
        """
        path = f"/api/v1/admin/accounts/{OPENVIKING_ACCOUNT_ID}/users/{user_id}"
        response = await self._request("DELETE", path)
        if isinstance(response, dict) and "status" in response:
            return "ok" == response["status"]
        else:
            logger.error(f"Failed to remove user {user_id}:{response}")
            return False

    async def list_user_memory(self, user_id: str) -> List[Dict]:
        """
        List all memory for a user
        :param user_id: User ID
        :return: Hierarchical memory structure
        """
        # User memory root path - adjust according to your actual path structure
        user_root = f"viking://user/{user_id}/memories/"

        try:
            # Get all recursive items with single ls call (already recursive=True)
            all_items = await self.ls(user_root)

            # Build tree structure from flat list
            node_map = {}
            root_nodes = []

            for item in all_items:
                rel_path = item.get("rel_path", "")
                if not rel_path:
                    continue

                # Create node
                node = {
                    "uri": "/" + rel_path,
                    "is_dir": item.get("isDir", False),
                    "children": [] if item.get("isDir", False) else None
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
        except Exception as e:
            # If user directory doesn't exist, return empty structure
            if "404" in str(e):
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
        full_uri = f"viking://user/{user_id}/memories{uri}"
        return await self.read(full_uri, level)

    async def delete_user_memory(self, user_id: str) -> None:
        """
        Delete all memory for a user
        :param user_id: User ID
        :return: Removal result
        """
        res = await self.remove_user(user_id)
        if res:
            global _existing_users
            if user_id in _existing_users:
                _existing_users.remove(user_id)
        return

    async def list_users(self) -> List[str]:
        """
        List all users in the account
        :return: List of user IDs
        """
        path = f"/api/v1/admin/accounts/{OPENVIKING_ACCOUNT_ID}/users"
        response = await self._request("GET", path)
        users = response.get("result", [])
        return [user.get("user_id") for user in users if user.get("user_id")]

    async def register_user(self, user_id: str) -> Dict:
        """
        Register a new user
        :param user_id: User ID to register
        :return: Registration result
        """
        path = f"/api/v1/admin/accounts/{OPENVIKING_ACCOUNT_ID}/users"
        payload = {
            "user_id": user_id,
            "role": "user"
        }
        return await self._request("POST", path, json=payload)

    async def check_user_exists(self, user_id: str) -> bool:
        """
        Check if user exists
        :param user_id: User ID to check
        :return: True if user exists, False otherwise
        """
        global _existing_users

        # Check cache first
        if user_id in _existing_users:
            return True

        try:
            # List all users
            users = await self.list_users()

            _existing_users.update(users)
            return user_id in _existing_users
        except Exception as e:
            return False

    async def ensure_user_exists(self, user_id: str) -> bool:
        """
        Ensure user exists, register if not found
        :param user_id: User ID to check
        :return: True if user exists or was registered successfully
        """
        global _existing_users

        # Check cache first
        if user_id in _existing_users:
            return True

        try:
            # List all users
            users = await self.list_users()
            _existing_users.update(users)

            if user_id in _existing_users:
                return True

            # User not found, register
            await self.register_user(user_id)
            _existing_users.add(user_id)
            return True
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to check or register user: {str(e)}"
            )

# Create global client instance
openviking_client = OpenVikingClient()
