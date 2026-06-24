# 🏭 Warehouse

A personal database and note-taking app built with Flask and SQLite. Think Airtable, but with a focus on rich-text writing, linked records, and staying out of your way.

## Features

### Rich Text & Writing
- Full rich-text fields powered by Quill — bold, bullets, ordered lists, links
- Type `[ ]` to insert a checkbox inline
- `Ctrl+Shift+C` — insert a clickable checklist block
- `Ctrl+/` — insert a saved template (searchable, ↑↓ to navigate, Enter to insert)
- `[[` — link to another record inline while writing; click the link to open it or edit/remove it

### Views
- **Grid** — spreadsheet-style table with inline editing
- **Card** — visual cards with configurable fields and body text length (1 / 3 / full lines)
- **Calendar** — month and week toggle with a Today button
- Create multiple saved views per database, each with their own filters, sorts, and field visibility
- Set any view as your **home** — the app opens to it on launch

### Filtering & Sorting
- Filter by any field type, including relative date operators: *overdue*, *upcoming*, *within N days*, *next N days*, *past N days*
- AND/OR filter groups
- Sort by option order for select fields (High → Medium → Low, not A–Z)
- **Pin field** — pinned records always float to the top regardless of sort
- All views auto-sort by Pin then Date Modified by default

### Linked Records & Backlinks
- Link fields connect records to each other; chips are clickable to open the linked record
- Backlink fields show which records link back to a given record, with full filter and sort support (e.g. "Tasks where Status = Open and Due Date is within 7 days")

### Other
- **Templates** — reusable rich-text snippets editable in Settings
- **Auto Created / Modified dates** — always accurate, no setup needed
- **Autosave** — all field types save 700ms after you stop typing; no Save button
- **Archive** — hide records from views without deleting them
- **Bulk actions** — select multiple records to archive, delete, or bulk-edit a field
- **Search** — global search with configurable results view (grid or card)
- Keyboard shortcuts panel (`?` button in sidebar)

## Tech Stack

- **Backend:** Python 3 / Flask 3.x
- **Database:** SQLite (EAV schema)
- **Rich text:** Quill.js 1.3.6
- **Frontend:** Vanilla JS, no framework

## Getting Started

1. Clone the repo
2. Install dependencies:
   ```bash
   pip install flask
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Open [http://localhost:5000](http://localhost:5000)

The database (`notes.db`) is created automatically on first run.
