"""
Agent Polis - Impact Preview Dashboard

A Streamlit UI for reviewing and approving AI agent actions.

Run with: streamlit run src/agent_polis/ui/app.py
"""

import os
from datetime import datetime

import httpx
import streamlit as st

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")


def init_session_state():
    """Initialize session state variables."""
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "agent_name" not in st.session_state:
        st.session_state.agent_name = ""


def get_headers():
    """Get headers for API requests."""
    headers = {"Content-Type": "application/json"}
    if st.session_state.api_key:
        headers["X-API-Key"] = st.session_state.api_key
    return headers


def api_get(endpoint: str):
    """Make a GET request to the API."""
    try:
        response = httpx.get(f"{API_URL}{endpoint}", headers=get_headers(), timeout=30)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, data: dict):
    """Make a POST request to the API."""
    try:
        response = httpx.post(
            f"{API_URL}{endpoint}",
            headers=get_headers(),
            json=data,
            timeout=60,
        )
        return response.json(), response.status_code
    except Exception as e:
        st.error(f"API Error: {e}")
        return None, 500


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Agent Polis - Impact Preview",
        page_icon="🔍",
        layout="wide",
    )
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("🔍 Agent Polis")
        st.caption("Impact Preview for AI Agents")
        
        st.divider()
        
        # API Key input
        st.subheader("Authentication")
        api_key = st.text_input(
            "API Key",
            value=st.session_state.api_key,
            type="password",
            help="Enter your agent's API key",
        )
        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
        
        if st.session_state.api_key:
            # Verify API key
            agent = api_get("/api/v1/agents/me")
            if agent:
                st.success(f"Logged in as: **{agent['name']}**")
                st.session_state.agent_name = agent["name"]
            else:
                st.error("Invalid API key")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigate",
            ["Pending Approvals", "All Actions", "Submit Action", "Agents", "Dashboard"],
        )
    
    # Main content
    if page == "Pending Approvals":
        show_pending_approvals()
    elif page == "All Actions":
        show_all_actions()
    elif page == "Submit Action":
        show_submit_action()
    elif page == "Agents":
        show_agents()
    elif page == "Dashboard":
        show_dashboard()


def show_pending_approvals():
    """Show pending actions awaiting approval."""
    st.title("⏳ Pending Approvals")
    st.caption("Review and approve/reject AI agent actions")
    
    if not st.session_state.api_key:
        st.warning("Please enter your API key to view pending actions")
        return
    
    # Toggle to see all agents' pending actions
    all_agents = st.checkbox("Show actions from all agents", value=True)
    
    # Fetch pending actions
    pending = api_get(f"/api/v1/actions/pending?all_agents={str(all_agents).lower()}")
    if not pending or not pending.get("actions"):
        st.info("No pending actions! All clear 🎉")
        return
    
    st.metric("Pending Actions", pending["pending_count"])
    st.divider()
    
    for action in pending["actions"]:
        show_action_card(action, show_actions=True)


def show_all_actions():
    """Show all actions."""
    st.title("📋 All Actions")
    
    if not st.session_state.api_key:
        st.warning("Please enter your API key to view actions")
        return
    
    # Filters
    col1, col2 = st.columns([1, 2])
    with col1:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "pending", "approved", "rejected", "executed", "failed", "timed_out"],
        )
    
    # Build query
    query = ""
    if status_filter != "All":
        query = f"?status={status_filter}"
    
    actions_resp = api_get(f"/api/v1/actions{query}")
    if not actions_resp or not actions_resp.get("actions"):
        st.info("No actions found")
        return
    
    for action in actions_resp["actions"]:
        show_action_card(action, show_actions=(action["status"] == "pending"))


def show_action_card(action: dict, show_actions: bool = False):
    """Display an action card with preview and approval controls."""
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
        "executed": "🚀",
        "failed": "💥",
        "timed_out": "⏰",
    }.get(action["status"], "❓")
    
    risk_color = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }
    
    preview = action.get("preview", {})
    risk_level = preview.get("risk_level", "medium")
    risk_emoji = risk_color.get(risk_level, "⚪")
    
    with st.expander(
        f"{status_emoji} {risk_emoji} {action['action_type']}: {action['target'][:50]}",
        expanded=action["status"] == "pending",
    ):
        # Header info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Action Type:** {action['action_type']}")
            st.write(f"**Status:** {action['status']}")
        with col2:
            st.write(f"**Risk Level:** {risk_level.upper()}")
            if action.get("agent_name"):
                st.write(f"**Agent:** {action['agent_name']}")
        with col3:
            st.write(f"**Created:** {action['created_at'][:19]}")
            if action.get("expires_at"):
                st.write(f"**Expires:** {action['expires_at'][:19]}")
        
        st.divider()
        
        # Description
        st.subheader("Description")
        st.write(action["description"])
        
        # Target
        st.subheader("Target")
        st.code(action["target"])
        
        # Preview / Diff
        if preview:
            st.subheader("Impact Preview")
            
            # Summary
            st.write(f"**Summary:** {preview.get('summary', 'No summary')}")
            
            # Warnings
            warnings = preview.get("warnings", [])
            if warnings:
                for warning in warnings:
                    st.warning(warning)
            
            # Risk factors
            risk_factors = preview.get("risk_factors", [])
            if risk_factors:
                st.write("**Risk Factors:**")
                for factor in risk_factors:
                    st.write(f"- {factor}")
            
            # File changes
            file_changes = preview.get("file_changes", [])
            if file_changes:
                st.subheader("File Changes")
                for change in file_changes:
                    change_emoji = {
                        "create": "🆕",
                        "modify": "📝",
                        "delete": "🗑️",
                        "move": "📦",
                    }.get(change.get("operation", ""), "❓")
                    
                    st.write(f"{change_emoji} **{change['path']}** ({change['operation']})")
                    
                    if change.get("lines_added") or change.get("lines_removed"):
                        st.write(f"  +{change['lines_added']} -{change['lines_removed']} lines")
                    
                    if change.get("diff"):
                        st.code(change["diff"], language="diff")
            
            # Reversibility
            st.write(f"**Reversible:** {'Yes' if preview.get('is_reversible', True) else 'No'}")
            if preview.get("reversal_instructions"):
                st.write(f"**How to reverse:** {preview['reversal_instructions']}")
        
        # Actions (for pending items)
        if show_actions and action["status"] == "pending":
            st.divider()
            st.subheader("Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Approve", key=f"approve_{action['id']}", type="primary"):
                    result, status = api_post(
                        f"/api/v1/actions/{action['id']}/approve",
                        {"comment": "Approved via dashboard"},
                    )
                    if status in [200, 201]:
                        st.success("Action approved!")
                        st.rerun()
                    else:
                        st.error(f"Failed: {result}")
            
            with col2:
                reject_reason = st.text_input(
                    "Rejection reason",
                    key=f"reason_{action['id']}",
                    placeholder="Why are you rejecting?",
                )
                if st.button("❌ Reject", key=f"reject_{action['id']}"):
                    if not reject_reason:
                        st.error("Please provide a reason for rejection")
                    else:
                        result, status = api_post(
                            f"/api/v1/actions/{action['id']}/reject",
                            {"reason": reject_reason},
                        )
                        if status in [200, 201]:
                            st.success("Action rejected!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")
            
            with col3:
                if action.get("approved_at"):
                    if st.button("🚀 Execute", key=f"execute_{action['id']}"):
                        result, status = api_post(
                            f"/api/v1/actions/{action['id']}/execute",
                            {},
                        )
                        if status in [200, 201]:
                            st.success("Action executed!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")
        
        # Show rejection reason if rejected
        if action.get("rejection_reason"):
            st.error(f"**Rejection reason:** {action['rejection_reason']}")
        
        # Show execution result
        if action.get("execution_result"):
            st.success("**Execution result:**")
            st.json(action["execution_result"])
        
        if action.get("execution_error"):
            st.error(f"**Execution error:** {action['execution_error']}")


def show_submit_action():
    """Form to submit a new action for approval."""
    st.title("📤 Submit Action")
    st.caption("Submit an action for human approval before execution")
    
    if not st.session_state.api_key:
        st.warning("Please enter your API key to submit actions")
        return
    
    with st.form("submit_action"):
        action_type = st.selectbox(
            "Action Type",
            ["file_write", "file_create", "file_delete", "file_move", 
             "db_query", "db_execute", "api_call", "shell_command", "custom"],
        )
        
        target = st.text_input(
            "Target",
            placeholder="/path/to/file or https://api.example.com/endpoint",
            help="The target of the action (file path, URL, table name, etc.)",
        )
        
        description = st.text_area(
            "Description",
            placeholder="What this action will do and why it's needed...",
            help="Human-readable description for the reviewer",
        )
        
        # Different payload fields based on action type
        st.subheader("Payload")
        
        if action_type in ["file_write", "file_create"]:
            content = st.text_area(
                "File Content",
                height=300,
                placeholder="Content to write to the file...",
            )
            payload = {"content": content}
        
        elif action_type == "file_move":
            destination = st.text_input(
                "Destination Path",
                placeholder="/new/path/to/file",
            )
            payload = {"destination": destination}
        
        elif action_type in ["db_query", "db_execute"]:
            query = st.text_area(
                "SQL Query",
                height=200,
                placeholder="SELECT * FROM users WHERE...",
            )
            payload = {"query": query}
        
        elif action_type == "api_call":
            method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
            body = st.text_area("Request Body (JSON)", placeholder="{}")
            payload = {"method": method, "body": body}
        
        elif action_type == "shell_command":
            command = st.text_input(
                "Command",
                placeholder="npm install ...",
            )
            payload = {"command": command}
        
        else:
            payload_str = st.text_area(
                "Custom Payload (JSON)",
                value="{}",
            )
            import json
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                payload = {}
        
        st.divider()
        
        # Options
        col1, col2 = st.columns(2)
        with col1:
            timeout = st.slider("Approval Timeout (seconds)", 30, 3600, 300)
        with col2:
            auto_approve = st.checkbox(
                "Auto-approve if low risk",
                help="Automatically approve if assessed as low risk",
            )
        
        context = st.text_area(
            "Additional Context (optional)",
            placeholder="Any additional context for the reviewer...",
        )
        
        submitted = st.form_submit_button("Submit for Approval", type="primary")
        
        if submitted:
            if not target or not description:
                st.error("Target and description are required")
            else:
                data = {
                    "action_type": action_type,
                    "target": target,
                    "description": description,
                    "payload": payload,
                    "context": context if context else None,
                    "timeout_seconds": timeout,
                    "auto_approve_if_low_risk": auto_approve,
                }
                
                result, status = api_post("/api/v1/actions", data)
                if status in [200, 201]:
                    st.success(f"Action submitted! ID: {result['id']}")
                    
                    if result.get("status") == "approved":
                        st.info("Action was auto-approved (low risk)")
                    else:
                        st.info("Action is pending approval")
                    
                    # Show preview
                    if result.get("preview"):
                        st.subheader("Impact Preview")
                        st.json(result["preview"])
                else:
                    st.error(f"Submission failed: {result}")


def show_agents():
    """Show agents list."""
    st.title("🤖 Agents")
    
    # Registration form
    with st.expander("Register New Agent"):
        with st.form("register_agent"):
            name = st.text_input("Agent Name", placeholder="my-agent")
            description = st.text_area("Description", placeholder="What this agent does...")
            
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if not name or not description:
                    st.error("Name and description are required")
                else:
                    result, status = api_post(
                        "/api/v1/agents/register",
                        {"name": name, "description": description},
                    )
                    if status == 201:
                        st.success("Agent registered!")
                        st.warning("⚠️ Save your API key - it won't be shown again!")
                        st.code(result["api_key"])
                    else:
                        st.error(f"Registration failed: {result}")
    
    # List agents
    st.subheader("Registered Agents")
    agents = api_get("/api/v1/agents?page_size=50")
    if agents:
        for agent in agents.get("agents", []):
            status_emoji = "✅" if agent["verified"] else "⏳"
            with st.expander(f"{status_emoji} {agent['name']}"):
                st.write(f"**Description:** {agent['description']}")
                st.write(f"**Status:** {agent['status']}")
                st.write(f"**Created:** {agent['created_at']}")


def show_dashboard():
    """Show the main dashboard."""
    st.title("📊 Dashboard")
    
    # Health check
    health = api_get("/health")
    if health:
        col1, col2, col3 = st.columns(3)
        with col1:
            status_text = "🟢 Healthy" if health["status"] == "healthy" else "🔴 Unhealthy"
            st.metric("Status", status_text)
        with col2:
            st.metric("Version", health["version"])
        with col3:
            st.metric("Environment", health["environment"])
    
    st.divider()
    
    # Agent Card
    st.subheader("Agent Capabilities")
    agent_card = api_get("/.well-known/agent.json")
    if agent_card:
        st.json(agent_card)
    
    st.divider()
    
    # Quick stats if logged in
    if st.session_state.api_key:
        st.subheader("Quick Stats")
        
        # Get pending count
        pending = api_get("/api/v1/actions/pending?all_agents=true")
        pending_count = pending.get("pending_count", 0) if pending else 0
        
        # Get my actions
        my_actions = api_get("/api/v1/actions")
        my_total = my_actions.get("total", 0) if my_actions else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Approvals", pending_count)
        with col2:
            st.metric("My Total Actions", my_total)
        with col3:
            if pending_count > 0:
                st.warning(f"{pending_count} action(s) awaiting approval!")


if __name__ == "__main__":
    main()
