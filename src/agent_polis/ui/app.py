"""
Streamlit demo application for Agent Polis.

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
        page_title="Agent Polis",
        page_icon="🏛️",
        layout="wide",
    )
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("🏛️ Agent Polis")
        st.caption("Governance & Coordination for AI Agents")
        
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
                st.metric("Reputation", f"{agent['reputation_score']:.2f}")
            else:
                st.error("Invalid API key")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigate",
            ["Dashboard", "Simulations", "New Simulation", "Agents", "Events"],
        )
    
    # Main content
    if page == "Dashboard":
        show_dashboard()
    elif page == "Simulations":
        show_simulations()
    elif page == "New Simulation":
        show_new_simulation()
    elif page == "Agents":
        show_agents()
    elif page == "Events":
        show_events()


def show_dashboard():
    """Show the main dashboard."""
    st.title("Dashboard")
    
    # Health check
    health = api_get("/health")
    if health:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", "🟢 Healthy" if health["status"] == "healthy" else "🔴 Unhealthy")
        with col2:
            st.metric("Version", health["version"])
        with col3:
            st.metric("Environment", health["environment"])
    
    st.divider()
    
    # Agent Card
    st.subheader("A2A Agent Card")
    agent_card = api_get("/.well-known/agent.json")
    if agent_card:
        st.json(agent_card)
    
    # Stats if logged in
    if st.session_state.api_key:
        st.divider()
        st.subheader("Your Stats")
        stats = api_get("/api/v1/agents/me/stats")
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Simulations", stats["total_simulations"])
            with col2:
                st.metric("Successful", stats["successful_simulations"])
            with col3:
                st.metric("Failed", stats["failed_simulations"])
            with col4:
                st.metric(
                    "This Month",
                    f"{stats['simulations_this_month']}/{stats['monthly_limit']}",
                )


def show_simulations():
    """Show simulations list."""
    st.title("Simulations")
    
    if not st.session_state.api_key:
        st.warning("Please enter your API key to view simulations")
        return
    
    # Fetch simulations
    sims = api_get("/api/v1/simulations?page_size=50")
    if not sims:
        st.info("No simulations found")
        return
    
    # Filter
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "pending", "running", "completed", "failed"],
    )
    
    # Display simulations
    for sim in sims.get("simulations", []):
        if status_filter != "All" and sim["status"] != status_filter:
            continue
        
        status_emoji = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(sim["status"], "❓")
        
        with st.expander(
            f"{status_emoji} {sim['scenario']['name']} - {sim['status']}",
            expanded=sim["status"] == "running",
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**ID:** `{sim['id']}`")
                st.write(f"**Created:** {sim['created_at']}")
                if sim.get("scenario", {}).get("description"):
                    st.write(f"**Description:** {sim['scenario']['description']}")
            
            with col2:
                if sim["status"] == "pending":
                    if st.button("Run", key=f"run_{sim['id']}"):
                        result, status = api_post(f"/api/v1/simulations/{sim['id']}/run", {})
                        if status == 200:
                            st.success("Simulation started!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")
            
            # Show result if available
            if sim.get("result"):
                st.divider()
                st.subheader("Result")
                result = sim["result"]
                
                if result.get("success"):
                    st.success("Execution successful")
                else:
                    st.error(f"Execution failed: {result.get('error', 'Unknown error')}")
                
                if result.get("output"):
                    st.write("**Output:**")
                    st.json(result["output"])
                
                if result.get("stdout"):
                    st.write("**Stdout:**")
                    st.code(result["stdout"])
                
                if result.get("duration_ms"):
                    st.write(f"**Duration:** {result['duration_ms']}ms")


def show_new_simulation():
    """Show form to create a new simulation."""
    st.title("New Simulation")
    
    if not st.session_state.api_key:
        st.warning("Please enter your API key to create simulations")
        return
    
    with st.form("new_simulation"):
        name = st.text_input("Scenario Name", placeholder="My Test Scenario")
        description = st.text_area("Description", placeholder="What this simulation tests...")
        
        code = st.text_area(
            "Python Code",
            height=300,
            placeholder="""# Your simulation code here
# The 'result' variable will be captured as output

inputs_value = inputs.get('my_input', 'default')
result = {"status": "success", "value": inputs_value * 2}
print(f"Processed: {result}")
""",
            help="Python code to execute in the sandbox. Use 'result' variable for output.",
        )
        
        inputs_str = st.text_area(
            "Inputs (JSON)",
            value="{}",
            help="JSON object of input variables",
        )
        
        timeout = st.slider("Timeout (seconds)", 10, 300, 60)
        
        run_immediately = st.checkbox("Run immediately after creation", value=True)
        
        submitted = st.form_submit_button("Create Simulation")
        
        if submitted:
            if not name or not code:
                st.error("Name and code are required")
            else:
                import json
                try:
                    inputs = json.loads(inputs_str)
                except json.JSONDecodeError:
                    st.error("Invalid JSON in inputs")
                    return
                
                data = {
                    "scenario": {
                        "name": name,
                        "description": description,
                        "code": code,
                        "inputs": inputs,
                        "timeout_seconds": timeout,
                    }
                }
                
                result, status = api_post("/api/v1/simulations", data)
                if status == 201:
                    st.success(f"Simulation created: {result['id']}")
                    
                    if run_immediately:
                        with st.spinner("Running simulation..."):
                            run_result, run_status = api_post(
                                f"/api/v1/simulations/{result['id']}/run", {}
                            )
                            if run_status == 200:
                                if run_result.get("success"):
                                    st.success("Simulation completed successfully!")
                                else:
                                    st.error(f"Simulation failed: {run_result.get('error')}")
                                
                                st.json(run_result)
                            else:
                                st.error(f"Run failed: {run_result}")
                else:
                    st.error(f"Creation failed: {result}")


def show_agents():
    """Show agents list."""
    st.title("Agents")
    
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
            with st.expander(f"{status_emoji} {agent['name']} - Rep: {agent['reputation_score']:.2f}"):
                st.write(f"**Description:** {agent['description']}")
                st.write(f"**Status:** {agent['status']}")
                st.write(f"**Verified:** {agent['verified']}")
                st.write(f"**Simulations:** {agent['simulation_count']}")
                st.write(f"**Created:** {agent['created_at']}")


def show_events():
    """Show event audit trail."""
    st.title("Event Audit Trail")
    st.caption("Immutable record of all governance actions")
    
    st.info(
        "Events are stored in an append-only, hash-chained log for tamper detection. "
        "This provides a complete audit trail for compliance."
    )
    
    # Note: In a full implementation, we'd have an events API endpoint
    st.warning("Event browsing API coming soon. Events are stored for each simulation.")
    
    if st.session_state.api_key:
        # Show simulation events as example
        sims = api_get("/api/v1/simulations?page_size=5")
        if sims and sims.get("simulations"):
            st.subheader("Recent Simulation Events")
            for sim in sims["simulations"][:3]:
                events = api_get(f"/api/v1/simulations/{sim['id']}/events")
                if events:
                    with st.expander(f"Events for: {sim['scenario']['name']}"):
                        for event in events:
                            st.write(f"**{event['type']}** at {event['created_at']}")
                            st.json(event["data"])


if __name__ == "__main__":
    main()
