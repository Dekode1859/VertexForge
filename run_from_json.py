"""
Execute a JSON config file through the VertexForge compiler.

Usage:
    python run_from_json.py <config.json> ["input text"]
    
Example:
    python run_from_json.py generated/abc123.json "Analyze renewable energy"
    python run_from_json.py examples/research_pipeline.json
"""

import json
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from compiler import GraphBuilder
from schema import load_config

load_dotenv()


def print_section(title, char="="):
    """Print a formatted section header."""
    print("\n" + char * 70)
    print(title)
    print(char * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_from_json.py <config.json> [input text]")
        print("\nExamples:")
        print('  python run_from_json.py examples/research_pipeline.json')
        print('  python run_from_json.py my_config.json "What is AI?"')
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Check if file exists
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        print(f"\nLooking in: {Path.cwd()}")
        print(f"Available configs: {list(Path('.').glob('**/*.json'))}")
        sys.exit(1)
    
    # Load config
    print_section("LOADING CONFIGURATION")
    print(f"File: {config_path}")
    
    try:
        config = load_config(config_path)
        print(f"Graph: {config.graph_name}")
        print(f"Version: {config.version}")
        print(f"Nodes: {[n.node_id for n in config.nodes]}")
        print(f"Description: {config.description or 'N/A'}")
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Get input
    if len(sys.argv) >= 3:
        user_input = sys.argv[2]
    else:
        # Try to get from config if available
        with open(config_path, 'r') as f:
            raw_config = json.load(f)
        user_input = raw_config.get('test_input', 'Hello, process this input.')
    
    print(f"\nInput: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
    
    # Build graph
    print_section("COMPILING GRAPH")
    try:
        builder = GraphBuilder(config_path)
        app = builder.build()
        print("[OK] Graph compiled successfully")
    except Exception as e:
        print(f"[FAIL] Compilation error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Check for API key
    if not os.getenv("OLLAMA_API_KEY"):
        print_section("WARNING", "!")
        print("OLLAMA_API_KEY not found in environment!")
        print("Add it to .env file to run the agent.")
        sys.exit(1)
    
    # Execute
    print_section("EXECUTING AGENT SYSTEM")
    
    try:
        result = app.invoke({
            "messages": [HumanMessage(content=user_input)],
            "current_node": "START",
            "iteration_count": 0
        })
        
        # Display final output
        print_section("FINAL OUTPUT")
        print(result["messages"][-1].content)
        
        # Execution stats
        print_section("EXECUTION STATS")
        print(f"Nodes visited: {result.get('iteration_count', 'N/A')}")
        print(f"Final agent: {result.get('current_agent', 'N/A')}")
        print(f"Total messages: {len(result.get('messages', []))}")
        
        # Show conversation history
        if result.get('messages'):
            print_section("CONVERSATION HISTORY")
            for i, msg in enumerate(result['messages'][:10], 1):  # Show first 10
                content = msg.content[:100] if hasattr(msg, 'content') else str(msg)[:100]
                msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
                print(f"\n{i}. [{msg_type}]")
                print(f"   {content}{'...' if len(content) >= 100 else ''}")
        
        print_section("SUCCESS", "=")
        
    except Exception as e:
        print_section("EXECUTION ERROR", "!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
