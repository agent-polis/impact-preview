#!/usr/bin/env python3
"""
Example: Using Agent Polis for Impact Preview

This example demonstrates how to use Agent Polis to add approval
workflows to your AI agent's dangerous operations.
"""

import os
import sys

# Add parent directory to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_polis.sdk import AgentPolisClient, ActionRejectedError, ActionTimedOutError


def main():
    """Demonstrate the impact preview workflow."""
    
    # Initialize client
    api_url = os.getenv("API_URL", "http://localhost:8000")
    api_key = os.getenv("AGENT_API_KEY", "")
    
    if not api_key:
        print("Please set AGENT_API_KEY environment variable")
        print("Register an agent first:")
        print(f"  curl -X POST {api_url}/api/v1/agents/register \\")
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"name": "my-agent", "description": "Example agent"}\'')
        return
    
    client = AgentPolisClient(api_url=api_url, api_key=api_key)
    
    print("=" * 60)
    print("Agent Polis - Impact Preview Example")
    print("=" * 60)
    
    # Example 1: Submit a file write action
    print("\n1. Submitting a file write action...")
    
    action = client.submit_action(
        action_type="file_write",
        target="/app/config.yaml",
        description="Update database connection to production",
        payload={
            "content": """
database:
  host: production-db.example.com
  port: 5432
  name: prod_database
  user: app_user
"""
        },
        context="AI agent wants to update config for deployment",
    )
    
    print(f"   Action ID: {action['id']}")
    print(f"   Status: {action['status']}")
    
    # Example 2: Get the preview
    print("\n2. Getting impact preview...")
    
    preview = client.get_preview(action["id"])
    print(f"   Risk Level: {preview['risk_level']}")
    print(f"   Summary: {preview['summary']}")
    
    if preview.get("warnings"):
        print("   Warnings:")
        for warning in preview["warnings"]:
            print(f"     - {warning}")
    
    if preview.get("risk_factors"):
        print("   Risk Factors:")
        for factor in preview["risk_factors"]:
            print(f"     - {factor}")
    
    # Example 3: Get the diff
    print("\n3. Getting file diff...")
    
    diff_result = client.get_diff(action["id"], format="plain")
    print("   Diff output:")
    for line in diff_result["diff"].split("\n")[:10]:
        print(f"     {line}")
    
    # Example 4: Approve or reject
    print("\n4. Action is pending approval...")
    print("   In a real workflow, a human would review and approve/reject.")
    print("   For this demo, we'll auto-approve.")
    
    approved = client.approve(action["id"], comment="Approved via example script")
    print(f"   Status after approval: {approved['status']}")
    
    # Example 5: Execute
    print("\n5. Executing approved action...")
    
    executed = client.execute(action["id"])
    print(f"   Final status: {executed['status']}")
    print(f"   Executed at: {executed['executed_at']}")
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


def decorator_example():
    """Example using the @require_approval decorator."""
    
    api_url = os.getenv("API_URL", "http://localhost:8000")
    api_key = os.getenv("AGENT_API_KEY", "")
    
    client = AgentPolisClient(api_url=api_url, api_key=api_key)
    
    # Define a dangerous function with approval required
    @client.require_approval(action_type="file_write", auto_approve_if_low_risk=True)
    def write_to_temp_file(path: str, content: str):
        """This function requires approval before execution."""
        print(f"Writing to {path}...")
        # In a real scenario, this would write the file
        # with open(path, 'w') as f:
        #     f.write(content)
        print("Write complete!")
        return True
    
    # When called, this will:
    # 1. Submit action for approval
    # 2. Wait for approval (or auto-approve if low risk)
    # 3. Execute only if approved
    try:
        result = write_to_temp_file("/tmp/safe_file.txt", "Hello, World!")
        print(f"Result: {result}")
    except ActionRejectedError as e:
        print(f"Action was rejected: {e.reason}")
    except ActionTimedOutError as e:
        print(f"Timed out waiting for approval: {e.timeout}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--decorator":
        decorator_example()
    else:
        main()
