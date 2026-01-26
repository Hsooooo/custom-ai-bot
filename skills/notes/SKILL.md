---
name: obsidian-notes
description: Read and search Obsidian vault notes
triggers:
  - "notes"
  - "노트"
  - "메모"
  - "obsidian"
  - "daily note"
  - "일기"
  - "기록"
---

## Instructions

The Obsidian vault is located at `/obsidian` in the Docker container.

### Directory Structure

```
/obsidian/
├── Health/          # Auto-generated health reports
├── Exercise/        # Auto-generated exercise logs
├── Daily/           # Daily notes (YYYY-MM-DD.md)
└── Weekly/          # Weekly summaries
```

### Search Notes

To search for content in notes:

```bash
# Search for keyword
grep -r "키워드" /obsidian/ --include="*.md"

# Search in specific folder
grep -r "운동" /obsidian/Exercise/ --include="*.md"

# Find files by name
find /obsidian -name "*2024-01*" -type f
```

### Read Notes

```bash
# Read today's daily note
cat /obsidian/Daily/$(date +%Y-%m-%d).md

# Read yesterday's note
cat /obsidian/Daily/$(date -d "yesterday" +%Y-%m-%d).md

# List recent health reports
ls -la /obsidian/Health/ | tail -10
```

### Response Guidelines

- Summarize note contents in Korean
- Highlight key information
- Offer to search for related notes
