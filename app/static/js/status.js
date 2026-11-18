// Status page JavaScript for PS5 Management Server

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    loadAllStatusData();
    setInterval(loadAllStatusData, 30000);
});

async function loadAllStatusData() {
    await Promise.all([
        loadModuleHealth(),
        loadServiceStatus(),
        loadSystemResources(),
        loadStorageInfo(),
        loadPS5Connections(),
        loadRecentTasks(),
    ]);
}

async function loadModuleHealth() {
    try {
        const response = await fetch(`${API_BASE}/modules`);
        if (response.ok) {
            const data = await response.json();
            renderModuleHealth(data);
        }
    } catch (error) {
        console.error('Failed to load module health:', error);
    }
}

function renderModuleHealth(modules) {
    const container = document.getElementById('moduleHealthCards');
    if (!container) return;
    
    container.innerHTML = Object.entries(modules).map(([name, module]) => {
        const status = module.status;
        const isHealthy = status === 'ready' || status === 'running';
        
        return `
            <div class="col-md-6 col-lg-4 col-xl-3 mb-3">
                <div class="card h-100 ${isHealthy ? 'border-success' : 'border-danger'}">
                    <div class="card-body text-center">
                        <div class="display-4 ${isHealthy ? 'text-success' : 'text-danger'}">
                            <i class="bi ${getModuleIcon(name)}"></i>
                        </div>
                        <h6 class="card-title mt-2">${module.info.name}</h6>
                        <p class="card-text small text-muted">${module.info.description}</p>
                        <span class="badge ${isHealthy ? 'bg-success' : 'bg-danger'}">${status}</span>
                        <div class="mt-2">
                            <small class="text-muted">v${module.info.version}</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function getModuleIcon(name) {
    const icons = {
        'ftp': 'bi-hdd-network',
        'push': 'bi-upload',
        'pull': 'bi-download',
        'save_backup': 'bi-save',
        'save_restore': 'bi-arrow-clockwise',
        'ppsa': 'bi-barcode',
        'artwork': 'bi-image',
        'store_db': 'bi-shop',
        'download': 'bi-cloud-download',
        'convert': 'bi-arrow-left-right',
        'info': 'bi-info-circle',
        'exploit': 'bi-shield-lock',
    };
    return icons[name] || 'bi-puzzle';
}

async function loadServiceStatus() {
    try {
        const response = await fetch(`${API_BASE}/services/status`);
        if (response.ok) {
            const data = await response.json();
            renderServiceStatus(data);
        }
    } catch (error) {
        console.error('Failed to load service status:', error);
    }
}

function renderServiceStatus(services) {
    const tbody = document.getElementById('serviceStatusBody');
    if (!tbody) return;
    
    tbody.innerHTML = services.map(s => {
        const successRate = s.run_count > 0 ? ((s.success_count / s.run_count) * 100).toFixed(1) : 0;
        
        return `
            <tr>
                <td>${s.service_name}</td>
                <td><span class="badge ${s.is_running ? 'bg-success' : 'bg-secondary'}">${s.is_running ? 'Running' : 'Stopped'}</span></td>
                <td>${s.last_run ? new Date(s.last_run).toLocaleString() : 'Never'}</td>
                <td>${s.last_success ? new Date(s.last_success).toLocaleString() : 'Never'}</td>
                <td>${s.run_count}</td>
                <td>${successRate}%</td>
                <td>${formatDuration(s.avg_duration_seconds * 1000)}</td>
                <td>${s.last_error || '-'}</td>
            </tr>
        `;
    }).join('');
}

async function loadSystemResources() {
    try {
        const response = await fetch(`${API_BASE}/system/resources`);
        if (response.ok) {
            const data = await response.json();
            renderSystemResources(data);
        }
    } catch (error) {
        console.error('Failed to load system resources:', error);
    }
}

function renderSystemResources(data) {
    const cpuEl = document.getElementById('cpuUsage');
    const memEl = document.getElementById('memoryUsage');
    const diskEl = document.getElementById('diskUsage');
    const netEl = document.getElementById('networkIO');
    
    if (cpuEl) cpuEl.textContent = `${data.cpu_percent || 0}%`;
    if (memEl) memEl.textContent = `${data.memory_percent || 0}%`;
    if (diskEl) diskEl.textContent = `${data.disk_percent || 0}%`;
    if (netEl) netEl.textContent = `${(data.network_io_mbps || 0).toFixed(1)} MB/s`;
}

async function loadStorageInfo() {
    try {
        const response = await fetch(`${API_BASE}/system/storage`);
        if (response.ok) {
            const data = await response.json();
            renderStorageInfo(data);
        }
    } catch (error) {
        console.error('Failed to load storage info:', error);
    }
}

function renderStorageInfo(paths) {
    const tbody = document.getElementById('storageBody');
    if (!tbody) return;
    
    tbody.innerHTML = paths.map(p => `
        <tr>
            <td>${p.path}</td>
            <td>${formatBytes(p.total)}</td>
            <td>${formatBytes(p.used)}</td>
            <td>${formatBytes(p.free)}</td>
            <td>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar ${p.percent > 90 ? 'bg-danger' : p.percent > 70 ? 'bg-warning' : 'bg-success'}" 
                         role="progressbar" style="width: ${p.percent}%"></div>
                </div>
                <small>${p.percent.toFixed(1)}%</small>
            </td>
        </tr>
    `).join('');
}

async function loadPS5Connections() {
    try {
        const response = await fetch(`${API_BASE}/ps5-systems`);
        if (response.ok) {
            const data = await response.json();
            renderPS5ConnectionsTable(data);
        }
    } catch (error) {
        console.error('Failed to load PS5 connections:', error);
    }
}

function renderPS5ConnectionsTable(systems) {
    const tbody = document.getElementById('ps5ConnectionsBody');
    if (!tbody) return;
    
    tbody.innerHTML = systems.map(ps5 => `
        <tr>
            <td>${ps5.name}</td>
            <td>${ps5.ip_address}</td>
            <td>${ps5.firmware_version || 'Unknown'}</td>
            <td>
                <span class="status-dot ${ps5.is_connected ? 'connected' : 'disconnected'}"></span>
                ${ps5.is_connected ? 'Yes' : 'No'}
            </td>
            <td>${ps5.last_seen ? new Date(ps5.last_seen).toLocaleString() : 'Never'}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="window.location.href='/#library'">
                    <i class="bi bi-search me-1"></i>Scan
                </button>
            </td>
        </tr>
    `).join('');
}

async function loadRecentTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        if (response.ok) {
            const data = await response.json();
            renderRecentTasks(data.slice(0, 20));
        }
    } catch (error) {
        console.error('Failed to load recent tasks:', error);
    }
}

function renderRecentTasks(tasks) {
    const tbody = document.getElementById('recentTasksBody');
    if (!tbody) return;
    
    tbody.innerHTML = tasks.map(task => `
        <tr>
            <td>${new Date(task.created_at).toLocaleString()}</td>
            <td><span class="badge bg-secondary">${task.task_type}</span></td>
            <td>${task.current_file || 'N/A'}</td>
            <td>${task.ps5_system_id ? `PS5 #${task.ps5_system_id}` : 'Server'}</td>
            <td><span class="status-${task.status}">${task.status}</span></td>
            <td>${task.completed_at && task.started_at ? 
                formatDuration(new Date(task.completed_at) - new Date(task.started_at)) : 'Running'}</td>
        </tr>
    `).join('');
}

// Utility functions
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(ms) {
    if (!ms) return 'N/A';
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}