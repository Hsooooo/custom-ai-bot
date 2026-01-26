#!/usr/bin/env python3
"""Test script for agent tools (can run without full dependencies)."""
import sys
import importlib.util


def load_module(name, path):
    """Load a module from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    print("Testing Agent Tools System")
    print("=" * 50)

    # Load modules
    registry_mod = load_module("registry", "agent/tools/registry.py")
    health_mod = load_module("health", "agent/tools/health.py")
    exercise_mod = load_module("exercise", "agent/tools/exercise.py")
    calendar_mod = load_module("calendar", "agent/tools/calendar.py")

    ToolRegistry = registry_mod.ToolRegistry

    print("\n✓ All modules loaded successfully")

    # Create registry
    registry = ToolRegistry()

    # Register all tools
    health_mod.register_health_tools(registry)
    exercise_mod.register_exercise_tools(registry)
    calendar_mod.register_calendar_tools(registry)

    print(f"✓ Registered {len(registry.list_tools())} tools:")
    for tool_name in registry.list_tools():
        print(f"  - {tool_name}")

    # Test tool definitions format
    print("\n✓ Tool definitions (Claude/Anthropic format):")
    print("-" * 50)
    for tool_def in registry.get_tool_definitions():
        print(f"\nTool: {tool_def['name']}")
        print(f"Description: {tool_def['description']}")
        print(f"Parameters: {list(tool_def['input_schema']['properties'].keys())}")
        print(f"Required: {tool_def['input_schema'].get('required', [])}")

    # Test calendar tool (placeholder - doesn't need DB)
    print("\n" + "=" * 50)
    print("Testing calendar tool (placeholder):")
    print("-" * 50)
    result = calendar_mod.get_calendar_events(date="today", days=1)
    print(f"Result: {result[0]['status']}")
    print(f"Message: {result[0]['message']}")

    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    print("\nNote: Health and exercise tools require database connection.")
    print("They will be tested in the Docker environment.")


if __name__ == "__main__":
    main()
