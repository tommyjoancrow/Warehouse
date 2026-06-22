from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import json
from datetime import datetime, date, timedelta
import calendar as cal_module

app = Flask(__name__)
DB_PATH = "notes.db"

# ── Column types ────────────────────────────────────────────────
COLUMN_TYPES = [
    ('text', 'Text'),
    ('longtext', 'Rich text'),
    ('number', 'Number'),
    ('date', 'Date'),
    ('checkbox', 'Checkbox'),
    ('select', 'Single select'),
    ('multiselect', 'Multi-select'),
    ('url', 'URL'),
    ('email', 'Email'),
    ('phone', 'Phone'),
    ('currency', 'Currency'),
    ('percent', 'Percent'),
    ('tag', 'Tag list'),
    ('link', 'Link to record'),
]
COLUMN_TYPE_KEYS = [t[0] for t in COLUMN_TYPES]

# Filter operators offered per type group (value, label)
TEXT_OPS   = [('contains','contains'),('equals','is'),('not_contains','is not'),('starts_with','starts with'),('is_empty','is empty'),('is_not_empty','is not empty')]
NUM_OPS    = [('eq','='),('ne','≠'),('gt','>'),('lt','<'),('gte','≥'),('lte','≤'),('is_empty','is empty'),('is_not_empty','is not empty')]
DATE_OPS   = [('equals','is'),('before','before'),('after','after'),('is_empty','is empty'),('is_not_empty','is not empty')]
CHECK_OPS  = [('is_true','is checked'),('is_false','is unchecked')]
SELECT_OPS = [('equals','is'),('not_equals','is not'),('is_empty','is empty'),('is_not_empty','is not empty')]
MULTI_OPS  = [('has_any','has any of'),('has_all','has all of'),('has_none','has none of'),('is_empty','is empty')]
LINK_OPS   = [('links_to','links to'),('is_empty','is empty'),('is_not_empty','is not empty')]

def ops_for_type(t):
    if t in ('text','longtext','url','email','phone'): return TEXT_OPS
    if t in ('number','currency','percent'): return NUM_OPS
    if t == 'date': return DATE_OPS
    if t == 'checkbox': return CHECK_OPS
    if t == 'select': return SELECT_OPS
    if t in ('multiselect', 'tag'): return MULTI_OPS
    if t == 'link': return LINK_OPS
    return TEXT_OPS

OPS_BY_TYPE = {t: ops_for_type(t) for t in COLUMN_TYPE_KEYS}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@app.template_filter('from_json')
def from_json_filter(s):
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []

# ── Schema ──────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '📋',
    position INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'text',
    position INTEGER DEFAULT 0,
    options TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS cell_values (
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    column_id INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    value TEXT DEFAULT '',
    PRIMARY KEY (record_id, column_id)
);
CREATE TABLE IF NOT EXISTS views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    view_type TEXT DEFAULT 'grid',
    filters_json TEXT DEFAULT '[]',
    filter_logic TEXT DEFAULT 'AND',
    sorts_json TEXT DEFAULT '[]',
    hidden_columns_json TEXT DEFAULT '[]',
    column_order_json TEXT DEFAULT '[]',
    detail_fields_json TEXT DEFAULT '[]',
    date_column_id INTEGER DEFAULT NULL,
    position INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
"""

def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    # migrations for existing DBs
    view_cols = [r[1] for r in conn.execute("PRAGMA table_info(views)").fetchall()]
    if 'column_order_json' not in view_cols:
        conn.execute("ALTER TABLE views ADD COLUMN column_order_json TEXT DEFAULT '[]'")
    if 'detail_fields_json' not in view_cols:
        conn.execute("ALTER TABLE views ADD COLUMN detail_fields_json TEXT DEFAULT '[]'")
    conn.commit()
    # purge trash > 30 days
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    conn.execute("DELETE FROM records WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cutoff,))
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0] == 0:
        seed(conn)
    conn.close()

def seed(conn):
    """One workspace table holding every record. 'Companies', 'People', etc. are
    VIEWS that filter on the Type column and hide the columns that don't apply."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = date.today()
    tid = conn.execute("INSERT INTO tables (name,icon,position,created_at) VALUES (?,?,?,?)",
                       ('Workspace', '🗂', 0, now)).lastrowid

    def add_col(name, typ, pos, options=None):
        return conn.execute("INSERT INTO columns (table_id,name,type,position,options,created_at) VALUES (?,?,?,?,?,?)",
                            (tid, name, typ, pos, json.dumps(options or []), now)).lastrowid
    def add_record(cells):
        rid = conn.execute("INSERT INTO records (table_id,created_at,updated_at) VALUES (?,?,?)",
                           (tid, now, now)).lastrowid
        for cid, val in cells.items():
            conn.execute("INSERT INTO cell_values (record_id,column_id,value) VALUES (?,?,?)", (rid, cid, val))
        return rid
    def add_view(name, vtype, filters, sorts, hidden, pos, date_col=None):
        conn.execute("""INSERT INTO views (table_id,name,view_type,filters_json,filter_logic,sorts_json,hidden_columns_json,date_column_id,position,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (tid, name, vtype, json.dumps(filters), 'AND', json.dumps(sorts), json.dumps(hidden), date_col, pos, now))

    # ── One shared set of columns. Name is primary (position 0). ──
    c_name   = add_col('Name', 'text', 0)
    c_type   = add_col('Type', 'select', 1, ['Company','Person','Task','Note'])
    c_status = add_col('Status', 'select', 2, ['Lead','Active','Inactive','To do','In progress','Done'])
    c_email  = add_col('Email', 'email', 3)
    c_phone  = add_col('Phone', 'phone', 4)
    c_web    = add_col('Website', 'url', 5)
    c_link   = add_col('Linked to', 'link', 6, {'target_table_id': tid})
    c_due    = add_col('Due Date', 'date', 7)
    c_pri    = add_col('Priority', 'select', 8, ['Low','Medium','High'])
    c_notes  = add_col('Notes', 'longtext', 9)

    # ── Records (all in the one table, distinguished by Type) ──
    acme   = add_record({c_name:'Acme Corp', c_type:'Company', c_web:'https://acme.example', c_status:'Active'})
    globex = add_record({c_name:'Globex', c_type:'Company', c_web:'https://globex.example', c_status:'Active'})
    initech= add_record({c_name:'Initech', c_type:'Company', c_web:'https://initech.example', c_status:'Inactive'})

    alice = add_record({c_name:'Alice Chen', c_type:'Person', c_email:'alice@acme.example', c_phone:'555-0100',
                        c_link:json.dumps([acme]), c_status:'Active', c_notes:'<p>Met at the <strong>2026 conference</strong>.</p>'})
    add_record({c_name:'Bob Martinez', c_type:'Person', c_email:'bob@globex.example', c_phone:'555-0142',
                c_link:json.dumps([globex]), c_status:'Lead', c_notes:'<p>Intro via Alice.</p>'})
    add_record({c_name:'Carol Singh', c_type:'Person', c_email:'carol@initech.example', c_phone:'555-0199',
                c_link:json.dumps([initech]), c_status:'Inactive'})

    add_record({c_name:'Follow up with Alice', c_type:'Task', c_status:'To do',
                c_due:(today+timedelta(days=2)).isoformat(), c_pri:'High', c_link:json.dumps([alice])})
    add_record({c_name:'Send proposal to Globex', c_type:'Task', c_status:'To do',
                c_due:(today+timedelta(days=5)).isoformat(), c_pri:'Medium'})
    add_record({c_name:'Archive old contacts', c_type:'Task', c_status:'Done',
                c_due:(today-timedelta(days=3)).isoformat(), c_pri:'Low'})

    add_record({c_name:'Welcome', c_type:'Note', c_due:today.isoformat(),
                c_notes:'<p>Everything lives in <strong>one table</strong>. The items in the sidebar are <em>views</em> — saved filters into this table. Try editing a view\'s filters, or make your own.</p>'})

    # ── Views (the sidebar). Each hides columns that don't apply. ──
    ALL = [c_name,c_type,c_status,c_email,c_phone,c_web,c_link,c_due,c_pri,c_notes]
    def hide_all_but(keep):
        return [c for c in ALL if c not in keep]

    add_view('All records', 'grid', [], [{'c':c_name,'d':'asc'}], [], 0)
    add_view('Companies', 'grid', [{'c':c_type,'op':'equals','v':'Company'}],
             [{'c':c_name,'d':'asc'}], hide_all_but([c_name,c_status,c_web,c_link,c_notes]), 1)
    add_view('People', 'grid', [{'c':c_type,'op':'equals','v':'Person'}],
             [{'c':c_name,'d':'asc'}], hide_all_but([c_name,c_status,c_email,c_phone,c_link,c_notes]), 2)
    add_view('Tasks', 'grid', [{'c':c_type,'op':'equals','v':'Task'}],
             [{'c':c_due,'d':'asc'}], hide_all_but([c_name,c_status,c_due,c_pri,c_link]), 3)
    add_view('Notes', 'grid', [{'c':c_type,'op':'equals','v':'Note'}],
             [{'c':c_due,'d':'desc'}], hide_all_but([c_name,c_notes,c_due]), 4)

    conn.commit()

init_db()

# ── Helpers ─────────────────────────────────────────────────────
def get_columns(conn, table_id):
    return [dict(c) for c in conn.execute(
        "SELECT * FROM columns WHERE table_id=? ORDER BY position, id", (table_id,)).fetchall()]

def primary_column(columns):
    return columns[0] if columns else None

def load_records(conn, table_id, include_deleted=False):
    q = "SELECT * FROM records WHERE table_id=?"
    if not include_deleted:
        q += " AND deleted_at IS NULL"
    rows = conn.execute(q, (table_id,)).fetchall()
    ids = [r['id'] for r in rows]
    cells = {}
    if ids:
        ph = ','.join('?' * len(ids))
        for cv in conn.execute(f"SELECT * FROM cell_values WHERE record_id IN ({ph})", ids).fetchall():
            cells.setdefault(cv['record_id'], {})[cv['column_id']] = cv['value']
    recs = []
    for r in rows:
        recs.append({'id': r['id'], 'created_at': r['created_at'], 'updated_at': r['updated_at'],
                     'deleted_at': r['deleted_at'], 'table_id': r['table_id'],
                     'cells': cells.get(r['id'], {})})
    return recs

def primary_values(conn, record_ids):
    """Map record_id -> display string (its primary/first column value)."""
    record_ids = [int(i) for i in record_ids if str(i).strip()]
    if not record_ids:
        return {}
    res = {}
    ph = ','.join('?' * len(record_ids))
    rows = conn.execute(f"SELECT id, table_id FROM records WHERE id IN ({ph})", record_ids).fetchall()
    by_table = {}
    for r in rows:
        by_table.setdefault(r['table_id'], []).append(r['id'])
    for tid, rids in by_table.items():
        pcol = conn.execute("SELECT id FROM columns WHERE table_id=? ORDER BY position, id LIMIT 1", (tid,)).fetchone()
        if not pcol:
            for rid in rids:
                res[rid] = f"Record {rid}"
            continue
        pcid = pcol['id']
        for rid in rids:
            cv = conn.execute("SELECT value FROM cell_values WHERE record_id=? AND column_id=?", (rid, pcid)).fetchone()
            res[rid] = (cv['value'] if cv and cv['value'] else f"Record {rid}")
    return res

def cell_match(col_type, raw, op, fval):
    raw = raw or ''
    if op == 'is_empty':
        return raw == '' or raw == '[]'
    if op == 'is_not_empty':
        return not (raw == '' or raw == '[]')
    if col_type in ('text','longtext','url','email','phone'):
        a = raw.lower(); b = (fval or '').lower()
        if op == 'contains': return b in a
        if op == 'not_contains': return b not in a
        if op == 'equals': return a == b
        if op == 'not_equals': return a != b
        if op == 'starts_with': return a.startswith(b)
    elif col_type in ('number','currency','percent'):
        try:
            x = float(raw); y = float(fval)
        except (ValueError, TypeError):
            return False
        return {'eq': x==y, 'ne': x!=y, 'gt': x>y, 'lt': x<y, 'gte': x>=y, 'lte': x<=y}.get(op, False)
    elif col_type == 'date':
        if not raw: return False
        if op == 'equals': return raw[:10] == fval
        if op == 'before': return raw[:10] < (fval or '')
        if op == 'after': return raw[:10] > (fval or '')
    elif col_type == 'checkbox':
        truthy = raw in ('1','true','True')
        if op == 'is_true': return truthy
        if op == 'is_false': return not truthy
    elif col_type == 'select':
        if op == 'equals': return raw == fval
        if op == 'not_equals': return raw != fval
    elif col_type in ('multiselect', 'tag'):
        try:
            items = [str(i).lower() for i in (json.loads(raw) if raw else [])]
        except Exception:
            items = []
        targets = [t.strip().lower() for t in (fval or '').split(',') if t.strip()]
        if op == 'has_any': return any(t in items for t in targets)
        if op == 'has_all': return all(t in items for t in targets)
        if op == 'has_none': return not any(t in items for t in targets)
    elif col_type == 'link':
        try:
            ids = [str(i) for i in (json.loads(raw) if raw else [])]
        except Exception:
            ids = []
        if op == 'links_to': return str(fval) in ids
    return True

def cell_sort_key(col_type, raw):
    raw = raw or ''
    if col_type in ('number','currency','percent'):
        try:
            return (0, float(raw))
        except (ValueError, TypeError):
            return (1, 0.0)
    if col_type == 'checkbox':
        return (0, 1 if raw in ('1','true','True') else 0)
    if col_type == 'date':
        return (1 if not raw else 0, raw)
    return (1 if not raw else 0, raw.lower())

def apply_view(recs, columns, filters, filter_logic, sorts, search):
    col_by_id = {c['id']: c for c in columns}
    # search across all text-ish cells
    if search:
        s = search.lower()
        def matches_search(rec):
            for cid, val in rec['cells'].items():
                if val and s in str(val).lower():
                    return True
            return False
        recs = [r for r in recs if matches_search(r)]
    # filters
    if filters:
        def passes(rec):
            results = []
            for f in filters:
                col = col_by_id.get(int(f.get('c'))) if f.get('c') else None
                if not col:
                    continue
                raw = rec['cells'].get(col['id'], '')
                results.append(cell_match(col['type'], raw, f.get('op','contains'), f.get('v','')))
            if not results:
                return True
            return all(results) if filter_logic == 'AND' else any(results)
        recs = [r for r in recs if passes(r)]
    # sorts (apply last-to-first for stable multi-sort)
    for s in reversed(sorts or []):
        col = col_by_id.get(int(s.get('c'))) if s.get('c') else None
        if not col:
            continue
        recs.sort(key=lambda r: cell_sort_key(col['type'], r['cells'].get(col['id'], '')),
                  reverse=(s.get('d') == 'desc'))
    return recs

def parse_params(view=None):
    def getj(key, fallback):
        v = request.args.get(key)
        if v is None:
            return fallback
        try:
            return json.loads(v)
        except Exception:
            return fallback
    vt = request.args.get('vt') or (view['view_type'] if view else 'grid')
    filters = getj('filters', json.loads(view['filters_json']) if view else [])
    logic = request.args.get('logic') or (view['filter_logic'] if view else 'AND')
    sorts = getj('sorts', json.loads(view['sorts_json']) if view else [])
    hidden = getj('hidden', json.loads(view['hidden_columns_json']) if view else [])
    search = request.args.get('search', '')
    return vt, filters, logic, sorts, hidden, search

def format_cell(col, raw, link_names):
    """Display string for a cell in grid/card."""
    raw = raw or ''
    t = col['type']
    if t == 'checkbox':
        return '✓' if raw in ('1','true','True') else ''
    if t == 'longtext':
        # strip tags crudely for preview
        import re
        return re.sub('<[^<]+?>', '', raw)[:120]
    if t in ('multiselect', 'tag'):
        try:
            return json.loads(raw) if raw else []
        except Exception:
            return []
    if t == 'link':
        try:
            ids = json.loads(raw) if raw else []
        except Exception:
            ids = []
        return [link_names.get(int(i), f"Record {i}") for i in ids]
    if t == 'currency':
        return f"${raw}" if raw else ''
    if t == 'percent':
        return f"{raw}%" if raw else ''
    return raw

def build_grid(conn, recs, columns):
    """Attach display values; resolve link names."""
    # gather all linked record ids
    link_cols = [c for c in columns if c['type'] == 'link']
    linked_ids = set()
    for rec in recs:
        for c in link_cols:
            raw = rec['cells'].get(c['id'], '')
            if raw:
                try:
                    linked_ids.update(int(i) for i in json.loads(raw))
                except Exception:
                    pass
    link_names = primary_values(conn, linked_ids) if linked_ids else {}
    for rec in recs:
        disp = {}
        for c in columns:
            disp[c['id']] = format_cell(c, rec['cells'].get(c['id'], ''), link_names)
        rec['display'] = disp
    return recs, link_names

# ── Context (sidebar) ───────────────────────────────────────────
def workspace_table(conn):
    return conn.execute("SELECT * FROM tables ORDER BY id LIMIT 1").fetchone()

@app.context_processor
def inject_sidebar():
    conn = get_db()
    ws = workspace_table(conn)
    views = []
    total = 0
    if ws:
        views = [dict(v) for v in conn.execute(
            "SELECT * FROM views WHERE table_id=? ORDER BY position, id", (ws['id'],)).fetchall()]
        total = conn.execute("SELECT COUNT(*) FROM records WHERE table_id=? AND deleted_at IS NULL", (ws['id'],)).fetchone()[0]
    conn.close()
    return dict(workspace=(dict(ws) if ws else None), sidebar_views=views,
                workspace_total=total, all_tables=([dict(ws)] if ws else []),
                column_types=COLUMN_TYPES, ops_by_type=OPS_BY_TYPE)

# ── Routes: browsing ────────────────────────────────────────────
@app.route("/")
def index():
    conn = get_db()
    ws = workspace_table(conn)
    first_view = None
    if ws:
        first_view = conn.execute("SELECT id FROM views WHERE table_id=? ORDER BY position, id LIMIT 1", (ws['id'],)).fetchone()
    conn.close()
    if first_view:
        return redirect(url_for('view_page', view_id=first_view['id']))
    if ws:
        return redirect(url_for('table_view', table_id=ws['id']))
    return render_template('table_view.html', table=None, columns=[], records=[],
                           view=None, views=[], view_type='grid', filters=[], filter_logic='AND',
                           sorts=[], hidden=[], search='', link_names={})

def _render_table(conn, table, view):
    columns = get_columns(conn, table['id'])
    vt, filters, logic, sorts, hidden, search = parse_params(view)
    recs = load_records(conn, table['id'])
    recs = apply_view(recs, columns, filters, logic, sorts, search)
    recs, link_names = build_grid(conn, recs, columns)
    views = [dict(v) for v in conn.execute(
        "SELECT * FROM views WHERE table_id=? ORDER BY position, id", (table['id'],)).fetchall()]
    hidden_set = set(int(h) for h in hidden)
    # column order: per-view order if set, else global position
    ordered = columns
    if view and view['column_order_json']:
        try:
            order = json.loads(view['column_order_json'])
        except Exception:
            order = []
        if order:
            id2col = {c['id']: c for c in columns}
            seen = set()
            ordered = []
            for cid in order:
                if cid in id2col:
                    ordered.append(id2col[cid]); seen.add(cid)
            ordered += [c for c in columns if c['id'] not in seen]
    visible_columns = [c for c in ordered if c['id'] not in hidden_set]
    primary = primary_column(columns)
    # which columns appear in the detail view when opening a record from here
    detail_field_ids = []
    if view and view['detail_fields_json']:
        try:
            detail_field_ids = json.loads(view['detail_fields_json'])
        except Exception:
            detail_field_ids = []
    date_columns = [c for c in columns if c['type'] == 'date']
    # calendar date column + month grid
    date_col_id = None
    cal_weeks = None
    cal_month_label = None
    cal_prev = cal_next = None
    if vt == 'calendar':
        req_dc = request.args.get('date_col', type=int)
        if req_dc:
            date_col_id = req_dc
        elif view and view['date_column_id']:
            date_col_id = view['date_column_id']
        else:
            date_col_id = date_columns[0]['id'] if date_columns else None
        if date_col_id:
            cal_weeks, cal_month_label, cal_prev, cal_next = build_calendar(recs, date_col_id, primary)
    return render_template('table_view.html',
        table=table, columns=columns, visible_columns=visible_columns,
        records=recs, link_names=link_names, primary=primary,
        view=view, views=views, view_type=vt,
        filters=filters, filter_logic=logic, sorts=sorts, hidden=list(hidden_set),
        search=search, date_col_id=date_col_id, date_columns=date_columns,
        detail_field_ids=detail_field_ids,
        cal_weeks=cal_weeks, cal_month_label=cal_month_label, cal_prev=cal_prev, cal_next=cal_next,
        page_title=(view['name'] if view else table['name']),
        active_table_id=table['id'], active_view_id=(view['id'] if view else None))

def build_calendar(recs, date_col_id, primary):
    """Return (weeks, month_label, prev_ym, next_ym) for the requested month."""
    ym = request.args.get('m')  # 'YYYY-MM'
    today = date.today()
    if ym:
        try:
            year, month = int(ym[:4]), int(ym[5:7])
        except Exception:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month
    # bucket records by date string
    by_date = {}
    for r in recs:
        dv = (r['cells'].get(date_col_id, '') or '')[:10]
        if dv:
            label = (r['cells'].get(primary['id'], '') if primary else '') or f"Record {r['id']}"
            by_date.setdefault(dv, []).append({'id': r['id'], 'label': label})
    cal = cal_module.Calendar(firstweekday=6)  # Sunday first
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        wk = []
        for d in week:
            ds = d.isoformat()
            wk.append({
                'day': d.day,
                'date': ds,
                'in_month': d.month == month,
                'is_today': d == today,
                'records': by_date.get(ds, []),
            })
        weeks.append(wk)
    month_label = date(year, month, 1).strftime('%B %Y')
    prev_m = (date(year, month, 1) - timedelta(days=1))
    next_m = (date(year, month, 28) + timedelta(days=10))
    return weeks, month_label, f"{prev_m.year}-{prev_m.month:02d}", f"{next_m.year}-{next_m.month:02d}"

@app.route("/table/<int:table_id>")
def table_view(table_id):
    conn = get_db()
    table = conn.execute("SELECT * FROM tables WHERE id=?", (table_id,)).fetchone()
    if not table:
        conn.close()
        return redirect(url_for('index'))
    out = _render_table(conn, dict(table), None)
    conn.close()
    return out

@app.route("/view/<int:view_id>")
def view_page(view_id):
    conn = get_db()
    view = conn.execute("SELECT * FROM views WHERE id=?", (view_id,)).fetchone()
    if not view:
        conn.close()
        return redirect(url_for('index'))
    table = conn.execute("SELECT * FROM tables WHERE id=?", (view['table_id'],)).fetchone()
    out = _render_table(conn, dict(table), dict(view))
    conn.close()
    return out

# ── Routes: record detail ───────────────────────────────────────
@app.route("/record/new")
def new_record_form():
    table_id = request.args.get('table_id', type=int)
    view_id = request.args.get('view_id', type=int)
    conn = get_db()
    table = conn.execute("SELECT * FROM tables WHERE id=?", (table_id,)).fetchone()
    if not table:
        conn.close()
        return redirect(url_for('index'))
    columns = get_columns(conn, table_id)
    # Pre-fill from the originating view's equality filters so the new record
    # actually lands in that view (e.g. adding from "Companies" sets Type=Company).
    prefill = {}
    if view_id:
        v = conn.execute("SELECT * FROM views WHERE id=?", (view_id,)).fetchone()
        if v:
            try:
                for f in json.loads(v['filters_json']):
                    if f.get('op') in ('equals', 'is') and f.get('v') != '':
                        prefill[int(f['c'])] = f['v']
            except Exception:
                pass
    detail_cols = detail_columns_for(conn, columns, view_id)
    conn.close()
    return render_template('record_editor.html', table=dict(table), columns=detail_cols,
                           record=None, cells=prefill, link_display={}, view_id=view_id,
                           active_table_id=table_id, page_title='New record')

def detail_columns_for(conn, all_columns, view_id):
    """Columns to show in the detail editor when opened from a given view.
    Empty/absent detail settings => all columns. Primary (first) always shown."""
    if not all_columns:
        return all_columns
    if not view_id:
        return all_columns
    v = conn.execute("SELECT detail_fields_json FROM views WHERE id=?", (view_id,)).fetchone()
    if not v or not v['detail_fields_json']:
        return all_columns
    try:
        ids = json.loads(v['detail_fields_json'])
    except Exception:
        ids = []
    if not ids:
        return all_columns
    id2 = {c['id']: c for c in all_columns}
    primary = all_columns[0]
    ordered = [primary]
    for cid in ids:
        if cid in id2 and cid != primary['id']:
            ordered.append(id2[cid])
    return ordered

@app.route("/record/<int:record_id>")
def record_detail(record_id):
    view_id = request.args.get('view', type=int)
    conn = get_db()
    rec = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
    if not rec:
        conn.close()
        return redirect(url_for('index'))
    table = conn.execute("SELECT * FROM tables WHERE id=?", (rec['table_id'],)).fetchone()
    all_columns = get_columns(conn, rec['table_id'])
    columns = detail_columns_for(conn, all_columns, view_id)
    cells = {}
    for cv in conn.execute("SELECT * FROM cell_values WHERE record_id=?", (record_id,)).fetchall():
        cells[cv['column_id']] = cv['value']
    # resolve link display names for link columns
    linked_ids = set()
    for c in columns:
        if c['type'] == 'link' and cells.get(c['id']):
            try:
                linked_ids.update(int(i) for i in json.loads(cells[c['id']]))
            except Exception:
                pass
    link_display = primary_values(conn, linked_ids) if linked_ids else {}
    conn.close()
    return render_template('record_editor.html', table=dict(table), columns=columns,
                           record=dict(rec), cells=cells, link_display=link_display, view_id=view_id,
                           active_table_id=rec['table_id'],
                           page_title='Record')

def _save_cells(conn, record_id, columns, form, only_ids=None):
    for c in columns:
        if only_ids is not None and c['id'] not in only_ids:
            continue  # field wasn't shown in this editor; leave its value alone
        key = f"col_{c['id']}"
        if c['type'] == 'checkbox':
            val = '1' if form.get(key) else '0'
        elif c['type'] in ('multiselect', 'tag'):
            vals = [v.strip() for v in form.getlist(key) if v.strip()]
            val = json.dumps(vals)
        elif c['type'] == 'link':
            vals = form.getlist(key)
            val = json.dumps([int(v) for v in vals if v.strip().isdigit()])
        else:
            val = form.get(key, '')
        conn.execute("INSERT OR REPLACE INTO cell_values (record_id, column_id, value) VALUES (?,?,?)",
                     (record_id, c['id'], val))

@app.route("/record/save", methods=["POST"])
def save_record():
    table_id = request.form.get('table_id', type=int)
    record_id = request.form.get('record_id', type=int)
    view_id = request.form.get('view_id', type=int)
    only_ids = None
    cols_field = request.form.get('_cols', '')
    if cols_field:
        only_ids = set(int(x) for x in cols_field.split(',') if x.strip().isdigit())
    conn = get_db()
    columns = get_columns(conn, table_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not record_id:
        record_id = conn.execute("INSERT INTO records (table_id,created_at,updated_at) VALUES (?,?,?)",
                                 (table_id, now, now)).lastrowid
    else:
        conn.execute("UPDATE records SET updated_at=? WHERE id=?", (now, record_id))
    _save_cells(conn, record_id, columns, request.form, only_ids=only_ids)
    conn.commit()
    conn.close()
    if view_id:
        return redirect(url_for('record_detail', record_id=record_id, view=view_id))
    return redirect(url_for('record_detail', record_id=record_id))

@app.route("/record/<int:record_id>/autosave", methods=["POST"])
def autosave_record(record_id):
    data = request.get_json() or {}
    conn = get_db()
    rec = conn.execute("SELECT table_id FROM records WHERE id=?", (record_id,)).fetchone()
    if not rec:
        conn.close()
        return jsonify({"ok": False}), 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for col_id, val in (data.get('cells') or {}).items():
        conn.execute("INSERT OR REPLACE INTO cell_values (record_id, column_id, value) VALUES (?,?,?)",
                     (record_id, int(col_id), val))
    conn.execute("UPDATE records SET updated_at=? WHERE id=?", (now, record_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/records", methods=["POST"])
def create_blank_record():
    """Create an empty record (grid '+ add row'). Returns id."""
    data = request.get_json() or {}
    table_id = data.get('table_id')
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rid = conn.execute("INSERT INTO records (table_id,created_at,updated_at) VALUES (?,?,?)",
                       (table_id, now, now)).lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": rid})

@app.route("/api/cells", methods=["POST"])
def update_cell():
    """Inline edit a single cell."""
    data = request.get_json() or {}
    rid = data.get('record_id'); cid = data.get('column_id'); val = data.get('value', '')
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO cell_values (record_id, column_id, value) VALUES (?,?,?)",
                 (rid, cid, val))
    conn.execute("UPDATE records SET updated_at=? WHERE id=?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M"), rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/record/<int:record_id>/delete", methods=["POST"])
def delete_record(record_id):
    conn = get_db()
    rec = conn.execute("SELECT table_id FROM records WHERE id=?", (record_id,)).fetchone()
    conn.execute("UPDATE records SET deleted_at=? WHERE id=?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M"), record_id))
    conn.commit()
    tid = rec['table_id'] if rec else None
    conn.close()
    return redirect(url_for('table_view', table_id=tid) if tid else url_for('index'))

@app.route("/api/records/bulk", methods=["POST"])
def bulk_records():
    data = request.get_json() or {}
    ids = data.get('record_ids', [])
    action = data.get('action')
    changes = data.get('changes', {})
    if not ids:
        return jsonify({"ok": False, "error": "no records"}), 400
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ph = ','.join('?' * len(ids))
    if action == 'delete':
        conn.execute(f"UPDATE records SET deleted_at=? WHERE id IN ({ph})", [now] + ids)
    elif action == 'set_cell':
        cid = changes.get('column_id'); val = changes.get('value', '')
        for rid in ids:
            conn.execute("INSERT OR REPLACE INTO cell_values (record_id, column_id, value) VALUES (?,?,?)",
                         (rid, cid, val))
        conn.execute(f"UPDATE records SET updated_at=? WHERE id IN ({ph})", [now] + ids)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/records/search")
def search_records_api():
    """For link-picker autocomplete: records in a table matching q (by primary col)."""
    table_id = request.args.get('table_id', type=int)
    q = request.args.get('q', '').strip().lower()
    conn = get_db()
    pcol = conn.execute("SELECT id FROM columns WHERE table_id=? ORDER BY position, id LIMIT 1", (table_id,)).fetchone()
    recs = load_records(conn, table_id)
    out = []
    for r in recs:
        label = (r['cells'].get(pcol['id'], '') if pcol else '') or f"Record {r['id']}"
        if not q or q in label.lower():
            out.append({'id': r['id'], 'label': label})
    conn.close()
    return jsonify(out[:15])

# ── Routes: tables ──────────────────────────────────────────────
@app.route("/api/tables", methods=["POST"])
def create_table():
    name = request.form.get('name', 'New Table').strip() or 'New Table'
    icon = request.form.get('icon', '📋').strip() or '📋'
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    maxpos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM tables").fetchone()[0]
    tid = conn.execute("INSERT INTO tables (name,icon,position,created_at) VALUES (?,?,?,?)",
                       (name, icon, maxpos, now)).lastrowid
    # every table needs at least a primary text column + a default view
    conn.execute("INSERT INTO columns (table_id,name,type,position,options,created_at) VALUES (?,?,?,?,?,?)",
                 (tid, 'Name', 'text', 0, '[]', now))
    conn.execute("""INSERT INTO views (table_id,name,view_type,filters_json,filter_logic,sorts_json,hidden_columns_json,position,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                 (tid, 'All records', 'grid', '[]', 'AND', '[]', '[]', 0, now))
    conn.commit()
    conn.close()
    return redirect(url_for('table_view', table_id=tid))

@app.route("/api/tables/<int:table_id>/rename", methods=["POST"])
def rename_table(table_id):
    conn = get_db()
    conn.execute("UPDATE tables SET name=?, icon=? WHERE id=?",
                 (request.form.get('name', 'Table'),
                  request.form.get('icon', '📋') or '📋', table_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('table_view', table_id=table_id))

@app.route("/api/tables/<int:table_id>/delete", methods=["POST"])
def delete_table(table_id):
    conn = get_db()
    conn.execute("DELETE FROM tables WHERE id=?", (table_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# ── Routes: columns ─────────────────────────────────────────────
@app.route("/api/tables/<int:table_id>/columns", methods=["POST"])
def add_column_route(table_id):
    name = request.form.get('name', 'Field').strip() or 'Field'
    ctype = request.form.get('type', 'text')
    if ctype not in COLUMN_TYPE_KEYS:
        ctype = 'text'
    options = []
    if ctype in ('select', 'multiselect'):
        raw = request.form.get('options', '')
        options = [o.strip() for o in raw.split(',') if o.strip()]
    elif ctype == 'link':
        options = {'target_table_id': table_id}  # one workspace: links point within it
    view_id = request.form.get('view_id', type=int)
    after_id = request.form.get('after_column_id', type=int)
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    maxpos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM columns WHERE table_id=?", (table_id,)).fetchone()[0]
    new_id = conn.execute("INSERT INTO columns (table_id,name,type,position,options,created_at) VALUES (?,?,?,?,?,?)",
                          (table_id, name, ctype, maxpos, json.dumps(options), now)).lastrowid
    if view_id:
        _view_insert_field(conn, view_id, new_id, after_id)
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('table_view', table_id=table_id))

def _view_insert_field(conn, view_id, column_id, after_id):
    """Make column visible in a view and place it right after after_id in the
    view's column order."""
    v = conn.execute("SELECT * FROM views WHERE id=?", (view_id,)).fetchone()
    if not v:
        return
    table_id = v['table_id']
    all_cols = [c['id'] for c in conn.execute(
        "SELECT id FROM columns WHERE table_id=? ORDER BY position, id", (table_id,)).fetchall()]
    try:
        order = json.loads(v['column_order_json']) or []
    except Exception:
        order = []
    # normalise order to a full list of current columns
    order = [c for c in order if c in all_cols]
    order += [c for c in all_cols if c not in order]
    if column_id in order:
        order.remove(column_id)
    if after_id and after_id in order:
        order.insert(order.index(after_id) + 1, column_id)
    else:
        order.append(column_id)
    try:
        hidden = json.loads(v['hidden_columns_json']) or []
    except Exception:
        hidden = []
    hidden = [h for h in hidden if h != column_id]
    conn.execute("UPDATE views SET column_order_json=?, hidden_columns_json=? WHERE id=?",
                 (json.dumps(order), json.dumps(hidden), view_id))

@app.route("/api/columns/<int:column_id>/update", methods=["POST"])
def update_column(column_id):
    conn = get_db()
    col = conn.execute("SELECT * FROM columns WHERE id=?", (column_id,)).fetchone()
    if not col:
        conn.close()
        return jsonify({"ok": False}), 404
    name = request.form.get('name', col['name'])
    ctype = request.form.get('type', col['type'])
    if ctype not in COLUMN_TYPE_KEYS:
        ctype = col['type']
    options = json.loads(col['options'] or '[]')
    if ctype in ('select', 'multiselect'):
        raw = request.form.get('options', None)
        if raw is not None:
            options = [o.strip() for o in raw.split(',') if o.strip()]
    elif ctype == 'link':
        options = {'target_table_id': col['table_id']}
    conn.execute("UPDATE columns SET name=?, type=?, options=? WHERE id=?",
                 (name, ctype, json.dumps(options), column_id))
    conn.commit()
    tid = col['table_id']
    conn.close()
    return redirect(request.referrer or url_for('table_view', table_id=tid))

@app.route("/api/columns/<int:column_id>/delete", methods=["POST"])
def delete_column(column_id):
    conn = get_db()
    col = conn.execute("SELECT table_id FROM columns WHERE id=?", (column_id,)).fetchone()
    conn.execute("DELETE FROM columns WHERE id=?", (column_id,))
    conn.commit()
    tid = col['table_id'] if col else None
    conn.close()
    return redirect(request.referrer or (url_for('table_view', table_id=tid) if tid else url_for('index')))

@app.route("/api/columns/reorder", methods=["POST"])
def reorder_columns():
    """Reorder globally (used by the base 'All records' table)."""
    data = request.get_json() or {}
    order = data.get('order', [])  # list of column ids
    conn = get_db()
    for i, cid in enumerate(order):
        conn.execute("UPDATE columns SET position=? WHERE id=?", (i, cid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/columns/<int:column_id>/tag-options")
def tag_options(column_id):
    """Distinct tag values already used in this column (for autocomplete)."""
    q = request.args.get('q', '').strip().lower()
    conn = get_db()
    seen = {}
    for cv in conn.execute("SELECT value FROM cell_values WHERE column_id=?", (column_id,)).fetchall():
        try:
            for t in json.loads(cv['value']) if cv['value'] else []:
                t = str(t).strip()
                if t and (not q or q in t.lower()):
                    seen[t.lower()] = t
        except Exception:
            pass
    conn.close()
    return jsonify(sorted(seen.values())[:15])

@app.route("/api/views/<int:view_id>/show-field", methods=["POST"])
def view_show_field(view_id):
    data = request.get_json() or {}
    conn = get_db()
    _view_insert_field(conn, view_id, data.get('column_id'), data.get('after_column_id'))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/views/<int:view_id>/hide-field", methods=["POST"])
def view_hide_field(view_id):
    data = request.get_json() or {}
    cid = data.get('column_id')
    conn = get_db()
    v = conn.execute("SELECT hidden_columns_json FROM views WHERE id=?", (view_id,)).fetchone()
    if v:
        try:
            hidden = json.loads(v['hidden_columns_json']) or []
        except Exception:
            hidden = []
        if cid not in hidden:
            hidden.append(cid)
        conn.execute("UPDATE views SET hidden_columns_json=? WHERE id=?", (json.dumps(hidden), view_id))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/views/<int:view_id>/reorder", methods=["POST"])
def view_reorder(view_id):
    data = request.get_json() or {}
    order = data.get('order', [])
    conn = get_db()
    conn.execute("UPDATE views SET column_order_json=? WHERE id=?", (json.dumps(order), view_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/views/<int:view_id>/detail-fields", methods=["POST"])
def view_detail_fields(view_id):
    """Save which fields (and order) show in the detail view for this view."""
    data = request.get_json() or {}
    conn = get_db()
    conn.execute("UPDATE views SET detail_fields_json=? WHERE id=?",
                 (json.dumps(data.get('fields', [])), view_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/views/<int:view_id>/set-date-column", methods=["POST"])
def view_set_date_column(view_id):
    """Anchor a calendar view on a specific date column."""
    data = request.get_json() or {}
    conn = get_db()
    conn.execute("UPDATE views SET date_column_id=? WHERE id=?", (data.get('date_column_id'), view_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Routes: views ───────────────────────────────────────────────
@app.route("/api/views", methods=["POST"])
def create_view():
    data = request.get_json() or {}
    table_id = data.get('table_id')
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    maxpos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM views WHERE table_id=?", (table_id,)).fetchone()[0]
    vid = conn.execute("""INSERT INTO views (table_id,name,view_type,filters_json,filter_logic,sorts_json,hidden_columns_json,date_column_id,position,created_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (table_id, data.get('name', 'New view'), data.get('view_type', 'grid'),
                        json.dumps(data.get('filters', [])), data.get('filter_logic', 'AND'),
                        json.dumps(data.get('sorts', [])), json.dumps(data.get('hidden', [])),
                        data.get('date_column_id'), maxpos, now)).lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": vid})

@app.route("/api/views/<int:view_id>/update", methods=["POST"])
def update_view(view_id):
    data = request.get_json() or {}
    conn = get_db()
    v = conn.execute("SELECT * FROM views WHERE id=?", (view_id,)).fetchone()
    if not v:
        conn.close()
        return jsonify({"ok": False}), 404
    conn.execute("""UPDATE views SET name=?, view_type=?, filters_json=?, filter_logic=?, sorts_json=?, hidden_columns_json=?, date_column_id=? WHERE id=?""",
                 (data.get('name', v['name']), data.get('view_type', v['view_type']),
                  json.dumps(data.get('filters')) if 'filters' in data else v['filters_json'],
                  data.get('filter_logic', v['filter_logic']),
                  json.dumps(data.get('sorts')) if 'sorts' in data else v['sorts_json'],
                  json.dumps(data.get('hidden')) if 'hidden' in data else v['hidden_columns_json'],
                  data.get('date_column_id', v['date_column_id']), view_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/views/<int:view_id>/rename", methods=["POST"])
def rename_view(view_id):
    conn = get_db()
    conn.execute("UPDATE views SET name=? WHERE id=?", (request.form.get('name', 'View'), view_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('view_page', view_id=view_id))

@app.route("/api/views/<int:view_id>/delete", methods=["POST"])
def delete_view(view_id):
    conn = get_db()
    v = conn.execute("SELECT table_id FROM views WHERE id=?", (view_id,)).fetchone()
    conn.execute("DELETE FROM views WHERE id=?", (view_id,))
    conn.commit()
    tid = v['table_id'] if v else None
    conn.close()
    return redirect(url_for('table_view', table_id=tid) if tid else url_for('index'))

# ── Calendar (uses a view's/table's date column) ────────────────
@app.route("/calendar")
def calendar_redirect():
    conn = get_db()
    # find first table with a date column
    for t in conn.execute("SELECT * FROM tables ORDER BY position, id").fetchall():
        dc = conn.execute("SELECT id FROM columns WHERE table_id=? AND type='date' ORDER BY position LIMIT 1", (t['id'],)).fetchone()
        if dc:
            conn.close()
            return redirect(url_for('table_view', table_id=t['id'], vt='calendar'))
    conn.close()
    return redirect(url_for('index'))

# ── Trash ───────────────────────────────────────────────────────
@app.route("/trash")
def trash():
    conn = get_db()
    rows = conn.execute("""SELECT r.*, t.name as table_name, t.icon as table_icon
                           FROM records r JOIN tables t ON r.table_id=t.id
                           WHERE r.deleted_at IS NOT NULL ORDER BY r.deleted_at DESC""").fetchall()
    items = []
    for r in rows:
        pcol = conn.execute("SELECT id FROM columns WHERE table_id=? ORDER BY position, id LIMIT 1", (r['table_id'],)).fetchone()
        label = ''
        if pcol:
            cv = conn.execute("SELECT value FROM cell_values WHERE record_id=? AND column_id=?", (r['id'], pcol['id'])).fetchone()
            label = cv['value'] if cv else ''
        items.append({'id': r['id'], 'label': label or f"Record {r['id']}",
                      'table_name': r['table_name'], 'table_icon': r['table_icon'],
                      'deleted_at': r['deleted_at']})
    conn.close()
    return render_template('trash.html', items=items, active_page='trash')

@app.route("/record/<int:record_id>/restore", methods=["POST"])
def restore_record(record_id):
    conn = get_db()
    conn.execute("UPDATE records SET deleted_at=NULL WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('trash'))

@app.route("/record/<int:record_id>/purge", methods=["POST"])
def purge_record(record_id):
    conn = get_db()
    conn.execute("DELETE FROM records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('trash'))

# ── Search ──────────────────────────────────────────────────────
@app.route("/search")
def search_page():
    q = request.args.get('q', '').strip()
    conn = get_db()
    results = []
    if q:
        s = q.lower()
        for t in conn.execute("SELECT * FROM tables ORDER BY position, id").fetchall():
            columns = get_columns(conn, t['id'])
            recs = load_records(conn, t['id'])
            recs = apply_view(recs, columns, [], 'AND', [], q)
            if recs:
                recs, _ = build_grid(conn, recs, columns)
                pcol = primary_column(columns)
                for r in recs[:25]:
                    label = (r['cells'].get(pcol['id'], '') if pcol else '') or f"Record {r['id']}"
                    results.append({'id': r['id'], 'label': label, 'table_name': t['name'], 'table_icon': t['icon']})
    conn.close()
    return render_template('search_results.html', query=q, results=results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
