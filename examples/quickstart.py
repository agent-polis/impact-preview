#!/usr/bin/env python3
"""
Agent Polis Quick Start Example

This script demonstrates basic usage of the Agent Polis API:
1. Register an agent
2. Create a simulation
3. Run the simulation
4. Check results

Prerequisites:
    pip install httpx

Usage:
    python examples/quickstart.py

    # Or with a custom server URL:
    API_URL=https://your-server.com python examples/quickstart.py
"""

import os

import httpx

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")


def main():
    print("=" * 60)
    print("Agent Polis Quick Start")
    print("=" * 60)
    print(f"\nConnecting to: {API_URL}")

    # Check server health
    print("\n1. Checking server health...")
    response = httpx.get(f"{API_URL}/health", timeout=10)
    if response.status_code != 200:
        print(f"   ERROR: Server not healthy - {response.text}")
        return
    health = response.json()
    print(f"   Status: {health['status']}")
    print(f"   Version: {health['version']}")

    # Check A2A agent card
    print("\n2. Fetching A2A agent card...")
    response = httpx.get(f"{API_URL}/.well-known/agent.json", timeout=10)
    card = response.json()
    print(f"   Name: {card['name']}")
    print(f"   Protocol: {card['protocol']}")
    print(f"   Capabilities: {', '.join(card['capabilities'])}")

    # Register an agent
    print("\n3. Registering a new agent...")
    import uuid
    agent_name = f"quickstart-{uuid.uuid4().hex[:8]}"

    response = httpx.post(
        f"{API_URL}/api/v1/agents/register",
        json={
            "name": agent_name,
            "description": "Quick start example agent",
        },
        timeout=10,
    )

    if response.status_code != 201:
        print(f"   ERROR: Registration failed - {response.text}")
        return

    agent_data = response.json()
    api_key = agent_data["api_key"]
    print(f"   Agent name: {agent_data['name']}")
    print(f"   Agent ID: {agent_data['id']}")
    print(f"   API Key: {api_key[:20]}...")
    print("   (Save this key - it won't be shown again!)")

    # Set up authenticated headers
    headers = {"X-API-Key": api_key}

    # Create a simulation
    print("\n4. Creating a simulation...")
    simulation_code = """
# Calculate Fibonacci sequence
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Generate first 10 numbers
fib_sequence = [fibonacci(i) for i in range(10)]

# Return result
result = {
    "sequence": fib_sequence,
    "sum": sum(fib_sequence),
    "message": "Fibonacci calculation complete!"
}
print(f"Generated sequence: {fib_sequence}")
"""

    response = httpx.post(
        f"{API_URL}/api/v1/simulations",
        headers=headers,
        json={
            "scenario": {
                "name": "Fibonacci Calculator",
                "description": "Calculate Fibonacci sequence in sandbox",
                "code": simulation_code,
                "inputs": {},
                "timeout_seconds": 30,
            }
        },
        timeout=10,
    )

    if response.status_code != 201:
        print(f"   ERROR: Simulation creation failed - {response.text}")
        return

    sim_data = response.json()
    sim_id = sim_data["id"]
    print(f"   Simulation ID: {sim_id}")
    print(f"   Status: {sim_data['status']}")

    # Run the simulation
    print("\n5. Running simulation...")
    response = httpx.post(
        f"{API_URL}/api/v1/simulations/{sim_id}/run",
        headers=headers,
        timeout=60,  # Longer timeout for execution
    )

    if response.status_code != 200:
        print(f"   ERROR: Simulation run failed - {response.text}")
        return

    result = response.json()
    print(f"   Success: {result['success']}")

    if result["success"]:
        print(f"   Output: {result['output']}")
        if result.get("stdout"):
            print(f"   Stdout: {result['stdout'][:200]}")
        print(f"   Duration: {result['duration_ms']}ms")
    else:
        print(f"   Error: {result['error']}")

    # Get agent stats
    print("\n6. Checking agent stats...")
    response = httpx.get(
        f"{API_URL}/api/v1/agents/me/stats",
        headers=headers,
        timeout=10,
    )
    stats = response.json()
    print(f"   Total simulations: {stats['total_simulations']}")
    print(f"   This month: {stats['simulations_this_month']}/{stats['monthly_limit']}")

    # Get simulation event trail
    print("\n7. Fetching audit trail...")
    response = httpx.get(
        f"{API_URL}/api/v1/simulations/{sim_id}/events",
        headers=headers,
        timeout=10,
    )
    events = response.json()
    print(f"   Found {len(events)} events:")
    for event in events:
        print(f"   - {event['type']} at {event['created_at']}")

    print("\n" + "=" * 60)
    print("Quick start complete!")
    print(f"\nYour API key: {api_key}")
    print("Use this key in the X-API-Key header for authenticated requests.")
    print("=" * 60)


if __name__ == "__main__":
    main()
