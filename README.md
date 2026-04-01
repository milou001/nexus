# Nexus

**Semantic Search + Document Generation + Reference Cross-Check for Technical Reports**

Nexus is a modular document processing system for ~3000 technical reports with three core capabilities:

```
NEXUS
 ├── Scry — Semantic Search
 ├── Forge — Document Generation
 └── Hawk — Reference Cross-Check
```

## Modules

### 🔮 Scry — Semantic Search
Find relevant content across all reports using natural language queries.

### ⚒️ Forge — Document Generation
Generate new documents based on templates and existing content.

### 🦅 Hawk — Reference Cross-Check
Compare external reports against internal references:
- Detects deviations
- Verifies changes
- Provides justifications (e.g., "previously method X, now method Y because...")

## Tech Stack

- **Backend:** FastAPI + SQLite
- **Frontend:** Vue 3
- **AI:** Ollama (100% local)
- **Language:** Python

## Status

🚧 In Development

## License

MIT
