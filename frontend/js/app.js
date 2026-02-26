// ════════════════════════════════════════
// LIFEOS — app.js
// ════════════════════════════════════════

const API_URL = 'http://127.0.0.1:8001/api/v1';

// ════════════════════════════════════════
// TOAST SYSTEM
// ════════════════════════════════════════

const TOAST_TYPES = {
    success: { icon: '✓', color: '#34d399' },
    error:   { icon: '✕', color: '#f87171' },
    info:    { icon: '●', color: '#4f7cff'  },
    warning: { icon: '⚠', color: '#fb923c' },
};

let toastQueue   = [];
let toastVisible = false;

function showToast(msg, type = 'success') {
    toastQueue.push({ msg, type });
    if (!toastVisible) processToastQueue();
}

function processToastQueue() {
    if (!toastQueue.length) { toastVisible = false; return; }
    toastVisible = true;
    const { msg, type } = toastQueue.shift();
    const t   = document.getElementById('toast');
    const cfg = TOAST_TYPES[type] || TOAST_TYPES.success;
    t.innerHTML = `<span style="color:${cfg.color};font-size:14px;font-weight:700">${cfg.icon}</span><span>${msg}</span>`;
    t.className = 'show';
    setTimeout(() => { t.className = ''; setTimeout(processToastQueue, 320); }, 2800);
}

// ════════════════════════════════════════
// CONFIRMATION MODAL SYSTEM
// ════════════════════════════════════════

let confirmCallback = null;

function showConfirm({ title, message, confirmText = 'Confirm', danger = false, onConfirm }) {
    confirmCallback = onConfirm;
    document.getElementById('confirm-modal-title').textContent   = title;
    document.getElementById('confirm-modal-message').textContent = message;
    const btn     = document.getElementById('confirm-modal-ok');
    btn.textContent = confirmText;
    btn.className   = danger ? 'btn-danger' : 'btn-primary modal-confirm';
    document.getElementById('confirm-modal').classList.add('open');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('open');
    confirmCallback = null;
}

function executeConfirm() {
    if (confirmCallback) confirmCallback();
    closeConfirmModal();
}

// ════════════════════════════════════════
// TOKEN MANAGEMENT
// ════════════════════════════════════════

function getTokens() {
    return { access: localStorage.getItem('access_token'), refresh: localStorage.getItem('refresh_token') };
}
function saveTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
}
function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
}

// ════════════════════════════════════════
// API HELPER
// ════════════════════════════════════════

async function tryRefresh() {
    const { refresh } = getTokens();
    if (!refresh) return false;
    try {
        const res = await fetch(`${API_URL}/refresh`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        saveTokens(data.access_token, data.refresh_token);
        return true;
    } catch { return false; }
}

async function apiFetch(endpoint, options = {}, retry = true) {
    const { access } = getTokens();
    const headers = {
        'Content-Type': 'application/json',
        ...(access && { 'Authorization': `Bearer ${access}` }),
        ...options.headers,
    };
    const res = await fetch(`${API_URL}${endpoint}`, { ...options, headers });
    if (res.status === 401 && retry) {
        const refreshed = await tryRefresh();
        if (refreshed) return apiFetch(endpoint, options, false);
        handleLogout();
        throw new Error('Session expired. Please sign in again.');
    }
    if (res.status === 204) return null;
    return res.json();
}

// ════════════════════════════════════════
// AUTH
// ════════════════════════════════════════

function switchAuthTab(tab) {
    const tabs = document.querySelectorAll('.login-tab');
    tabs[0].classList.toggle('active', tab === 'login');
    tabs[1].classList.toggle('active', tab === 'register');
    document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
    document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
    hideError('login-error');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('login-error');
    const formData = new URLSearchParams();
    formData.append('username', document.getElementById('email').value);
    formData.append('password', document.getElementById('password').value);
    try {
        const res = await fetch(`${API_URL}/login`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Invalid email or password.');
        const data = await res.json();
        saveTokens(data.access_token, data.refresh_token);
        showToast('Welcome back! 👋', 'success');
        bootApp();
    } catch (err) { showError('login-error', err.message); }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('login-error');
    const name = document.getElementById('reg-name').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    if (password.length < 8) { showError('login-error', 'Password must be at least 8 characters.'); return; }
    try {
        const res = await apiFetch('/users/', { method: 'POST', body: JSON.stringify({ name, email, password }) });
        if (res.detail) throw new Error(Array.isArray(res.detail) ? res.detail[0].msg : res.detail);
        showToast('Account created! Please sign in.', 'success');
        switchAuthTab('login');
        document.getElementById('email').value = email;
    } catch (err) { showError('login-error', err.message || 'Registration failed.'); }
});

function handleLogout() {
    clearTokens();
    document.getElementById('app-screen').classList.add('hidden');
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('email').value = '';
    document.getElementById('password').value = '';
}

function confirmLogout() {
    showConfirm({
        title: 'Log Out', message: 'Are you sure you want to log out of LifeOS?',
        confirmText: 'Log Out', danger: true,
        onConfirm: () => { showToast('You have been logged out.', 'info'); setTimeout(handleLogout, 700); },
    });
}

// ════════════════════════════════════════
// BOOT + NAV
// ════════════════════════════════════════

function bootApp() {
    const { access } = getTokens();
    if (!access) { handleLogout(); return; }
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app-screen').classList.remove('hidden');
    setGreeting();
    loadProfile();
    const lastTab = localStorage.getItem('active_tab') || 'dashboard';
    switchTab(lastTab);
}

function setGreeting() {
    const h = new Date().getHours();
    const greet = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
    document.getElementById('dash-greeting').textContent = `${greet}! Here's your overview.`;
}

function switchTab(tabName) {
    localStorage.setItem('active_tab', tabName);
    ['dashboard', 'tasks', 'habits', 'profile'].forEach(t => {
        document.getElementById(`${t}-view`).classList.add('hidden');
        const btn = document.getElementById(`tab-btn-${t}`);
        if (btn) btn.classList.remove('active');
    });
    document.getElementById(`${tabName}-view`).classList.remove('hidden');
    const btn = document.getElementById(`tab-btn-${tabName}`);
    if (btn) btn.classList.add('active');
    if (tabName === 'dashboard') loadDashboard();
    if (tabName === 'tasks')     loadTasks();
    if (tabName === 'habits')    loadHabits();
    if (tabName === 'profile')   loadProfile();
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('open');
}

function toggleMobileSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('open');
}

// ════════════════════════════════════════
// TASKS
// ════════════════════════════════════════

// ── Task pagination state ──
let taskPage = 1;
let taskHasNext = false;

async function loadTasks(page = 1) {
    try {
        const data = await apiFetch(`/tasks/?page=${page}&limit=20`);
        taskPage    = data.page;
        taskHasNext = data.has_next;

        if (page === 1) {
            renderTasks(data.items, data);
        } else {
            appendTasks(data.items);    // append instead of replace
            updateTaskPagination(data);
        }
    } catch (e) { console.error('Failed to load tasks:', e); }
}


function submitTask() {
    const input = document.getElementById('new-task-title');
    const title = input.value.trim();
    const priority = document.getElementById('new-task-priority').value;
    if (!title) return;
    apiFetch('/tasks/', { method: 'POST', body: JSON.stringify({ title, priority }) })
        .then(() => { input.value = ''; loadTasks(); showToast('Task added!', 'success'); })
        .catch(() => showToast('Could not add task.', 'error'));
}
document.getElementById('new-task-title').addEventListener('keydown', e => { if (e.key === 'Enter') submitTask(); });

function toggleTask(id, title, currentStatus) {
    const isCompleting = currentStatus !== 'completed';
    showConfirm({
        title: isCompleting ? 'Complete Task?' : 'Mark as Pending?',
        message: isCompleting ? `Mark "${title}" as completed?` : `Move "${title}" back to pending?`,
        confirmText: isCompleting ? 'Mark Complete ✓' : 'Mark Pending',
        danger: false,
        onConfirm: async () => {
            await apiFetch(`/tasks/${id}/complete`, { method: 'PUT' });
            loadTasks();
            showToast(isCompleting ? `"${title}" completed! ✓` : `"${title}" moved to pending.`, isCompleting ? 'success' : 'info');
        },
    });
}

function confirmDeleteTask(id, title) {
    showConfirm({
        title: 'Delete Task', message: `Delete "${title}"? This cannot be undone.`,
        confirmText: 'Delete', danger: true,
        onConfirm: async () => {
        await apiFetch(`/tasks/${id}`, { method: 'DELETE' });
        taskPage = 1;          // ← add this
        loadTasks();
        showToast(`"${title}" deleted.`, 'warning');
        },
    });
}

function loadMoreTasks() {
    loadTasks(taskPage + 1);
}

function renderTasks(tasks, meta) {
    const el = document.getElementById('task-list');

    if (!tasks || !tasks.length) {
        el.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">✦</div>
                <div class="empty-text">No tasks yet — add one above</div>
            </div>`;
        return;
    }

    const order  = { high: 0, medium: 1, low: 2 };
    const sorted = [...tasks].sort((a, b) => {
        if (a.status === 'completed' && b.status !== 'completed') return 1;
        if (b.status === 'completed' && a.status !== 'completed') return -1;
        return (order[a.priority] ?? 1) - (order[b.priority] ?? 1);
    });

    el.innerHTML = sorted.map(task => taskHTML(task)).join('') + paginationHTML(meta, 'task');
}

function appendTasks(tasks) {
    const el  = document.getElementById('task-list');
    const btn = document.getElementById('task-load-more');
    if (btn) btn.remove();

    const order  = { high: 0, medium: 1, low: 2 };
    const sorted = [...tasks].sort((a, b) => {
        if (a.status === 'completed' && b.status !== 'completed') return 1;
        if (b.status === 'completed' && a.status !== 'completed') return -1;
        return (order[a.priority] ?? 1) - (order[b.priority] ?? 1);
    });

    el.insertAdjacentHTML('beforeend', sorted.map(task => taskHTML(task)).join(''));
    updateTaskPagination({ has_next: taskHasNext, total: null });
}

function updateTaskPagination(meta) {
    const existing = document.getElementById('task-load-more');
    if (existing) existing.remove();
    if (meta.has_next) {
        document.getElementById('task-list').insertAdjacentHTML('beforeend', paginationHTML(meta, 'task'));
    }
}

function taskHTML(task) {
    const done = task.status === 'completed';
    return `<div class="task-item ${done ? 'done' : ''}">
        <div class="task-checkbox ${done ? 'checked' : ''}"
             onclick="toggleTask(${task.id}, '${esc(task.title)}', '${task.status}')">${done ? '✓' : ''}</div>
        <span class="task-title">${esc(task.title)}</span>
        <span class="priority-badge priority-${task.priority}">${task.priority}</span>
        <div class="task-actions">
            <button class="icon-btn" onclick="openEditModal('task', ${task.id}, '${esc(task.title)}')" title="Edit">✎</button>
            <button class="icon-btn del" onclick="confirmDeleteTask(${task.id}, '${esc(task.title)}')" title="Delete">✕</button>
        </div>
    </div>`;
}

// ════════════════════════════════════════
// HABITS
// ════════════════════════════════════════

// ── Habit pagination state ──
let habitPage    = 1;
let habitHasNext = false;

async function loadHabits(page = 1) {
    try {
        const data   = await apiFetch(`/habits/?page=${page}&limit=20`);
        habitPage    = data.page;
        habitHasNext = data.has_next;

        if (page === 1) {
            renderHabits(data.items, data);
        } else {
            appendHabits(data.items);
            updateHabitPagination(data);
        }
    } catch (e) { console.error('Failed to load habits:', e); }
}

function loadMoreHabits() {
    loadHabits(habitPage + 1);
}

function renderHabits(habits, meta) {
    const el = document.getElementById('habit-list');

    if (!habits || !habits.length) {
        el.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">◎</div>
                <div class="empty-text">No habits yet — start small and build momentum</div>
            </div>`;
        return;
    }

    el.innerHTML = habits.map(h => habitHTML(h)).join('') + paginationHTML(meta, 'habit');
}

function appendHabits(habits) {
    const el  = document.getElementById('habit-list');
    const btn = document.getElementById('habit-load-more');
    if (btn) btn.remove();
    el.insertAdjacentHTML('beforeend', habits.map(h => habitHTML(h)).join(''));
    updateHabitPagination({ has_next: habitHasNext });
}

function updateHabitPagination(meta) {
    const existing = document.getElementById('habit-load-more');
    if (existing) existing.remove();
    if (meta.has_next) {
        document.getElementById('habit-list').insertAdjacentHTML('beforeend', paginationHTML(meta, 'habit'));
    }
}

function habitHTML(h) {
    const pct = Math.min(h.current_streak * 10, 100);
    return `<div class="habit-card">
        <div class="habit-card-header">
            <div class="habit-name">${esc(h.name)}</div>
            <div class="streak-badge">🔥 ${h.current_streak}d</div>
        </div>
        <div class="habit-card-actions">
            <button class="action-btn" onclick="openEditModal('habit', ${h.id}, '${esc(h.name)}')">✎ Edit</button>
            <button class="action-btn del" onclick="confirmDeleteHabit(${h.id}, '${esc(h.name)}')">✕ Delete</button>
        </div>
        <div class="habit-progress">
            <div class="habit-progress-bar" style="width:${pct}%"></div>
        </div>
        ${h.is_logged_today
            ? `<button class="habit-check-btn done" onclick="undoHabitToday(${h.id}, '${esc(h.name)}')">✅ Done today — tap to undo</button>`
            : `<button class="habit-check-btn" onclick="logHabitToday(${h.id}, '${esc(h.name)}')">○ Check in for today</button>`
        }
    </div>`;
}

function submitHabit() {
    const input = document.getElementById('new-habit-name');
    const name  = input.value.trim();
    if (!name) return;
    apiFetch('/habits/', { method: 'POST', body: JSON.stringify({ name, target_type: 'daily' }) })
        .then(() => { input.value = ''; loadHabits(); showToast(`Habit "${name}" created!`, 'success'); })
        .catch(() => showToast('Could not create habit.', 'error'));
}
document.getElementById('new-habit-name').addEventListener('keydown', e => { if (e.key === 'Enter') submitHabit(); });

async function logHabitToday(habitId, habitName) {
    await apiFetch(`/habits/${habitId}/logs/`, { method: 'POST', body: JSON.stringify({ date: todayString(), completed: true }) });
    loadHabits();
    showToast(`"${habitName}" checked in! 🔥`, 'success');
}

function undoHabitToday(habitId, habitName) {
    showConfirm({
        title: 'Undo Check-in?', message: `Remove today's check-in for "${habitName}"?`,
        confirmText: 'Undo', danger: false,
        onConfirm: async () => {
            await apiFetch(`/habits/${habitId}/logs/`, { method: 'POST', body: JSON.stringify({ date: todayString(), completed: false }) });
            loadHabits();
            showToast(`Check-in for "${habitName}" undone.`, 'info');
        },
    });
}

function confirmDeleteHabit(id, name) {
    showConfirm({
        title: 'Delete Habit', message: `Delete "${name}" and all its history? This cannot be undone.`,
        confirmText: 'Delete Habit', danger: true,
        onConfirm: async () => {
        await apiFetch(`/habits/${id}`, { method: 'DELETE' });
        habitPage = 1;         // ← add this
        loadHabits();
        showToast(`"${name}" deleted.`, 'warning');
        },
    });
}


function paginationHTML(meta, type) {
    if (!meta.has_next) return '';
    return `<div id="${type}-load-more" style="text-align:center;padding:16px 0;grid-column:1/-1">
        <button class="btn-secondary" style="padding:10px 28px;font-size:13px"
            onclick="loadMore${type.charAt(0).toUpperCase() + type.slice(1)}s()">
            Load More
        </button>
    </div>`;
}
// ════════════════════════════════════════
// DASHBOARD
// ════════════════════════════════════════

let taskChart, habitChart;

async function loadDashboard() {
    try {
        const data = await apiFetch('/dashboard/');
        renderDashboard(data);
        loadWeeklyReport();   // ← load weekly report after dashboard data is rendered
    } catch (e) { console.error('Failed to load dashboard:', e); }
}

function renderDashboard(data) {
    document.getElementById('dash-productivity-score').textContent = data.productivity_score;
    document.getElementById('dash-completed-tasks').textContent    = data.completed_tasks;
    document.getElementById('dash-pending-tasks').textContent      = data.pending_tasks;
    document.getElementById('dash-logged-today').textContent       = data.habits_logged_today;
    document.getElementById('dash-total-habits').textContent       = data.total_habits;
    document.getElementById('dash-task-rate').textContent          = data.task_completion_rate + '%';
    document.getElementById('dash-habit-rate').textContent         = data.habit_consistency_rate + '%';
    const ring = document.getElementById('score-ring-fill');
    setTimeout(() => { ring.style.strokeDashoffset = 251.2 - (251.2 * data.productivity_score / 100); }, 200);
    const sl = document.getElementById('dash-streak-list');
    sl.innerHTML = (!data.current_streaks || !data.current_streaks.length)
        ? `<div class="empty-state" style="padding:20px"><div class="empty-text">No habits tracked yet</div></div>`
        : data.current_streaks.map(h => `
            <div class="streak-item">
                <div class="streak-dot ${h.logged_today ? 'active' : 'inactive'}"></div>
                <div class="streak-name">${esc(h.name)}</div>
                <div class="streak-count">🔥 ${h.streak}</div>
                <div class="streak-status ${h.logged_today ? 'done' : 'miss'}">${h.logged_today ? '✓ Done' : 'Pending'}</div>
            </div>`).join('');
    const chartOpts = { cutout: '72%', plugins: { legend: { labels: { color: '#8888aa', font: { family: "'Segoe UI', sans-serif", size: 12 } } } } };
    if (taskChart)  taskChart.destroy();
    if (habitChart) habitChart.destroy();
    taskChart = new Chart(document.getElementById('task-chart'), {
        type: 'doughnut',
        data: { labels: ['Completed', 'Pending'], datasets: [{ data: [data.completed_tasks, data.pending_tasks], backgroundColor: ['#4f7cff', '#1a1a24'], borderColor: ['#4f7cff', '#22222f'], borderWidth: 2 }] },
        options: chartOpts,
    });
    habitChart = new Chart(document.getElementById('habit-chart'), {
        type: 'doughnut',
        data: { labels: ['Consistent', 'Missed'], datasets: [{ data: [data.habit_consistency_rate, 100 - data.habit_consistency_rate], backgroundColor: ['#7c5cfc', '#1a1a24'], borderColor: ['#7c5cfc', '#22222f'], borderWidth: 2 }] },
        options: chartOpts,
    });
}

// ════════════════════════════════════════
// PROFILE
// ════════════════════════════════════════

function loadProfile() {
    const { access } = getTokens();
    if (!access) return;
    try {
        const payload = JSON.parse(atob(access.split('.')[1]));
        const email   = payload.sub || '';
        const name    = email.split('@')[0];
        const initial = name.charAt(0).toUpperCase();
        document.getElementById('profile-name').textContent     = name;
        document.getElementById('profile-email').textContent    = email;
        document.getElementById('profile-avatar').textContent   = initial;
        document.getElementById('sidebar-avatar').textContent   = initial;
        document.getElementById('sidebar-username').textContent = name;
    } catch (e) { console.error(e); }
}

function changePassword() {
    const current = document.getElementById('current-password').value;
    const newPw   = document.getElementById('new-password').value;
    const confirm = document.getElementById('confirm-password').value;
    hideError('pw-error');
    if (!current || !newPw || !confirm) { showError('pw-error', 'Please fill in all three fields.'); return; }
    if (newPw !== confirm) { showError('pw-error', 'New passwords do not match.'); return; }
    if (newPw.length < 8) { showError('pw-error', 'New password must be at least 8 characters.'); return; }
    showConfirm({
        title: 'Change Password', message: 'Are you sure you want to update your password?',
        confirmText: 'Yes, Update', danger: false,
        onConfirm: async () => {
            try {
                const res = await apiFetch('/users/change-password', { method: 'POST', body: JSON.stringify({ current_password: current, new_password: newPw }) });
                if (res && res.detail) throw new Error(res.detail);
                showToast('Password updated successfully!', 'success');
                document.getElementById('current-password').value = '';
                document.getElementById('new-password').value     = '';
                document.getElementById('confirm-password').value = '';
            } catch (err) {
                showError('pw-error', err.message || 'Incorrect current password.');
                showToast('Password update failed.', 'error');
            }
        },
    });
}

// ════════════════════════════════════════
// EDIT MODAL
// ════════════════════════════════════════

let editState = { type: null, id: null, originalName: null };

function openEditModal(type, id, currentName) {
    editState = { type, id, originalName: currentName };
    document.getElementById('edit-modal-title').textContent = type === 'task' ? 'Edit Task' : 'Edit Habit';
    document.getElementById('edit-modal-input').value       = currentName;
    document.getElementById('edit-modal').classList.add('open');
    setTimeout(() => document.getElementById('edit-modal-input').focus(), 80);
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('open');
}
// ── Weekly Report ──────────────────────
async function loadWeeklyReport() {
    try {
        const report = await apiFetch('/reports/latest');
        if (report && report.report) {
            document.getElementById('weekly-report-text').textContent = report.report;
            document.getElementById('weekly-report-card').style.display = 'block';
        }
    } catch (e) {
        // No report yet — card stays hidden, that's fine
    }
}

async function generateReportNow() {
    try {
        await apiFetch('/reports/generate', { method: 'POST' });
        showToast('Report generated!', 'success');
        loadWeeklyReport();
    } catch (e) {
        showToast('Could not generate report.', 'error');
    }
}
function saveEdit() {
    const val = document.getElementById('edit-modal-input').value.trim();
    if (!val) return;
    const { type, id, originalName } = editState;
    closeEditModal();
    showConfirm({
        title: 'Save Changes?', message: `Rename "${originalName}" to "${val}"?`,
        confirmText: 'Save', danger: false,
        onConfirm: async () => {
            try {
                if (type === 'task') {
                    await apiFetch(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify({ title: val }) });
                    loadTasks();
                    showToast(`Task renamed to "${val}".`, 'success');
                } else {
                    await apiFetch(`/habits/${id}`, { method: 'PUT', body: JSON.stringify({ name: val }) });
                    loadHabits();
                    showToast(`Habit renamed to "${val}".`, 'success');
                }
            } catch { showToast('Could not save changes.', 'error'); }
        },
    });
}

document.getElementById('edit-modal-input').addEventListener('keydown', e => {
    if (e.key === 'Enter')  saveEdit();
    if (e.key === 'Escape') closeEditModal();
});

// Close modals on overlay click
window.addEventListener('load', () => {
    document.getElementById('confirm-modal').addEventListener('click', e => { if (e.target === document.getElementById('confirm-modal')) closeConfirmModal(); });
    document.getElementById('edit-modal').addEventListener('click', e => { if (e.target === document.getElementById('edit-modal')) closeEditModal(); });
});

// ════════════════════════════════════════
// UTILS
// ════════════════════════════════════════

function esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function todayString() { return new Date().toLocaleDateString('en-CA'); }
function showError(id, msg) { const el = document.getElementById(id); el.textContent = msg; el.style.display = 'block'; }
function hideError(id) { document.getElementById(id).style.display = 'none'; }

// ════════════════════════════════════════
// START
// ════════════════════════════════════════
bootApp();