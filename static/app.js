// ── Modals ──────────────────────────────────────────────────────────────────
function openModal(id) {
    document.getElementById('modal-overlay').classList.remove('hidden');
    document.getElementById(id).classList.remove('hidden');
    var input = document.querySelector('#' + id + ' input[type="text"]');
    if (input) setTimeout(function() { input.focus(); }, 50);
}

function closeModals() {
    document.getElementById('modal-overlay').classList.add('hidden');
    document.querySelectorAll('.modal').forEach(function(m) { m.classList.add('hidden'); });
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeModals();
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        var s = document.getElementById('global-search');
        if (s) s.focus();
    }
});

// ── Tag modal helper ─────────────────────────────────────────────────────────
function openAddTag(groupId) {
    document.getElementById('add-tag-group-id').value = groupId;
    openModal('modal-add-tag');
    setTimeout(function() { document.getElementById('add-tag-input').focus(); }, 50);
}

// ── Sidebar more-options menus ────────────────────────────────────────────────
function toggleSidebarMenu(e, id) {
    e.stopPropagation();
    var menu = document.getElementById(id);
    if (!menu) return;
    var wasHidden = menu.classList.contains('hidden');
    document.querySelectorAll('.sidebar-menu').forEach(function(m) { m.classList.add('hidden'); });
    if (wasHidden) menu.classList.remove('hidden');
}

document.addEventListener('click', function() {
    document.querySelectorAll('.sidebar-menu').forEach(function(m) { m.classList.add('hidden'); });
});

function openRenameFolder(id, name) {
    document.getElementById('rename-folder-form').action = '/api/folders/' + id + '/rename';
    document.getElementById('rename-folder-input').value = name;
    openModal('modal-rename-folder');
    setTimeout(function() { document.getElementById('rename-folder-input').select(); }, 50);
}

function openRenameTagGroup(id, name) {
    document.getElementById('rename-tag-group-form').action = '/api/tag-groups/' + id + '/rename';
    document.getElementById('rename-tag-group-input').value = name;
    openModal('modal-rename-tag-group');
    setTimeout(function() { document.getElementById('rename-tag-group-input').select(); }, 50);
}

function openRenameTag(id, name) {
    document.getElementById('rename-tag-form').action = '/api/tags/' + id + '/rename';
    document.getElementById('rename-tag-input').value = name;
    openModal('modal-rename-tag');
    setTimeout(function() { document.getElementById('rename-tag-input').select(); }, 50);
}

function openRenameSavedView(id, name) {
    document.getElementById('rename-saved-view-form').action = '/api/saved-views/' + id + '/rename';
    document.getElementById('rename-saved-view-input').value = name;
    openModal('modal-rename-saved-view');
    setTimeout(function() { document.getElementById('rename-saved-view-input').select(); }, 50);
}

// ── Sidebar toggles ──────────────────────────────────────────────────────────
function toggleEl(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('hidden');
    var header = el.previousElementSibling;
    if (header) {
        var arrow = header.querySelector('.tag-group-arrow');
        if (arrow) arrow.style.transform = el.classList.contains('hidden') ? '' : 'rotate(90deg)';
    }
}

// Expand tag groups that contain active tag on load
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tag-group-tags').forEach(function(el) {
        if (el.querySelector('.nav-item.active')) {
            el.classList.remove('hidden');
            var arrow = el.previousElementSibling && el.previousElementSibling.querySelector('.tag-group-arrow');
            if (arrow) arrow.style.transform = 'rotate(90deg)';
        } else {
            el.classList.add('hidden');
        }
    });
});

// ── Filter panel ─────────────────────────────────────────────────────────────
function toggleFilterPanel() {
    var panel = document.getElementById('filter-panel');
    if (panel) panel.classList.toggle('hidden');
}

// ── Inline title editing ──────────────────────────────────────────────────────
function startTitleEdit() {
    var display = document.getElementById('view-title-display');
    var form = document.getElementById('title-edit-form');
    var input = document.getElementById('title-edit-input');
    if (!display || !form || !input) return;
    display.style.display = 'none';
    form.style.display = 'block';
    input.focus();
    input.select();
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); form.submit(); }
        if (e.key === 'Escape') { cancelTitleEdit(); }
    });
    input.addEventListener('blur', function() { form.submit(); });
}

function cancelTitleEdit() {
    document.getElementById('view-title-display').style.display = '';
    document.getElementById('title-edit-form').style.display = 'none';
}

// ── View options dropdown ─────────────────────────────────────────────────────
function toggleViewOptions(e) {
    e.stopPropagation();
    var menu = document.getElementById('view-options-menu');
    if (menu) menu.classList.toggle('hidden');
}

function closeViewOptions() {
    var menu = document.getElementById('view-options-menu');
    if (menu) menu.classList.add('hidden');
}

document.addEventListener('click', function(e) {
    closeViewOptions();
    if (!e.target.closest('.col-menu') && !e.target.closest('.th-arrow')) {
        closeColMenus();
    }
});

// ── Column header menus ───────────────────────────────────────────────────────
function toggleColMenu(e, id) {
    e.stopPropagation();
    var menu = document.getElementById(id);
    if (!menu) return;
    var wasHidden = menu.classList.contains('hidden');
    closeColMenus();
    if (wasHidden) menu.classList.remove('hidden');
}

function closeColMenus(e) {
    document.querySelectorAll('.col-menu').forEach(function(m) { m.classList.add('hidden'); });
}

function applySort(field, dir) {
    var url = new URL(window.location.href);
    url.searchParams.set('sort', field);
    url.searchParams.set('dir', dir);
    url.searchParams.set('view', 'table');
    window.location.href = url.toString();
}

function applyColFilter(field) {
    var op = document.getElementById('op-' + field);
    var val = document.getElementById('fv-' + field);
    if (!op || !val || !val.value.trim()) return;

    var filtersInput = document.getElementById('filters-input');
    var filters = [];
    try { filters = JSON.parse(filtersInput.value || '[]'); } catch(e) {}
    filters.push({ field: field, op: op.value, value: val.value.trim() });
    filtersInput.value = JSON.stringify(filters);

    var panel = document.getElementById('filter-panel');
    if (panel) panel.classList.remove('hidden');

    document.getElementById('filter-form').submit();
}

function openAddCol() {
    closeColMenus();
    openModal('modal-add-col');
    setTimeout(function() {
        var inp = document.getElementById('new-field-name-input');
        if (inp) inp.focus();
    }, 50);
}

function openEditField(fieldId, name, type) {
    closeColMenus();
    document.getElementById('edit-field-form').action = '/api/custom-fields/' + fieldId + '/rename';
    document.getElementById('edit-field-name').value = name;
    openModal('modal-edit-field');
    setTimeout(function() { document.getElementById('edit-field-name').focus(); }, 50);
}
