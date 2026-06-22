# MyBase — Work Tracker

A running list of bugs, features, and unfinished work. Newest items go at the
top of each section. When something is done, move it to **Done** with the date.

Status key: 🔴 not started · 🟡 in progress · ✅ done

---

## 🐞 Bugs

_(none reported yet — add them here as we find them)_

---

## ✨ Features wanted

_(add ideas here as they come up)_

---

## 🚧 Known unfinished work (from the tables-model rewrite)

These are things I know are incomplete or rough after the big rewrite to the
tables/columns/records/views model.

- 🔴 **Link filter UX is raw.** The "links to" filter expects you to type a record
  *id* into the value box instead of picking a record by name.
- 🔴 **No way to reorder views in the sidebar.** Position is stored but
  there's no UI to change it.
- 🔴 **Inline edit reloads the whole page** after every cell save. Works, but
  feels heavy — could update just the cell in place.
- 🔴 **Single vs. multi-link not enforced.** A "link to record" column always
  allows multiple links. No option yet for "only one linked record."
- 🔴 **Select/multiselect options have no colors.** Airtable-style colored option
  chips would be nice.
- 🔴 **Bulk edit doesn't cover link fields well.** Tag/multiselect bulk edit takes
  comma-separated text; link fields aren't offered a record picker in bulk edit.

---

## ✅ Done

- ✅ 2026-06-21 — View header & toolbar cleanup:
  - Removed **"in Workspace"** subtitle from the view header.
  - Added a **▾ dropdown** next to the view title with: **Save changes to view**, **Save as new view**, and **Detail layout**. Replaces the old "Update X" toolbar button.
  - **Detail layout** is also accessible from the **···** menu on each view in the sidebar (navigates to the view and auto-opens the modal).
  - Added **Card details** button (card view only) and **Calendar item details** button (calendar view only) in the toolbar. These control which fields appear on card faces / calendar event blocks respectively — separate from the per-record detail layout.
  - Toolbar and header both fit on one line.

- ✅ 2026-06-21 — Grid/column/bulk/calendar batch:
  - Fixed the half-hidden **insert-field (+) buttons** between column headers and
    moved the **field-options caret (▾)** to sit right next to the header text.
  - **Add Field** is now a two-step chooser: *Add an existing field* (lists the
    fields hidden in this view) or *Create a new field*. Removed the old
    **Columns** toolbar button and the trailing **+** column on the right.
  - **Bulk actions** on selected records: **Archive**, **Delete (trash)**, and
    **bulk-edit any field** (pick a field + value, applied to all selected).
  - **Archive** works per the original spec: archived records are hidden from
    views by default, excluded from search, and shown (dimmed, sorted to the
    bottom) via a **Show archived** toggle that appears when archived records
    exist. Unarchive via bulk action while viewing archived.
  - Added a **Pin** field (checkbox). **New views default to sorting by Pin
    first, then date modified** (multi-sort). Sorting by record metadata
    (`_updated_at` / `_created_at`) is now supported.
  - **Calendar fixed**: the per-day **+** pre-fills that day into the date
    column, and events are **drag-to-reschedule** (drop on another day updates
    the date). Calendar is a per-view type with a date-column anchor selector.

- ✅ 2026-06-21 — Sidebar/view cleanup + per-view detail layouts:
  - Removed the standalone **Calendar** sidebar link and the seeded **Task
    calendar** view. Calendar is now a view *type* (grid / cards / calendar) that
    any view can use, with a toolbar selector to **anchor on any date column**.
  - Fixed the **duplicate "All records"** (removed the hardcoded base-table link;
    the real "All records" *view* is canonical, and `/` lands there).
  - Removed field-type labels under grid column headers and in the detail view.
  - Detail view: each field has a **▾ caret to edit the field** (rename / type /
    options / delete) inline.
  - **Per-view detail layout** ("Detail layout" toolbar button): choose which
    fields show when opening a record *from that view*. Records opened from a
    view carry `?view=` so the right layout applies. Saving only writes the
    fields actually shown (hidden fields are preserved).
  - **Inline editing for all field types in the grid**, including tag,
    multi-select, and link (popover editors); only rich-text still opens the
    record. Added a row **⤢ expand** button to open the full record.
- ✅ 2026-06-21 — Grid column improvements: **drag to reorder columns**
  (per-view order), **click a header to sort** by it, **caret menu** per column
  (Edit field / Hide field / Delete field), **"+" between columns** to insert a
  field (pick an existing hidden field or create a new one), and removed the
  bottom "new record" line. Added a new **Tag list** column type (comma-separated,
  with autocomplete from tags already used in that column).
- ✅ 2026-06-21 — Collapsed to a **single workspace table**. The sidebar now
  lists **views** (Companies, People, Tasks, Notes…) instead of tables — each
  is a saved filter (on a Type column) + hidden-column set into the one table.
  Adding a record from a view pre-fills that view's filter values so it lands
  in the right place. Removed table create/rename/delete UI.
- ✅ 2026-06-21 — Rewrote data model to tables/columns/records/views
  (Access/FileMaker-style). Grid/card/calendar views, record editor with typed
  fields + rich text + link picker, trash, search. _(commit 31eef30)_
- ✅ 2026-06-21 — Set up git repo + periodic commits. Snapshotted old
  folders/notes DB before rewrite. _(commits f21c003, facb34d)_

---

## 📌 Notes for future me

- Old folders/notes app is preserved at commit **f21c003**; old sample DB at
  **facb34d** if we ever need to restore it.
- Filter/sort runs in Python (see `apply_view` in `app.py`) — fine for personal
  data sizes, revisit if a table gets very large.
- Column data is stored EAV-style in `cell_values`; link/multiselect values are
  JSON in the cell.
