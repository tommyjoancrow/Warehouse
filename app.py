from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import json
from datetime import datetime, date, timedelta
import calendar as cal_module

app = Flask(__name__)
DB_PATH = "notes.db"

VALID_SORT_FIELDS = {'title','created_at','updated_at','status','due_date','source','is_archived'}

def build_order(sorts):
    parts = []
    for s in (sorts or []):
        f = s.get('f','created_at')
        d = 'DESC' if s.get('d','desc') == 'desc' else 'ASC'
        if f in VALID_SORT_FIELDS:
            parts.append(f'n.{f} {d}')
    if not parts:
        parts.append('n.created_at DESC')
    return 'n.is_archived ASC, ' + ', '.join(parts)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

FIELD_TYPES = ['text','longtext','date','number','url','email','phone',
               'checkbox','select','multiselect','currency','percent','link']

def migrate(conn):
    cols = lambda tbl: [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
    notes_cols = cols('notes')
    if 'is_archived' not in notes_cols:
        conn.execute("ALTER TABLE notes ADD COLUMN is_archived INTEGER DEFAULT 0")
    folder_cols = cols('folders')
    for col, default in [('default_view_type',"'card'"),('default_sort_field',"'created_at'"),
                          ('default_sort_dir',"'desc'"),('default_filters_json',"'[]'"),
                          ('default_filter_logic',"'AND'"),('default_sorts_json',"'[]'"),
                          ('detail_view_mode',"'body'")]:
        if col not in folder_cols:
            conn.execute(f"ALTER TABLE folders ADD COLUMN {col} TEXT DEFAULT {default}")
    # folder_field_settings: field_name key, add display_order if missing
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS folder_field_settings (
            folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            visible_in_detail INTEGER DEFAULT 1,
            display_order INTEGER DEFAULT 100,
            PRIMARY KEY (folder_id, field_name)
        );
    """)
    ffs_cols = cols('folder_field_settings')
    if 'display_order' not in ffs_cols:
        conn.execute("ALTER TABLE folder_field_settings ADD COLUMN display_order INTEGER DEFAULT 100")
    if 'display_label' not in ffs_cols:
        conn.execute("ALTER TABLE folder_field_settings ADD COLUMN display_label TEXT")
    # drop visible_in_table if present (no longer used - table visibility controlled per-session)
    conn.commit()

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tag_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tag_group_id INTEGER REFERENCES tag_groups(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'Untitled',
            body TEXT DEFAULT '',
            folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
            status TEXT DEFAULT 'raw',
            source TEXT DEFAULT '',
            is_task INTEGER DEFAULT 0,
            due_date TEXT DEFAULT NULL,
            is_archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS note_links (
            source_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            PRIMARY KEY (source_id, target_id)
        );
        CREATE TABLE IF NOT EXISTS custom_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            field_type TEXT DEFAULT 'text'
        );
        CREATE TABLE IF NOT EXISTS note_custom_values (
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES custom_fields(id) ON DELETE CASCADE,
            value TEXT DEFAULT '',
            PRIMARY KEY (note_id, field_id)
        );
        CREATE TABLE IF NOT EXISTS saved_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            context_type TEXT DEFAULT 'folder',
            context_id INTEGER,
            filters_json TEXT DEFAULT '[]',
            filter_logic TEXT DEFAULT 'AND',
            sort_field TEXT DEFAULT 'created_at',
            sort_dir TEXT DEFAULT 'desc',
            view_type TEXT DEFAULT 'card',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS folder_field_settings (
            folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            visible_in_detail INTEGER DEFAULT 1,
            visible_in_table INTEGER DEFAULT 1,
            PRIMARY KEY (folder_id, field_name)
        );
    """)
    migrate(conn)

    # Auto-purge trash older than 30 days
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    conn.execute("DELETE FROM notes WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cutoff,))
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0] == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        inbox_id = conn.execute("INSERT INTO folders (name, parent_id, created_at) VALUES ('Inbox',NULL,?)", (now,)).lastrowid
        tasks_id = conn.execute("INSERT INTO folders (name, parent_id, created_at) VALUES ('Tasks',NULL,?)", (now,)).lastrowid
        people_id = conn.execute("INSERT INTO folders (name, parent_id, created_at) VALUES ('People',NULL,?)", (now,)).lastrowid
        writing_id = conn.execute("INSERT INTO folders (name, parent_id, created_at) VALUES ('Writing',NULL,?)", (now,)).lastrowid

        for fname, ftype in [("Email","text"),("Phone","text"),("Company","text"),("Last Contacted","date"),("Notes","text")]:
            conn.execute("INSERT INTO custom_fields (folder_id, name, field_type) VALUES (?,?,?)", (people_id, fname, ftype))
        for fname, ftype in [("Due Date","date"),("Priority","text"),("Done","text")]:
            conn.execute("INSERT INTO custom_fields (folder_id, name, field_type) VALUES (?,?,?)", (tasks_id, fname, ftype))

        people = [
            ("Alice Johnson","<p>Marketing director at Acme Corp. Met at industry conference 2024.</p>","alice@acmecorp.com","555-0101","Acme Corp"),
            ("Bob Martinez","<p>Freelance developer. Strong Python and React. Interested in collaboration.</p>","bob@freelance.dev","555-0102","Independent"),
            ("Clara Smith","<p>Potential client. Small design studio. Follow up about consulting rates.</p>","clara@smithdesign.co","555-0103","Smith Design"),
            ("David Park","<p>Old college friend at Google. Great for tech industry insights.</p>","dpark@gmail.com","555-0104","Google"),
            ("Elena Torres","<p>Journalist at The Atlantic. Met at a reading last spring.</p>","elena@theatlantic.com","555-0105","The Atlantic"),
        ]
        field_ids = [r['id'] for r in conn.execute("SELECT id FROM custom_fields WHERE folder_id=? ORDER BY id",(people_id,)).fetchall()]
        for name, body, email, phone, company in people:
            nid = conn.execute(
                "INSERT INTO notes (title,body,folder_id,status,created_at,updated_at) VALUES (?,?,?,'raw',?,?)",
                (name, body, people_id, now, now)
            ).lastrowid
            for fid, val in zip(field_ids, [email, phone, company, "", ""]):
                conn.execute("INSERT INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)", (nid, fid, val))

        inbox_notes = [
            ("Book recommendation from Alice", "<p>Alice suggested <em>The Creative Act</em> by Rick Rubin. Also mentioned <em>Range</em> by David Epstein.</p>", "2026-01-10 09:00"),
            ("Meeting notes: product kickoff", "<p>Attended the Q1 product kickoff. Key themes: user retention, onboarding flow redesign, and the new mobile app.</p>", "2026-02-14 14:30"),
            ("Ideas from the weekend", "<p>Thought about starting a newsletter. Possible topics: tools I use, productivity systems, book reviews. Weekly cadence?</p>", "2026-03-01 10:00"),
            ("Quote I liked", "<p><em>The secret of getting ahead is getting started.</em> — Mark Twain</p>", "2026-03-15 08:00"),
            ("Research: note-taking apps", "<p>Compared Capacities, Notion, Obsidian, Roam. Capacities has the best object model. Obsidian best for longevity.</p>", "2026-04-02 16:00"),
        ]
        for title, body, created_at in inbox_notes:
            conn.execute(
                "INSERT INTO notes (title,body,folder_id,status,source,created_at,updated_at) VALUES (?,?,?,'raw','',?,?)",
                (title, body, inbox_id, created_at, now)
            )

        today = date.today()
        tasks_data = [
            ("Follow up with Clara about proposal", 1, (today + timedelta(days=2)).isoformat(), "High"),
            ("Write first draft of newsletter", 1, (today + timedelta(days=5)).isoformat(), "Medium"),
            ("Review Bob's project proposal", 1, (today + timedelta(days=1)).isoformat(), "High"),
            ("Schedule dentist appointment", 1, (today + timedelta(days=14)).isoformat(), "Low"),
            ("Read The Creative Act", 1, (today + timedelta(days=30)).isoformat(), "Low"),
        ]
        task_field_ids = [r['id'] for r in conn.execute("SELECT id FROM custom_fields WHERE folder_id=? ORDER BY id",(tasks_id,)).fetchall()]
        for title, is_task, due_date, priority in tasks_data:
            nid = conn.execute(
                "INSERT INTO notes (title,body,folder_id,status,is_task,due_date,created_at,updated_at) VALUES (?,?,?,'raw',?,?,?,?)",
                (title, "", tasks_id, is_task, due_date, now, now)
            ).lastrowid
            if task_field_ids:
                conn.execute("INSERT OR IGNORE INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)", (nid, task_field_ids[0], due_date))
                if len(task_field_ids) > 1:
                    conn.execute("INSERT OR IGNORE INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)", (nid, task_field_ids[1], priority))

        writing_notes = [
            ("Draft: Why I stopped using Notion", "<p>I used Notion for three years. Here's what broke me...</p>", "2025-11-01 10:00"),
            ("Fragment: the morning light", "<p>There is a particular quality to morning light in late October that I keep trying to describe and failing.</p>", "2025-06-15 07:30"),
            ("Essay outline: on slowness", "<p>Thesis: Deliberate slowness is a form of resistance. Sections: 1) The cult of productivity 2) What slowness actually feels like 3) How to practice it</p>", "2026-01-20 21:00"),
        ]
        for title, body, created_at in writing_notes:
            conn.execute(
                "INSERT INTO notes (title,body,folder_id,status,created_at,updated_at) VALUES (?,?,?,'raw',?,?)",
                (title, body, writing_id, created_at, now)
            )

        for group_name, tag_names in [
            ("Priority", ["High","Medium","Low"]),
            ("Type", ["Idea","Reference","Action","Question"]),
            ("Project", ["Personal","Work","Side Project"]),
        ]:
            gid = conn.execute("INSERT INTO tag_groups (name) VALUES (?)", (group_name,)).lastrowid
            for t in tag_names:
                conn.execute("INSERT INTO tags (name,tag_group_id) VALUES (?,?)", (t, gid))

        conn.commit()
    conn.close()

def get_folder_tree(conn, parent_id=None):
    rows = conn.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM notes n WHERE n.folder_id=f.id AND n.deleted_at IS NULL AND n.is_archived=0) as note_count "
        "FROM folders f WHERE f.parent_id IS ? ORDER BY f.name", (parent_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['children'] = get_folder_tree(conn, r['id'])
        result.append(d)
    return result

def get_folder_tree_with_views(conn, saved_views_by_folder, parent_id=None):
    rows = conn.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM notes n WHERE n.folder_id=f.id AND n.deleted_at IS NULL AND n.is_archived=0) as note_count "
        "FROM folders f WHERE f.parent_id IS ? ORDER BY f.name", (parent_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['children'] = get_folder_tree_with_views(conn, saved_views_by_folder, r['id'])
        d['saved_views'] = saved_views_by_folder.get(r['id'], [])
        result.append(d)
    return result

@app.context_processor
def inject_sidebar():
    conn = get_db()
    saved_views_raw = conn.execute("SELECT * FROM saved_views WHERE context_type='folder' ORDER BY name").fetchall()
    saved_views_by_folder = {}
    for sv in saved_views_raw:
        saved_views_by_folder.setdefault(sv['context_id'], []).append(dict(sv))
    folders = get_folder_tree_with_views(conn, saved_views_by_folder)
    tag_groups = []
    for tg in conn.execute("SELECT * FROM tag_groups ORDER BY name").fetchall():
        tags = conn.execute(
            "SELECT t.*, (SELECT COUNT(*) FROM note_tags nt JOIN notes n ON nt.note_id=n.id WHERE nt.tag_id=t.id AND n.deleted_at IS NULL AND n.is_archived=0) as note_count "
            "FROM tags t WHERE t.tag_group_id=? ORDER BY t.name", (tg['id'],)
        ).fetchall()
        tag_groups.append({'id': tg['id'], 'name': tg['name'], 'tags': [dict(t) for t in tags]})
    tag_saved_views = conn.execute("SELECT * FROM saved_views WHERE context_type='tag' ORDER BY name").fetchall()
    all_folders_flat = conn.execute("SELECT * FROM folders ORDER BY name").fetchall()
    all_tag_groups = conn.execute("SELECT * FROM tag_groups ORDER BY name").fetchall()
    all_custom_fields = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
    conn.close()
    return dict(
        sidebar_folders=folders,
        sidebar_tag_groups=tag_groups,
        sidebar_tag_saved_views=[dict(v) for v in tag_saved_views],
        all_folders=[dict(f) for f in all_folders_flat],
        all_tag_groups=[dict(g) for g in all_tag_groups],
        all_custom_fields=[dict(f) for f in all_custom_fields],
        field_types=FIELD_TYPES,
    )

def build_where(filters, filter_logic, params):
    clauses = []
    for f in filters:
        field = f.get('field', '')
        op = f.get('op', 'contains')
        val = f.get('value', '')
        if field in ('title', 'body', 'source', 'status'):
            if op == 'is_empty':
                clauses.append(f"(n.{field} IS NULL OR n.{field} = '')")
            elif op == 'is_not_empty':
                clauses.append(f"(n.{field} IS NOT NULL AND n.{field} != '')")
            elif op == 'contains':
                clauses.append(f"n.{field} LIKE ?"); params.append(f'%{val}%')
            elif op == 'equals':
                clauses.append(f"n.{field} = ?"); params.append(val)
            elif op == 'not_contains':
                clauses.append(f"n.{field} NOT LIKE ?"); params.append(f'%{val}%')
            elif op == 'starts_with':
                clauses.append(f"n.{field} LIKE ?"); params.append(f'{val}%')
        elif field == 'folder':
            if op == 'is_empty':
                clauses.append("n.folder_id IS NULL")
            elif op == 'is_not_empty':
                clauses.append("n.folder_id IS NOT NULL")
            elif op == 'equals':
                clauses.append("n.folder_id IN (SELECT id FROM folders WHERE name = ?)"); params.append(val)
            elif op == 'contains':
                clauses.append("n.folder_id IN (SELECT id FROM folders WHERE name LIKE ?)"); params.append(f'%{val}%')
            elif op == 'not_contains':
                clauses.append("n.folder_id NOT IN (SELECT id FROM folders WHERE name LIKE ?)"); params.append(f'%{val}%')
        elif field in ('due_date', 'created_at'):
            col = 'n.' + field
            if op == 'before':
                clauses.append(f"{col} < ?"); params.append(val)
            elif op == 'after':
                clauses.append(f"{col} > ?"); params.append(val)
            elif op == 'equals':
                clauses.append(f"DATE({col}) = ?"); params.append(val)
            elif op == 'is_empty':
                clauses.append(f"({col} IS NULL OR {col} = '')")
            elif op == 'is_not_empty':
                clauses.append(f"({col} IS NOT NULL AND {col} != '')")
        elif field == 'is_task':
            clauses.append("n.is_task = ?"); params.append(1 if val == '1' else 0)
    if not clauses:
        return "", params
    join = " AND " if filter_logic == 'AND' else " OR "
    return " AND (" + join.join(clauses) + ")", params

def get_notes_with_tags(conn, query, params):
    notes = conn.execute(query, params).fetchall()
    result = []
    for note in notes:
        d = dict(note)
        tags = conn.execute(
            "SELECT t.* FROM tags t JOIN note_tags nt ON t.id=nt.tag_id WHERE nt.note_id=?", (note['id'],)
        ).fetchall()
        d['tags_list'] = [dict(t) for t in tags]
        folder = conn.execute("SELECT id, name FROM folders WHERE id=?", (note['folder_id'],)).fetchone() if note['folder_id'] else None
        d['folder_name'] = folder['name'] if folder else ''
        result.append(d)
    return result

def parse_view_params():
    view_type = request.args.get('view', 'card')
    search = request.args.get('search', '')
    filter_logic = request.args.get('filter_logic', 'AND')
    filters_str = request.args.get('filters', '[]')
    show_archived = request.args.get('show_archived', '0')
    sorts_str = request.args.get('sorts', '')
    try:
        filters = json.loads(filters_str)
    except Exception:
        filters = []
    try:
        sorts = json.loads(sorts_str) if sorts_str else []
    except Exception:
        sorts = []
    if not sorts:
        sf = request.args.get('sort', 'created_at')
        sd = request.args.get('dir', 'desc')
        if sf in VALID_SORT_FIELDS:
            sorts = [{'f': sf, 'd': sd}]
        else:
            sorts = [{'f': 'created_at', 'd': 'desc'}]
    sorts_str = json.dumps(sorts)
    return view_type, sorts, sorts_str, search, filter_logic, filters, filters_str, show_archived

@app.route("/")
def index():
    conn = get_db()
    inbox = conn.execute("SELECT id FROM folders WHERE name='Inbox' LIMIT 1").fetchone()
    conn.close()
    return redirect(url_for('folder_view', folder_id=inbox['id'] if inbox else 1))

@app.route("/folder/<int:folder_id>")
def folder_view(folder_id):
    conn = get_db()
    folder = conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
    if not folder:
        conn.close()
        return redirect(url_for('index'))

    has_params = any(request.args.get(k) for k in ('view','sort','dir','sorts','filters','search','filter_logic'))
    if not has_params:
        view_type = folder['default_view_type'] or 'card'
        dsj = folder['default_sorts_json'] if folder['default_sorts_json'] and folder['default_sorts_json'] != '[]' else None
        if dsj:
            try: sorts = json.loads(dsj)
            except: sorts = [{'f': 'created_at', 'd': 'desc'}]
        else:
            sorts = [{'f': folder['default_sort_field'] or 'created_at', 'd': folder['default_sort_dir'] or 'desc'}]
        sorts_str = json.dumps(sorts)
        filters_str = folder['default_filters_json'] or '[]'
        filter_logic = folder['default_filter_logic'] or 'AND'
        search = ''
        show_archived = '0'
        try:
            filters = json.loads(filters_str)
        except Exception:
            filters = []
    else:
        view_type, sorts, sorts_str, search, filter_logic, filters, filters_str, show_archived = parse_view_params()

    query = "SELECT n.* FROM notes n WHERE n.folder_id=? AND n.deleted_at IS NULL"
    params = [folder_id]
    if show_archived != '1':
        query += " AND n.is_archived=0"
    if search:
        query += " AND (n.title LIKE ? OR n.body LIKE ?)"; params += [f'%{search}%', f'%{search}%']
    extra, params = build_where(filters, filter_logic, params)
    query += extra
    query += f" ORDER BY {build_order(sorts)}"

    notes = get_notes_with_tags(conn, query, params)
    custom_fields = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
    custom_vals = {}
    if notes:
        note_ids = [n['id'] for n in notes]
        for cv in conn.execute(f"SELECT * FROM note_custom_values WHERE note_id IN ({','.join('?'*len(note_ids))})", note_ids).fetchall():
            custom_vals.setdefault(cv['note_id'], {})[cv['field_id']] = cv['value']
    all_tags = conn.execute("SELECT t.*, tg.name as group_name FROM tags t LEFT JOIN tag_groups tg ON t.tag_group_id=tg.id ORDER BY tg.name,t.name").fetchall()
    field_settings = {}
    for fs in conn.execute("SELECT * FROM folder_field_settings WHERE folder_id=?", (folder_id,)).fetchall():
        field_settings[fs['field_name']] = dict(fs)
    conn.close()
    return render_template('list_view.html',
        page_title=folder['name'], context_type='folder', context_id=folder_id,
        folder=dict(folder), notes=notes,
        view_type=view_type, sorts=sorts, sorts_str=sorts_str,
        search=search, filter_logic=filter_logic, filters=filters, filters_str=filters_str,
        show_archived=show_archived,
        custom_fields=[dict(f) for f in custom_fields], custom_vals=custom_vals,
        all_tags=[dict(t) for t in all_tags],
        field_settings=field_settings,
        active_folder_id=folder_id, saved_view_obj=None,
    )

@app.route("/tag/<int:tag_id>")
def tag_view(tag_id):
    conn = get_db()
    tag = conn.execute("SELECT * FROM tags WHERE id=?", (tag_id,)).fetchone()
    if not tag:
        conn.close()
        return redirect(url_for('index'))
    view_type, sorts, sorts_str, search, filter_logic, filters, filters_str, show_archived = parse_view_params()
    query = "SELECT n.* FROM notes n JOIN note_tags nt ON n.id=nt.note_id WHERE nt.tag_id=? AND n.deleted_at IS NULL"
    params = [tag_id]
    if show_archived != '1':
        query += " AND n.is_archived=0"
    if search:
        query += " AND (n.title LIKE ? OR n.body LIKE ?)"; params += [f'%{search}%', f'%{search}%']
    extra, params = build_where(filters, filter_logic, params)
    query += extra + f" ORDER BY {build_order(sorts)}"
    notes = get_notes_with_tags(conn, query, params)
    all_tags = conn.execute("SELECT t.*, tg.name as group_name FROM tags t LEFT JOIN tag_groups tg ON t.tag_group_id=tg.id ORDER BY tg.name,t.name").fetchall()
    conn.close()
    return render_template('list_view.html',
        page_title=f'#{tag["name"]}', context_type='tag', context_id=tag_id,
        folder=None, notes=notes,
        view_type=view_type, sorts=sorts, sorts_str=sorts_str,
        search=search, filter_logic=filter_logic, filters=filters, filters_str=filters_str,
        show_archived=show_archived,
        custom_fields=[], custom_vals={},
        all_tags=[dict(t) for t in all_tags],
        all_standard_fields=[],
        active_tag_id=tag_id, saved_view_obj=None,
    )

@app.route("/view/<int:view_id>")
def saved_view(view_id):
    conn = get_db()
    sv = conn.execute("SELECT * FROM saved_views WHERE id=?", (view_id,)).fetchone()
    if not sv:
        conn.close()
        return redirect(url_for('index'))
    sv_dict = dict(sv)
    filters = json.loads(sv_dict.get('filters_json', '[]'))
    filter_logic = sv_dict.get('filter_logic', 'AND')
    sorts = [{'f': sv_dict.get('sort_field','created_at'), 'd': sv_dict.get('sort_dir','desc')}]
    sorts_str = json.dumps(sorts)
    view_type = sv_dict.get('view_type', 'card')
    filters_str = sv_dict.get('filters_json', '[]')
    show_archived = '0'

    if sv_dict['context_type'] == 'folder':
        query = "SELECT n.* FROM notes n WHERE n.folder_id=? AND n.deleted_at IS NULL AND n.is_archived=0"
    else:
        query = "SELECT n.* FROM notes n JOIN note_tags nt ON n.id=nt.note_id WHERE nt.tag_id=? AND n.deleted_at IS NULL AND n.is_archived=0"
    params = [sv_dict['context_id']]
    extra, params = build_where(filters, filter_logic, params)
    query += extra + f" ORDER BY {build_order(sorts)}"
    notes = get_notes_with_tags(conn, query, params)
    folder = conn.execute("SELECT * FROM folders WHERE id=?", (sv_dict['context_id'],)).fetchone() if sv_dict['context_type'] == 'folder' else None
    all_tags = conn.execute("SELECT t.*, tg.name as group_name FROM tags t LEFT JOIN tag_groups tg ON t.tag_group_id=tg.id ORDER BY tg.name,t.name").fetchall()
    conn.close()
    return render_template('list_view.html',
        page_title=sv_dict['name'], context_type=sv_dict['context_type'], context_id=sv_dict['context_id'],
        folder=dict(folder) if folder else None, notes=notes,
        view_type=view_type, sorts=sorts, sorts_str=sorts_str,
        search='', filter_logic=filter_logic, filters=filters, filters_str=filters_str,
        show_archived=show_archived,
        custom_fields=[], custom_vals={},
        all_tags=[dict(t) for t in all_tags],
        all_standard_fields=[],
        active_view_id=view_id, saved_view_obj=sv_dict,
    )

@app.route("/search")
def search_view():
    q = request.args.get('q', '')
    show_archived = request.args.get('show_archived', '0')
    conn = get_db()
    notes = []
    if q:
        archived_clause = "" if show_archived == '1' else " AND n.is_archived=0"
        rows = conn.execute(
            f"SELECT n.* FROM notes n WHERE (n.title LIKE ? OR n.body LIKE ?) AND n.deleted_at IS NULL{archived_clause} ORDER BY n.updated_at DESC LIMIT 100",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
        for note in rows:
            d = dict(note)
            tags = conn.execute("SELECT t.* FROM tags t JOIN note_tags nt ON t.id=nt.tag_id WHERE nt.note_id=?", (note['id'],)).fetchall()
            d['tags_list'] = [dict(t) for t in tags]
            folder = conn.execute("SELECT name FROM folders WHERE id=?", (note['folder_id'],)).fetchone() if note['folder_id'] else None
            d['folder_name'] = folder['name'] if folder else ''
            notes.append(d)
    conn.close()
    return render_template('search_results.html', notes=notes, q=q, show_archived=show_archived)

@app.route("/calendar")
def calendar_view():
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    conn = get_db()
    tasks = conn.execute(
        "SELECT * FROM notes WHERE is_task=1 AND due_date IS NOT NULL AND deleted_at IS NULL AND is_archived=0 ORDER BY due_date"
    ).fetchall()
    conn.close()
    tasks_by_date = {}
    for t in tasks:
        d = (t['due_date'] or '')[:10]
        if d:
            tasks_by_date.setdefault(d, []).append(dict(t))
    grid = cal_module.monthcalendar(year, month)
    month_name = datetime(year, month, 1).strftime('%B %Y')
    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year
    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year
    return render_template('calendar.html',
        grid=grid, month=month, year=year, month_name=month_name,
        tasks_by_date=tasks_by_date,
        prev_month=prev_month, prev_year=prev_year,
        next_month=next_month, next_year=next_year,
        today=date.today().isoformat(), active_page='calendar',
    )

@app.route("/trash")
def trash_view():
    conn = get_db()
    notes = conn.execute("SELECT * FROM notes WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC").fetchall()
    conn.close()
    return render_template('trash.html', notes=[dict(n) for n in notes], active_page='trash')

@app.route("/folder/<int:folder_id>/settings", methods=["GET","POST"])
def folder_settings(folder_id):
    conn = get_db()
    folder = conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
    if not folder:
        conn.close()
        return redirect(url_for('index'))
    if request.method == "POST":
        detail_mode = request.form.get('detail_view_mode', 'body')
        conn.execute("UPDATE folders SET detail_view_mode=? WHERE id=?", (detail_mode, folder_id))
        std_fields = ['title','body','status','source','created_at','updated_at','due_date','tags','folder']
        all_cfs = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
        all_field_names = std_fields + [f'cf_{cf["id"]}' for cf in all_cfs]
        for i, fname in enumerate(all_field_names):
            visible_detail = 1 if request.form.get(f'detail_{fname}') else 0
            order = int(request.form.get(f'order_{fname}', i * 10))
            display_label = request.form.get(f'label_{fname}', '').strip() or None
            conn.execute(
                "INSERT OR REPLACE INTO folder_field_settings (folder_id, field_name, visible_in_detail, display_order, display_label) VALUES (?,?,?,?,?)",
                (folder_id, fname, visible_detail, order, display_label)
            )
        conn.commit()
        conn.close()
        return redirect(url_for('folder_settings', folder_id=folder_id))
    all_custom_fields = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
    field_settings = {}
    for fs in conn.execute("SELECT * FROM folder_field_settings WHERE folder_id=?", (folder_id,)).fetchall():
        field_settings[fs['field_name']] = dict(fs)
    conn.close()
    return render_template('folder_settings.html',
        folder=dict(folder),
        custom_fields=[dict(f) for f in all_custom_fields],
        field_settings=field_settings,
        active_folder_id=folder_id,
    )

@app.route("/note/new", methods=["GET","POST"])
def new_note():
    if request.method == "POST":
        folder_id = request.form.get("folder_id") or None
        title = request.form.get("title","Untitled")
        body = request.form.get("body","")
        status = request.form.get("status","raw")
        source = request.form.get("source","")
        is_task = 1 if request.form.get("is_task") else 0
        due_date = request.form.get("due_date") or None
        created_at = (request.form.get("created_at") or "").replace("T"," ") or datetime.now().strftime("%Y-%m-%d %H:%M")
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = get_db()
        note_id = conn.execute(
            "INSERT INTO notes (title,body,folder_id,status,source,is_task,due_date,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (title, body, folder_id, status, source, is_task, due_date, created_at, updated_at)
        ).lastrowid
        for tid in request.form.getlist("tag_ids"):
            conn.execute("INSERT OR IGNORE INTO note_tags (note_id,tag_id) VALUES (?,?)", (note_id, int(tid)))
        for key, val in request.form.items():
            if key.startswith("custom_"):
                fid = int(key[7:])
                conn.execute("INSERT OR REPLACE INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)", (note_id, fid, val))
        conn.commit()
        conn.close()
        return redirect(url_for('edit_note', note_id=note_id))
    folder_id = request.args.get('folder_id')
    prefill_due_date = request.args.get('due_date', '')
    prefill_is_task = request.args.get('is_task', '0')
    conn = get_db()
    folder = conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone() if folder_id else None
    all_tags = conn.execute("SELECT t.*, tg.name as group_name FROM tags t LEFT JOIN tag_groups tg ON t.tag_group_id=tg.id ORDER BY tg.name,t.name").fetchall()
    custom_fields = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
    field_settings = {}
    detail_view_mode = 'body'
    if folder_id:
        for fs in conn.execute("SELECT * FROM folder_field_settings WHERE folder_id=?", (folder_id,)).fetchall():
            field_settings[fs['field_name']] = dict(fs)
        frow = conn.execute("SELECT detail_view_mode FROM folders WHERE id=?", (folder_id,)).fetchone()
        if frow:
            detail_view_mode = frow['detail_view_mode'] or 'body'
    conn.close()
    return render_template('note_editor.html',
        note=None, folder=dict(folder) if folder else None,
        all_tags=[dict(t) for t in all_tags], note_tags=[],
        custom_fields=[dict(f) for f in custom_fields], note_custom_values={},
        linked_notes=[], backlinks=[], all_notes_for_link=[],
        field_settings=field_settings, detail_view_mode=detail_view_mode,
        prefill_due_date=prefill_due_date, prefill_is_task=prefill_is_task,
    )

@app.route("/note/<int:note_id>", methods=["GET","POST"])
def edit_note(note_id):
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if not note:
        conn.close()
        return redirect(url_for('index'))
    if request.method == "POST":
        folder_id = request.form.get("folder_id") or None
        title = request.form.get("title","Untitled")
        body = request.form.get("body","")
        status = request.form.get("status","raw")
        source = request.form.get("source","")
        is_task = 1 if request.form.get("is_task") else 0
        due_date = request.form.get("due_date") or None
        created_at = (request.form.get("created_at") or "").replace("T"," ") or note['created_at']
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "UPDATE notes SET title=?,body=?,folder_id=?,status=?,source=?,is_task=?,due_date=?,created_at=?,updated_at=? WHERE id=?",
            (title, body, folder_id, status, source, is_task, due_date, created_at, updated_at, note_id)
        )
        conn.execute("DELETE FROM note_tags WHERE note_id=?", (note_id,))
        for tid in request.form.getlist("tag_ids"):
            conn.execute("INSERT OR IGNORE INTO note_tags (note_id,tag_id) VALUES (?,?)", (note_id, int(tid)))
        for key, val in request.form.items():
            if key.startswith("custom_"):
                fid = int(key[7:])
                conn.execute("INSERT OR REPLACE INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)", (note_id, fid, val))
        conn.commit()
        conn.close()
        return redirect(url_for('edit_note', note_id=note_id))
    note_dict = dict(note)
    note_tag_ids = {r['tag_id'] for r in conn.execute("SELECT tag_id FROM note_tags WHERE note_id=?", (note_id,)).fetchall()}
    all_tags = conn.execute("SELECT t.*, tg.name as group_name FROM tags t LEFT JOIN tag_groups tg ON t.tag_group_id=tg.id ORDER BY tg.name,t.name").fetchall()
    folder = conn.execute("SELECT * FROM folders WHERE id=?", (note['folder_id'],)).fetchone() if note['folder_id'] else None
    custom_fields = conn.execute("SELECT * FROM custom_fields ORDER BY name").fetchall()
    custom_vals = {}
    for cv in conn.execute("SELECT * FROM note_custom_values WHERE note_id=?", (note_id,)).fetchall():
        custom_vals[cv['field_id']] = cv['value']
    linked = conn.execute(
        "SELECT n.id,n.title FROM notes n JOIN note_links nl ON nl.target_id=n.id WHERE nl.source_id=? AND n.deleted_at IS NULL", (note_id,)
    ).fetchall()
    backlinks = conn.execute(
        "SELECT n.id,n.title FROM notes n JOIN note_links nl ON nl.source_id=n.id WHERE nl.target_id=? AND n.deleted_at IS NULL", (note_id,)
    ).fetchall()
    all_notes_for_link = conn.execute(
        "SELECT id,title FROM notes WHERE deleted_at IS NULL AND id!=? ORDER BY title", (note_id,)
    ).fetchall()
    field_settings = {}
    detail_view_mode = 'body'
    if note['folder_id']:
        for fs in conn.execute("SELECT * FROM folder_field_settings WHERE folder_id=?", (note['folder_id'],)).fetchall():
            field_settings[fs['field_name']] = dict(fs)
        frow = conn.execute("SELECT detail_view_mode FROM folders WHERE id=?", (note['folder_id'],)).fetchone()
        if frow:
            detail_view_mode = frow['detail_view_mode'] or 'body'
    # Sort custom fields by display_order for this folder
    def cf_order(cf):
        key = f'cf_{cf["id"]}'
        return field_settings.get(key, {}).get('display_order', 100)
    custom_fields_sorted = sorted([dict(f) for f in custom_fields], key=cf_order)
    conn.close()
    return render_template('note_editor.html',
        note=note_dict, folder=dict(folder) if folder else None,
        all_tags=[dict(t) for t in all_tags], note_tags=list(note_tag_ids),
        custom_fields=custom_fields_sorted, note_custom_values=custom_vals,
        linked_notes=[dict(n) for n in linked], backlinks=[dict(n) for n in backlinks],
        all_notes_for_link=[dict(n) for n in all_notes_for_link],
        field_settings=field_settings, detail_view_mode=detail_view_mode,
        prefill_due_date='', prefill_is_task='0',
    )

@app.route("/note/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id):
    conn = get_db()
    note = conn.execute("SELECT folder_id FROM notes WHERE id=?", (note_id,)).fetchone()
    folder_id = note['folder_id'] if note else None
    conn.execute("UPDATE notes SET deleted_at=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M"), note_id))
    conn.commit()
    conn.close()
    return redirect(url_for('folder_view', folder_id=folder_id) if folder_id else url_for('index'))

@app.route("/note/<int:note_id>/archive", methods=["POST"])
def archive_note(note_id):
    conn = get_db()
    note = conn.execute("SELECT folder_id, is_archived FROM notes WHERE id=?", (note_id,)).fetchone()
    new_val = 0 if note and note['is_archived'] else 1
    conn.execute("UPDATE notes SET is_archived=? WHERE id=?", (new_val, note_id))
    conn.commit()
    folder_id = note['folder_id'] if note else None
    conn.close()
    return redirect(request.referrer or (url_for('folder_view', folder_id=folder_id) if folder_id else url_for('index')))

@app.route("/note/<int:note_id>/restore", methods=["POST"])
def restore_note(note_id):
    conn = get_db()
    conn.execute("UPDATE notes SET deleted_at=NULL WHERE id=?", (note_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('trash_view'))

@app.route("/note/<int:note_id>/delete-permanent", methods=["POST"])
def delete_permanent(note_id):
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('trash_view'))

@app.route("/note/<int:note_id>/autosave", methods=["POST"])
def autosave_note(note_id):
    data = request.get_json()
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    created_at = (data.get("created_at") or "").replace("T"," ") or updated_at
    conn = get_db()
    conn.execute(
        "UPDATE notes SET title=?,body=?,status=?,source=?,created_at=?,updated_at=? WHERE id=?",
        (data.get("title","Untitled"), data.get("body",""), data.get("status","raw"),
         data.get("source",""), created_at, updated_at, note_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/notes/<int:note_id>/set-due-date", methods=["POST"])
def set_note_due_date(note_id):
    due_date = request.json.get("due_date") if request.is_json else request.form.get("due_date")
    conn = get_db()
    conn.execute("UPDATE notes SET due_date=?, is_task=1, updated_at=? WHERE id=?",
                 (due_date, datetime.now().strftime("%Y-%m-%d %H:%M"), note_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/notes/<int:note_id>/set-folder", methods=["POST"])
def set_note_folder(note_id):
    folder_id = request.form.get("folder_id") or None
    conn = get_db()
    conn.execute("UPDATE notes SET folder_id=? WHERE id=?", (folder_id, note_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/folders", methods=["POST"])
def create_folder():
    name = request.form.get("name","New Folder")
    parent_id = request.form.get("parent_id") or None
    filters_json = request.form.get("default_filters_json", "[]")
    sorts_json = request.form.get("default_sorts_json", "[]")
    filter_logic = request.form.get("default_filter_logic", "AND")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO folders (name,parent_id,created_at,default_filters_json,default_sorts_json,default_filter_logic) VALUES (?,?,?,?,?,?)",
        (name, parent_id, datetime.now().strftime("%Y-%m-%d %H:%M"), filters_json, sorts_json, filter_logic)
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    redirect_to = request.form.get("redirect_to")
    if redirect_to == "new_folder":
        return redirect(url_for('folder_view', folder_id=new_id))
    return redirect(request.referrer or url_for('index'))

@app.route("/api/folders/<int:folder_id>/save-defaults", methods=["POST"])
def save_folder_defaults(folder_id):
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No data"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE folders SET default_filters_json=?,default_sorts_json=?,default_filter_logic=? WHERE id=?",
        (data.get("filters_json","[]"), data.get("sorts_json","[]"), data.get("filter_logic","AND"), folder_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/folders/<int:folder_id>/set-detail-mode", methods=["POST"])
def set_folder_detail_mode(folder_id):
    data = request.get_json()
    mode = data.get('mode', 'body') if data else 'body'
    if mode not in ('body', 'data'):
        mode = 'body'
    conn = get_db()
    conn.execute("UPDATE folders SET detail_view_mode=? WHERE id=?", (mode, folder_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/folders/<int:folder_id>/rename", methods=["POST"])
def rename_folder(folder_id):
    name = request.form.get("name","Folder")
    conn = get_db()
    conn.execute("UPDATE folders SET name=? WHERE id=?", (name, folder_id))
    conn.commit()
    conn.close()
    return redirect(url_for('folder_view', folder_id=folder_id))

@app.route("/api/folders/<int:folder_id>/save-default-view", methods=["POST"])
def save_folder_default_view(folder_id):
    conn = get_db()
    conn.execute(
        "UPDATE folders SET default_view_type=?,default_sort_field=?,default_sort_dir=?,default_filters_json=?,default_filter_logic=? WHERE id=?",
        (request.form.get("view_type","card"), request.form.get("sort_field","created_at"),
         request.form.get("sort_dir","desc"), request.form.get("filters_json","[]"),
         request.form.get("filter_logic","AND"), folder_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('folder_view', folder_id=folder_id))

@app.route("/api/folders/<int:folder_id>/delete", methods=["POST"])
def delete_folder(folder_id):
    conn = get_db()
    conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route("/api/tag-groups", methods=["POST"])
def create_tag_group():
    name = request.form.get("name","New Group")
    conn = get_db()
    conn.execute("INSERT INTO tag_groups (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tag-groups/<int:group_id>/rename", methods=["POST"])
def rename_tag_group(group_id):
    name = request.form.get("name","Group")
    conn = get_db()
    conn.execute("UPDATE tag_groups SET name=? WHERE id=?", (name, group_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tag-groups/<int:group_id>/delete", methods=["POST"])
def delete_tag_group(group_id):
    conn = get_db()
    conn.execute("DELETE FROM tag_groups WHERE id=?", (group_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tags", methods=["POST"])
def create_tag():
    name = request.form.get("name","New Tag")
    group_id = request.form.get("tag_group_id") or None
    conn = get_db()
    conn.execute("INSERT INTO tags (name,tag_group_id) VALUES (?,?)", (name, group_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tags/<int:tag_id>/rename", methods=["POST"])
def rename_tag(tag_id):
    name = request.form.get("name","Tag")
    conn = get_db()
    conn.execute("UPDATE tags SET name=? WHERE id=?", (name, tag_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tags/<int:tag_id>/delete", methods=["POST"])
def delete_tag(tag_id):
    conn = get_db()
    conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/note-links", methods=["POST"])
def add_note_link():
    source_id = int(request.form.get("source_id"))
    target_id = int(request.form.get("target_id"))
    if source_id != target_id:
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO note_links (source_id,target_id) VALUES (?,?)", (source_id, target_id))
        conn.commit()
        conn.close()
    return redirect(url_for('edit_note', note_id=source_id))

@app.route("/api/note-links/<int:source_id>/<int:target_id>/delete", methods=["POST"])
def delete_note_link(source_id, target_id):
    conn = get_db()
    conn.execute("DELETE FROM note_links WHERE source_id=? AND target_id=?", (source_id, target_id))
    conn.commit()
    conn.close()
    return redirect(url_for('edit_note', note_id=source_id))

@app.route("/api/custom-fields", methods=["POST"])
def add_custom_field():
    name = request.form.get("name","New Field")
    field_type = request.form.get("field_type","text")
    if field_type not in FIELD_TYPES:
        field_type = 'text'
    folder_id = request.form.get("folder_id") or None
    conn = get_db()
    conn.execute("INSERT INTO custom_fields (folder_id,name,field_type) VALUES (?,?,?)", (folder_id, name, field_type))
    conn.commit()
    conn.close()
    redirect_folder = request.form.get("redirect_folder_id") or folder_id
    return redirect(url_for('folder_view', folder_id=redirect_folder) if redirect_folder else url_for('index'))

@app.route("/api/notes/search")
def search_notes_api():
    q = request.args.get('q', '').strip()
    conn = get_db()
    notes = conn.execute(
        "SELECT id, title FROM notes WHERE deleted_at IS NULL AND title LIKE ? ORDER BY updated_at DESC LIMIT 12",
        (f'%{q}%',)
    ).fetchall()
    conn.close()
    return jsonify([dict(n) for n in notes])

@app.route("/api/notes/bulk-edit", methods=["POST"])
def bulk_edit_notes():
    data = request.get_json()
    note_ids = data.get("note_ids", [])
    changes = data.get("changes", {})
    if not note_ids:
        return jsonify({"ok": False, "error": "No notes selected"})
    conn = get_db()
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    for note_id in note_ids:
        sets = ["updated_at=?"]
        params = [updated_at]
        if "status" in changes:
            sets.append("status=?"); params.append(changes["status"])
        if "folder_id" in changes:
            sets.append("folder_id=?"); params.append(changes["folder_id"] or None)
        if "is_archived" in changes:
            sets.append("is_archived=?"); params.append(1 if changes["is_archived"] else 0)
        if changes.get("action") == "trash":
            sets.append("deleted_at=?"); params.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
        if "due_date" in changes:
            # absolute date
            sets.append("due_date=?"); params.append(changes["due_date"] or None)
        if "due_date_shift" in changes:
            # shift by N days
            shift = int(changes["due_date_shift"])
            note = conn.execute("SELECT due_date FROM notes WHERE id=?", (note_id,)).fetchone()
            if note and note["due_date"]:
                try:
                    old = datetime.strptime(note["due_date"][:10], "%Y-%m-%d").date()
                    new_date = (old + timedelta(days=shift)).isoformat()
                    sets.append("due_date=?"); params.append(new_date)
                except Exception:
                    pass
        params.append(note_id)
        if len(sets) > 1:
            conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id=?", params)
        if "custom_values" in changes:
            for field_id, value in changes["custom_values"].items():
                conn.execute(
                    "INSERT OR REPLACE INTO note_custom_values (note_id,field_id,value) VALUES (?,?,?)",
                    (note_id, int(field_id), value)
                )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": len(note_ids)})

@app.route("/api/custom-fields/<int:field_id>/rename", methods=["POST"])
def rename_custom_field(field_id):
    name = request.form.get("name","Field")
    conn = get_db()
    field = conn.execute("SELECT folder_id FROM custom_fields WHERE id=?", (field_id,)).fetchone()
    folder_id = field['folder_id'] if field else None
    conn.execute("UPDATE custom_fields SET name=? WHERE id=?", (name, field_id))
    conn.commit()
    conn.close()
    return redirect(url_for('folder_view', folder_id=folder_id) if folder_id else url_for('index'))

@app.route("/api/custom-fields/<int:field_id>/delete", methods=["POST"])
def delete_custom_field(field_id):
    conn = get_db()
    field = conn.execute("SELECT folder_id FROM custom_fields WHERE id=?", (field_id,)).fetchone()
    folder_id = field['folder_id'] if field else None
    conn.execute("DELETE FROM custom_fields WHERE id=?", (field_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('folder_view', folder_id=folder_id) if folder_id else url_for('index'))

@app.route("/api/saved-views", methods=["POST"])
def create_saved_view():
    conn = get_db()
    conn.execute(
        "INSERT INTO saved_views (name,context_type,context_id,filters_json,filter_logic,sort_field,sort_dir,view_type,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (request.form.get("name","New View"), request.form.get("context_type","folder"),
         request.form.get("context_id"), request.form.get("filters_json","[]"),
         request.form.get("filter_logic","AND"), request.form.get("sort_field","created_at"),
         request.form.get("sort_dir","desc"), request.form.get("view_type","card"),
         datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/saved-views/<int:view_id>/update", methods=["POST"])
def update_saved_view(view_id):
    conn = get_db()
    conn.execute(
        "UPDATE saved_views SET filters_json=?,filter_logic=?,sort_field=?,sort_dir=?,view_type=? WHERE id=?",
        (request.form.get("filters_json","[]"), request.form.get("filter_logic","AND"),
         request.form.get("sort_field","created_at"), request.form.get("sort_dir","desc"),
         request.form.get("view_type","card"), view_id)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('saved_view', view_id=view_id))

@app.route("/api/saved-views/<int:view_id>/rename", methods=["POST"])
def rename_saved_view(view_id):
    name = request.form.get("name","View")
    conn = get_db()
    conn.execute("UPDATE saved_views SET name=? WHERE id=?", (name, view_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route("/api/saved-views/<int:view_id>/delete", methods=["POST"])
def delete_saved_view(view_id):
    conn = get_db()
    conn.execute("DELETE FROM saved_views WHERE id=?", (view_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
