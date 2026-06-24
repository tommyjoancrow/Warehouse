# 🏭 Warehouse

> *This README was written entirely by Claude (claude-sonnet-4-6).*

A personal 4-in-1 database app for **notetaking, writing, task management, and CRM** — built in about one day using Claude Code. Born from the frustration of not being able to find purchasable software that combined the power of a professional CRM with the writing-friendliness of a notetaking app.

The closest retail product is Airtable — it's fundamentally a database in the same way — but Airtable is not designed for writing and notetaking. Warehouse is. It weaves in the best writing-oriented features from tools like Roam Research, Obsidian, and Notion, while keeping the full power of a structured database underneath.

---

## Who it's for

- **Writers and content creators** managing large portfolios of work across topics, styles, and stages of completion
- **Researchers** who need to query, filter, and cross-reference a large body of notes
- **Small businesses** that want CRM-style power without proprietary software
- **Anyone pitching editors**, tracking publication status, repurposing old writing, or mining a writing archive for gems
- **Power users** who have outgrown Notion or Obsidian but don't want to pay for enterprise CRM software

---

## What makes it different

Most of these features are rare or absent in notetaking apps, and several are missing from Airtable entirely.

### Rich text in every field ✦ *rare in databases*
Every text field can be a full rich-text editor — bold, italics, bullet lists, ordered lists, hyperlinks, tables, and clickable checklists — not just the "notes" field. Airtable's long-text fields are plain text. Here, any field can hold structured writing.

### Inline record linking with `[[` ✦ *Roam/Obsidian-style, rare in databases*
Type `[[` in any rich-text field to search and link to another record inline, wiki-style. The link renders as a clickable chip. Click it to open the linked record, or use the tooltip to edit or remove the link. This is the kind of associative linking that makes Roam Research and Obsidian powerful, brought into a structured database.

### Backlinks with full filter + sort ✦ *not found in Airtable*
Every record can show which other records link back to it — and those backlinks are fully filterable and sortable, just like a main view. For example: *"Show me all Tasks linked to this Project where Status = Open and Due Date is within 7 days."* Airtable has linked record rollups, but not queryable backlink views.

### Relative date filters ✦ *rare in databases*
Filter by *overdue*, *upcoming*, *within N days*, *next N days*, *past N days* — without writing formulas. Airtable requires formula fields to approximate this. Useful for surfacing what needs attention right now.

### Templates with keyboard insertion ✦ *rare in databases*
Create reusable rich-text snippets in Settings. Press `Ctrl+/` in any rich-text field to open the template picker — type to filter, ↑↓ to navigate, Enter to insert. Good for boilerplate structures, headers, or recurring note formats.

### Calendar views on any date field ✦ *rare*
Any date field can power a calendar view — due date, completion date, posting date, publication date. Month and week modes. Switch between them with a toggle; jump to today with one click. This means you can build a social media content calendar, a project deadline tracker, and a submission tracker all in the same database, each as its own calendar view.

### Infinitely nestable views ✦ *not found in Airtable*
Views can be nested under other views for organization. Airtable has flat view lists. Here you can group related views into hierarchies — for example, a "Writing" parent view with children for "In Progress," "Pitched," and "Published."

### Named browser tabs
The browser tab shows the record's name when you open a record — not just "Record." Small thing, but useful when you have multiple records open.

### Backdating ✦ *rare in notetaking apps*
Created and Modified dates are stored and editable, so you can accurately date historical entries. Most notetaking apps stamp the current date and don't let you change it.

### Home view
Set any view as your home — the app opens directly to it on launch.

### Bulk editing ✦ *rare in notetaking apps*
Select multiple records and archive them, delete them, or set a field to the same value across all of them at once. Essential for managing a large writing portfolio.

### Configurable search results
Search results appear as a real view — configure it as grid or card, choose which fields to show, and save those defaults. Your search results look and behave exactly like any other view.

---

## Full Feature List

### Views
- **Grid** — spreadsheet-style with inline cell editing
- **Card** — visual cards; configure which fields show and body text length (1 / 3 / full lines)
- **Calendar** — month and week toggle, Today button, any date field as the calendar axis
- Multiple saved views per database, each with independent filters, sorts, and field visibility
- Views can be nested for organization
- Set any view as **home** — opens on launch

### Filtering & Sorting
- Filter by any field type
- Relative date operators: *overdue*, *upcoming*, *within N days*, *next N days*, *past N days*
- AND / OR filter groups
- Multiple sort conditions, drag to reorder
- Sort select fields by option order (not A–Z)
- Pin field — pinned records always float to top

### Rich Text
- Full Quill editor in every long-text field
- Bold, italic, underline, ordered lists, bullet lists, links
- `[ ]` — checkbox (type in a rich-text field)
- `Ctrl+Shift+C` — clickable checklist block
- `Ctrl+Shift+T` — insert table (set rows × cols, then Enter)
- `Ctrl+/` — insert a saved template (type to filter, ↑↓, Enter)
- `[[` — link to another record inline (click the link to open, edit, or remove)

### Linked Records & Backlinks
- Link fields connect records; chips are clickable to open the linked record
- Backlink fields show reverse links with full filter + sort support

### Records & Fields
- Auto Created / Modified date fields — always accurate, no setup
- Backdating supported
- Named browser tabs (tab shows record name)
- Autosave 700ms after any change, plus `beforeunload` flush
- Archive — hide records from views without deleting
- Trash with restore

### Bulk Actions
- Select multiple records
- Bulk archive, bulk delete, bulk field edit

### Templates
- Reusable rich-text snippets, editable in Settings
- Insert with `Ctrl+/` from any rich-text field

### Search
- Global search from sidebar (`Ctrl+K`)
- Results rendered as a configurable view (grid or card, saved field preferences)

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl K` | Search (from sidebar) |
| `Ctrl B` | Bold |
| `Ctrl I` | Italic |
| `Ctrl U` | Underline |
| `Ctrl Shift 7` | Ordered list |
| `Ctrl Shift 8` | Bullet list |
| `Ctrl K` | Insert link |
| `Ctrl Shift C` | Checklist (clickable checkboxes) |
| `Ctrl Shift T` | Insert table — set rows × cols, Enter |
| `[ ]` | Checkbox (type in a rich-text field) |
| `Ctrl /` | Insert a template — ↑↓, Enter |
| `[[` | Link to another record — type to filter, ↑↓, Enter |

---

## Tech Stack

- **Backend:** Python 3 / Flask 3.x
- **Database:** SQLite (EAV schema — tables, columns, records, cell values)
- **Rich text:** Quill.js 1.3.6
- **Frontend:** Vanilla JS, no framework

---

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

The database (`notes.db`) is created automatically on first run and is gitignored — your data never leaves your machine.
