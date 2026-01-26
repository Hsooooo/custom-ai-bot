---
name: test
description: Run pytest tests for Clawd
triggers:
  - "test"
  - "테스트"
  - "pytest"
---

## Instructions

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov

# Run specific test file
pytest tests/{test_file}.py -v

# Run specific test function
pytest tests/{test_file}.py::{test_function} -v
```

Test files location: `tests/`
- `conftest.py` - fixtures (health data, activities)
- `test_db.py` - database tests
- `test_garmin_parser.py` - Garmin data parsing
- `test_markdown_generator.py` - Obsidian markdown generation
