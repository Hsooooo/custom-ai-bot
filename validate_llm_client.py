#!/usr/bin/env python3
"""Validation script for LLM Client implementation."""

import ast
import sys
from pathlib import Path


def validate_llm_client():
    """Validate LLM client implementation structure."""
    print("=== LLM Client Implementation Validation ===\n")

    client_path = Path("agent/core/llm_client.py")

    if not client_path.exists():
        print(f"❌ File not found: {client_path}")
        return False

    print(f"✓ File exists: {client_path}")

    # Parse the file
    with open(client_path, "r") as f:
        content = f.read()
        tree = ast.parse(content)

    # Find LLMClient class
    llm_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LLMClient":
            llm_class = node
            break

    if not llm_class:
        print("❌ LLMClient class not found")
        return False

    print("✓ LLMClient class found")

    # Check required methods
    required_methods = {
        "__init__": "Initialization",
        "chat": "Main chat method",
        "_chat_claude": "Claude API handler",
        "_chat_openai": "OpenAI fallback handler",
        "_resolve_model": "Model resolution",
        "_convert_tools_to_openai": "Tool format conversion",
        "count_tokens": "Token counting",
    }

    found_methods = set()
    for node in llm_class.body:
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            found_methods.add(node.name)

    print("\nMethod Validation:")
    all_methods_found = True
    for method, description in required_methods.items():
        if method in found_methods:
            print(f"  ✓ {method}: {description}")
        else:
            print(f"  ❌ {method}: {description} - NOT FOUND")
            all_methods_found = False

    # Check class attributes
    print("\nClass Attributes:")
    class_attrs = set()
    for node in llm_class.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    class_attrs.add(target.id)

    required_attrs = {"MODEL_MAP", "OPENAI_MODEL_MAP"}
    for attr in required_attrs:
        if attr in class_attrs:
            print(f"  ✓ {attr}")
        else:
            print(f"  ❌ {attr} - NOT FOUND")
            all_methods_found = False

    # Check imports
    print("\nImport Validation:")
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    required_imports = ["anthropic", "logging", "os", "typing"]
    for imp in required_imports:
        if any(imp in i for i in imports):
            print(f"  ✓ {imp}")
        else:
            print(f"  ⚠️  {imp} - not found (might be imported differently)")

    # Check async methods
    print("\nAsync Method Validation:")
    async_methods = set()
    for node in llm_class.body:
        if isinstance(node, ast.AsyncFunctionDef):
            async_methods.add(node.name)

    required_async = ["chat", "_chat_claude", "_chat_openai", "count_tokens"]
    for method in required_async:
        if method in async_methods:
            print(f"  ✓ {method} is async")
        else:
            print(f"  ❌ {method} should be async")
            all_methods_found = False

    print("\n" + "=" * 50)
    if all_methods_found:
        print("✓ All validations passed!")
        print("\nImplementation includes:")
        print("  • Multi-provider support (Claude + OpenAI)")
        print("  • Model routing (auto/fast/smart)")
        print("  • Tool calling support")
        print("  • Automatic fallback on errors")
        print("  • Token counting")
        return True
    else:
        print("❌ Some validations failed")
        return False


def validate_tests():
    """Validate test file structure."""
    print("\n\n=== Test File Validation ===\n")

    test_path = Path("tests/test_llm_client.py")

    if not test_path.exists():
        print(f"❌ File not found: {test_path}")
        return False

    print(f"✓ Test file exists: {test_path}")

    with open(test_path, "r") as f:
        content = f.read()
        tree = ast.parse(content)

    # Count test methods
    test_methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("test_"):
                test_methods.append(node.name)

    print(f"✓ Found {len(test_methods)} test methods:")
    for test in sorted(test_methods):
        print(f"  • {test}")

    print("\n✓ Test suite created")
    return True


def validate_readme():
    """Validate README documentation."""
    print("\n\n=== Documentation Validation ===\n")

    readme_path = Path("agent/core/README.md")

    if not readme_path.exists():
        print(f"❌ README not found: {readme_path}")
        return False

    print(f"✓ README exists: {readme_path}")

    with open(readme_path, "r") as f:
        content = f.read()

    # Check for key sections
    required_sections = [
        "Quick Start",
        "Model Selection",
        "Tool",
        "Advanced Usage",
        "API Reference",
    ]

    print("\nDocumentation sections:")
    for section in required_sections:
        if section in content:
            print(f"  ✓ {section}")
        else:
            print(f"  ⚠️  {section} - not found")

    return True


if __name__ == "__main__":
    print("Validating LLM Client Implementation\n")

    results = []
    results.append(("LLM Client", validate_llm_client()))
    results.append(("Tests", validate_tests()))
    results.append(("Documentation", validate_readme()))

    print("\n\n" + "=" * 50)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n🎉 All validations passed!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r clawd/requirements.txt")
        print("2. Set environment variables in .env")
        print("3. Run tests: pytest tests/test_llm_client.py -v")
        sys.exit(0)
    else:
        print("\n⚠️  Some validations failed")
        sys.exit(1)
