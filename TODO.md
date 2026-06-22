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

- 🔴 **Calendar "+" doesn't pre-fill the date.** Clicking the `+` on a calendar
  day opens a new record but does not set that day as the date-column value.
- 🔴 **No drag-to-reschedule on the calendar.** In the old version you could drag
  a task to a new day; that isn't wired up in the new model yet.
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

---

## ✅ Done

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
