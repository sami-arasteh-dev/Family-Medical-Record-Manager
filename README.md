# Family Medical Record Manager

A local-first, Flask-based application for managing family medical records, tracking health events, and leveraging configurable AI endpoints to generate structured clinical summaries and action timelines.

## 📋 Overview

This project provides a centralized, offline-capable platform for organizing health data across multiple family members. It supports comprehensive medical history logging, secure local document storage, and optional AI-assisted analysis that converts raw health data into prioritized medical timelines and printable reports. All data is stored locally in SQLite; no external database or cloud storage is required.

## ✨ Features

- **Family Member Management:** CRUD operations for profiles including demographics, emergency contacts, and lifestyle data.
- **Structured Health Tracking:** Dedicated tables for conditions, surgeries, hospitalizations, allergies, medications, family history, habits, vaccinations, physicians, and medical events.
- **Document Upload & Storage:** Secure local storage for images, PDFs, and office documents with MIME validation and size limits (25 MB max).
- **AI-Driven Analysis:** Configurable LLM integration that processes full member profiles or uploaded documents against a strict JSON schema. Outputs include summaries, red flags, observations, suggested tests, and medication/lifestyle review points.
- **Action Timeline Generation:** Automatically extracts timeline items from AI responses, stores them as trackable tasks with priority and due dates, and allows status toggling (`pending` ↔ `done`).
- **Printable Reports:** Clean, print-optimized HTML/CSS layout for exporting member summaries, AI analysis, and action items.
- **Local-First & Self-Contained:** Single `app.py` entry point, auto-initializing SQLite schema, and local file system storage.

## 🏗 Architecture & Structure

```
project-root/
├── app.py                  # Flask application, routing, DB logic, AI integration
├── family_medical.db       # SQLite database (auto-created on first run)
├── uploads/                # Local directory for uploaded documents/images
├── templates/              # Jinja2 HTML templates (base, index, member, forms, report, settings)
└── static/                 # CSS/JS assets (style.css referenced in templates)
```

**Data Flow:**  
1. User submits forms → Flask routes validate input → SQLite inserts/updates records.  
2. AI Analysis triggered → `get_member_data()` aggregates all tables → `make_prompt()` constructs JSON schema + patient data → `requests.post()` sends to configured LLM endpoint → Response parsed → `ai_analyses` and `action_items` tables updated.  
3. Report generation → `get_member_data()` fetched → `report.html` rendered with `print_mode` flag.

## 📦 Prerequisites

- Python 3.8+
- `pip` package manager
- Access to an external LLM API (compatible with OpenAI-style `/chat/completions` endpoint)

## 🛠 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <project-directory>
   ```

2. **Install dependencies:**
   ```bash
   pip install flask requests
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```
   The server will start at `http://0.0.0.0:5000`.

## ⚙️ Configuration

- **Database:** Automatically initialized on first run. Schema includes 15 tables with foreign key constraints and cascade deletes.
- **AI Settings:** Accessible via `/settings`. Configure:
  - `Base URL`: API endpoint (default: `https://api.gapgpt.app/v1`)
  - `API Key`: Bearer token for authentication
  - `Model`: Target LLM identifier (default: `gpt-4o`)
  - `System Prompt`: Optional custom instructions appended to the AI prompt
- **File Limits:** Maximum upload size is 25 MB (`app.config["MAX_CONTENT_LENGTH"]`). Allowed extensions: `png, jpg, jpeg, webp, gif, pdf, txt, csv, doc, docx, xls, xlsx`.

## 📖 Usage Guide

1. **Add a Family Member:** Navigate to `+ عضو جدید` (New Member), fill in required fields, and save.
2. **Populate Medical Records:** On the member dashboard, use the inline forms to log conditions, surgeries, medications, allergies, etc.
3. **Upload Documents:** Use the document section to attach reports or images. Specify category, date, and description.
4. **Run AI Analysis:** Click `تحلیل کل پرونده با AI` (Analyze Full Profile) or `تحلیل AI` on a specific document. The system will query the LLM, parse the JSON response, and populate the Timeline and AI Analysis sections.
5. **Manage Action Items:** In the Timeline tab, toggle items as completed. Items are linked to the generating AI analysis.
6. **Generate Report:** Click `گزارش پزشکی` (Medical Report) to open a print-optimized view. Use browser print/PDF export.

## 🗄 Database Schema Overview

| Table | Purpose |
|-------|---------|
| `settings` | API configuration & system prompt |
| `family_members` | Core demographic & contact data |
| `conditions`, `surgeries`, `hospitalizations` | Clinical history |
| `allergies`, `medications` | Safety & pharmacology |
| `family_history`, `habits`, `vaccinations` | Preventive & lifestyle data |
| `doctors`, `medical_events` | Care team & timeline logs |
| `documents` | Uploaded file metadata & AI analysis cache |
| `ai_analyses` | LLM request/response logs |
| `action_items` | Extracted timeline tasks with status |

All clinical tables reference `family_members.id` with `ON DELETE CASCADE`.

## 🔍 Technical Notes & Security

- **No Authentication:** This is a local-first tool. Access control is not implemented. Restrict network exposure if deploying beyond localhost.
- **API Key Storage:** Stored in plaintext in SQLite. The settings page explicitly warns against network deployment without encryption/auth.
- **AI Fallback:** If the LLM returns malformed JSON, the system gracefully stores the raw text with a `parse_warning` flag instead of crashing.
- **Foreign Keys:** Enabled via `PRAGMA foreign_keys=ON`. Deletion of a member cascades to all related tables.
- **File Handling:** Uses `werkzeug.utils.secure_filename` and explicit MIME/type validation to prevent path traversal and unsafe uploads.

## 🧪 Development

- The application follows a monolithic Flask pattern. Routes, DB helpers, and AI logic are centralized in `app.py` for simplicity.
- Templates use standard Jinja2 inheritance (`base.html` → child templates).
- To extend: Add new record types by updating `FIELD_MAP` in `app.py`, creating corresponding form sections in `member.html`, and adding tables to `init_db()`.

## ⚠️ Disclaimer

This software is intended for health information organization and clinical communication support. It does not provide medical diagnoses, treatment recommendations, or replace professional healthcare advice. AI-generated insights are probabilistic and must be verified by qualified medical professionals.

## 📄 License

License information is not specified in the provided files. Please refer to the repository root or original source for licensing terms.
