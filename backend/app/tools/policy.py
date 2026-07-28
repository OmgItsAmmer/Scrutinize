from typing import Literal

ToolName = Literal["web_search", "generate_pdf", "generate_flowchart", "execute_python"]
RiskLevel = Literal["low", "medium", "high"]

TOOL_POLICIES = {
    "web_search": {"risk_level": "low", "required_role": "member"},
    "generate_pdf": {"risk_level": "medium", "required_role": "member"},
    "generate_flowchart": {"risk_level": "medium", "required_role": "member"},
    "execute_python": {"risk_level": "high", "required_role": "owner"},
}

class PermissionChecker:
    @staticmethod
    def check_permission(tool_name: str, user_role: str) -> bool:
        """Deterministically check if a user with a given role is allowed to run a tool."""
        policy = TOOL_POLICIES.get(tool_name)
        if not policy:
            # Deny access to unknown tools by default
            return False
        
        required_role = policy["required_role"]
        
        # Simple role hierarchy: owner > member
        role_hierarchy = {"owner": 2, "member": 1}
        user_rank = role_hierarchy.get(user_role, 0)
        required_rank = role_hierarchy.get(required_role, 1)
        
        return user_rank >= required_rank

    @staticmethod
    def requires_approval(tool_name: str) -> bool:
        """Check if executing the tool requires explicit human approval."""
        policy = TOOL_POLICIES.get(tool_name)
        if not policy:
            return True  # Require approval for unknown tools by default
        return policy["risk_level"] == "high"
