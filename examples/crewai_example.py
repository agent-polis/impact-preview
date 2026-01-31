#!/usr/bin/env python3
"""
Agent Polis + CrewAI Integration Example

This script demonstrates how to use Agent Polis simulations
as a tool in CrewAI agents for decision validation.

Prerequisites:
    pip install agent-polis[crewai]
    # Or: pip install crewai httpx

Usage:
    # First, get an API key by running quickstart.py
    API_KEY=your_api_key python examples/crewai_example.py
"""

import os

# Check for API key
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL", "http://localhost:8000")

if not API_KEY:
    print("ERROR: Please set the API_KEY environment variable")
    print("       Run quickstart.py first to get an API key")
    exit(1)


def main():
    """Demonstrate Agent Polis with CrewAI."""
    
    # Try to import CrewAI
    try:
        from crewai import Agent, Task, Crew
        CREWAI_AVAILABLE = True
    except ImportError:
        CREWAI_AVAILABLE = False
        print("CrewAI not installed. Install with: pip install crewai")
        print("\nShowing standalone client usage instead...\n")
    
    # Import our client (works with or without CrewAI)
    from agent_polis.integrations.crewai import AgentPolisClient
    
    print("=" * 60)
    print("Agent Polis Integration Example")
    print("=" * 60)
    
    # ===== Part 1: Standalone Client Usage =====
    print("\n--- Part 1: Standalone Client ---\n")
    
    with AgentPolisClient(api_url=API_URL, api_key=API_KEY) as client:
        # Check connection
        me = client.get_me()
        print(f"Connected as: {me['name']}")
        
        # Run a quick simulation
        print("\nRunning simulation to validate a calculation...")
        
        result = client.simulate_and_run(
            name="Validate Pricing Logic",
            description="Test that discount calculation is correct",
            code="""
# Pricing logic to validate
base_price = inputs.get('base_price', 100)
discount_percent = inputs.get('discount', 20)

final_price = base_price * (1 - discount_percent / 100)

# Validation
assert final_price > 0, "Price cannot be negative"
assert final_price <= base_price, "Discounted price should not exceed base"

result = {
    'base_price': base_price,
    'discount': discount_percent,
    'final_price': final_price,
    'savings': base_price - final_price,
    'valid': True,
}
print(f"Calculated: ${base_price} - {discount_percent}% = ${final_price}")
""",
            inputs={"base_price": 150, "discount": 25},
        )
        
        if result["success"]:
            print(f"✓ Simulation passed!")
            print(f"  Output: {result['output']}")
        else:
            print(f"✗ Simulation failed: {result['error']}")
    
    # ===== Part 2: CrewAI Integration =====
    if CREWAI_AVAILABLE:
        print("\n--- Part 2: CrewAI Integration ---\n")
        
        from agent_polis.integrations.crewai import create_crewai_tool
        
        # Create the simulation tool
        polis_tool = create_crewai_tool(api_url=API_URL, api_key=API_KEY)
        
        # Create a risk analyst agent that uses simulations
        risk_analyst = Agent(
            role="Risk Analyst",
            goal="Validate business logic before deployment using simulations",
            backstory="""You are a meticulous risk analyst who believes in 
            testing everything before it goes live. You use simulations to 
            validate code and business logic, catching bugs before they 
            cause problems in production.""",
            tools=[polis_tool],
            verbose=True,
        )
        
        # Create a task
        validation_task = Task(
            description="""
            Use the Agent Polis simulation tool to validate this inventory 
            calculation logic:
            
            - Starting stock: 1000 units
            - Daily sales: 50 units
            - Reorder point: 200 units
            - Question: After how many days should we reorder?
            
            Write Python code to simulate this and verify the answer.
            """,
            agent=risk_analyst,
            expected_output="A validated answer with simulation proof",
        )
        
        # Run the crew
        crew = Crew(
            agents=[risk_analyst],
            tasks=[validation_task],
            verbose=True,
        )
        
        print("Running CrewAI with Agent Polis simulation tool...")
        result = crew.kickoff()
        
        print("\n--- Crew Result ---")
        print(result)
    
    print("\n" + "=" * 60)
    print("Integration example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
