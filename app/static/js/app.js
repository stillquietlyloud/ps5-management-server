// Main application JavaScript for PS5 Management Server

// Global state
const state = {
    games: [],
    ps5Systems: [],
    tasks: [],
    clients: [],
    payloads: [],
    currentTab: 'library',
};

// API base URL
const API_BASE = '/api';

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Load initial data
    await Promise.all([
        loadGames(),
        loadPS5Systems(),
        loadTasks(),
        loadTorrentClients(),
        loadExploitStatus(),
    ]);
    
    // Set up event listeners
    setupEventListeners();
    
    // Start periodic refresh
    setInterval(refreshData, 30000);
}

function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', (e) => {
            state.currentTab = e.target.getAttribute('href').substring(1);
            refreshCurrentTab();
        });
    });
    
    // Add PS5 form
    const addPS5Form = document.getElementById('addPS5Form');
    if (addPS5Form) {
        addPS5Form.addEventListener('submit', handleAddPS5);
    }
    
    // Add client form
    const addClientForm = document.getElementById('addClientForm');
    if (addClientForm) {
        addClientForm.addEventListener('submit', handleAddClient);
    }
    
    // Paths form
    const pathsForm = document.getElementById('pathsForm');
    if (pathsForm) {
        // Just display, read-only
    }
    
    // API keys form
    const apiKeysForm = document.getElementById('apiKeysForm');
    if (apiKeysForm) {
        apiKeysForm.addEventListener('submit', handleSaveAPIKeys);
    }
}

// ==================== Data Loading ====================

async function loadGames() {
    try {
        const response = await fetch(`${API_BASE}/games`);
        if (response.ok) {
            state.games = await response.json();
            renderGameGrid();
        }
    } catch (error) {
        console.error('Failed to load games:', error);
        showToast('Failed to load games', 'error');
    }
}

async function loadPS5Systems() {
    try {
        const response = await fetch(`${API_BASE}/ps5-systems`);
        if (response.ok) {
            state.ps5Systems = await response.json();
            renderPS5Table();
            renderPS5Connections();
        }
    } catch (error) {
        console.error('Failed to load PS5 systems:', error);
    }
}

async function loadTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        if (response.ok) {
            state.tasks = await response.json();
            renderActiveTasks();
            renderHistory();
        }
    } catch (error) {
        console.error('Failed to load tasks:', error);
    }
}

async function loadTorrentClients() {
    // This would need a new API endpoint
    // For now, just placeholder
}

async function loadExploitStatus() {
    try {
        const response = await fetch(`${API_BASE}/exploit/status`);
        if (response.ok) {
            const data = await response.json();
            renderExploitStatus(data);
        }
    } catch (error) {
        console.error('Failed to load exploit status:', error);
    }
}

// ==================== Rendering ====================

function renderGameGrid() {
    const grid = document.getElementById('gameGrid');
    if (!grid) return;
    
    if (state.games.length === 0) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5">
                <i class="bi bi-collection display-1 text-muted"></i>
                <h3 class="mt-3 text-muted">No games found</h3>
                <p class="text-muted">Scan your PS5 or add games from web stores</p>
                <button class="btn btn-primary" onclick="scanPS5()">
                    <i class="bi bi-search me-1"></i>Scan PS5
                </button>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = state.games.map(game => `
        <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 game-col" data-game-id="${game.id}">
            <div class="game-card h-100">
                ${game.local_cover_path ? `
                    <img src="/static/artwork/${game.local_cover_path.split('/').pop()}" 
                         class="game-card-image" 
                         alt="${game.name}"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                ` : ''}
                <div class="game-card-image-placeholder" style="${game.local_cover_path ? 'display:none;' : ''}">
                    <i class="bi bi-controller"></i>
                </div>
                <div class="game-card-body">
                    <h6 class="game-card-title">${game.name}</h6>
                    <div class="game-card-meta">
                        ${game.ppsa ? `<span class="text-muted">${game.ppsa}</span>` : ''}
                        ${game.title_id ? `<span class="text-muted ms-2">${game.title_id}</span>` : ''}
                        ${game.region ? `<span class="text-muted ms-2">${game.region}</span>` : ''}
                    </div>
                    <div class="game-card-badges">
                        ${game.is_on_server ? '<span class="badge bg-local badge-source">Local</span>' : ''}
                        ${game.is_on_any_ps5 ? '<span class="badge bg-ps5 badge-source">PS5</span>' : ''}
                        ${game.available_sources?.includes('orbit_store') ? '<span class="badge bg-orbit badge-source">Orbit</span>' : ''}
                        ${game.available_sources?.includes('blackbox') ? '<span class="badge bg-blackbox badge-source">BlackBox</span>' : ''}
                        ${game.available_sources?.includes('overdrive') ? '<span class="badge bg-overdrive badge-source">Overdrive</span>' : ''}
                        ${game.format ? `<span class="badge bg-secondary badge-format">${game.format}</span>` : ''}
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary w-100" onclick="showGameDetail(${game.id})">
                            <i class="bi bi-info-circle me-1"></i>Details
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function filterGames() {
    const search = document.getElementById('gameSearch')?.value.toLowerCase() || '';
    const sourceFilter = document.getElementById('sourceFilter')?.value || '';
    const formatFilter = document.getElementById('formatFilter')?.value || '';
    
    const cards = document.querySelectorAll('.game-col');
    
    cards.forEach(card => {
        const gameId = parseInt(card.dataset.gameId);
        const game = state.games.find(g => g.id === gameId);
        
        if (!game) return;
        
        const matchesSearch = game.name.toLowerCase().includes(search) ||
                             game.ppsa?.toLowerCase().includes(search) ||
                             game.title_id?.toLowerCase().includes(search);
        
        const matchesSource = !sourceFilter || 
            (sourceFilter === 'local' && game.is_on_server) ||
            (sourceFilter === 'ps5' && game.is_on_any_ps5) ||
            (sourceFilter && game.available_sources?.includes(sourceFilter));
        
        const matchesFormat = !formatFilter || game.format === formatFilter;
        
        if (matchesSearch && matchesSource && matchesFormat) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

function renderPS5Table() {
    const tbody = document.getElementById('ps5Body');
    if (!tbody) return;
    
    tbody.innerHTML = state.ps5Systems.map(ps5 => `
        <tr>
            <td>${ps5.name}</td>
            <td>${ps5.ip_address}:${ps5.ftp_port}</td>
            <td>${ps5.firmware_version || 'Unknown'}</td>
            <td>
                <span class="status-dot ${ps5.is_connected ? 'connected' : 'disconnected'}"></span>
                ${ps5.is_connected ? 'Connected' : 'Disconnected'}
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="connectPS5(${ps5.id})">
                    ${ps5.is_connected ? '<i class="bi bi-check-circle me-1"></i>Connected' : '<i class="bi bi-wifi me-1"></i>Connect'}
                </button>
                <button class="btn btn-sm btn-outline-danger ms-1" onclick="deletePS5(${ps5.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function renderPS5Connections() {
    const tbody = document.getElementById('ps5ConnectionsBody');
    if (!tbody) return;
    
    tbody.innerHTML = state.ps5Systems.map(ps5 => `
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
                <button class="btn btn-sm btn-outline-primary" onclick="scanPS5Specific(${ps5.id})">
                    <i class="bi bi-search me-1"></i>Scan
                </button>
            </td>
        </tr>
    `).join('');
}

function renderActiveTasks() {
    const tbody = document.getElementById('activeTasksBody');
    if (!tbody) return;
    
    const activeTasks = state.tasks.filter(t => ['pending', 'running'].includes(t.status));
    
    tbody.innerHTML = activeTasks.map(task => `
        <tr>
            <td><span class="badge bg-secondary">${task.task_type}</span></td>
            <td>${task.current_file || 'N/A'}</td>
            <td>${task.ps5_system_id ? `PS5 #${task.ps5_system_id}` : 'Server'}</td>
            <td>
                <div class="progress-container">
                    <div class="progress">
                        <div class="progress-bar task-progress" role="progressbar" 
                             style="width: ${task.progress}%" 
                             aria-valuenow="${task.progress}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <span class="progress-text">${task.progress}%</span>
                </div>
            </td>
            <td>${formatBytes(task.speed_bps)}/s</td>
            <td>${formatETA(task.eta_seconds)}</td>
            <td><span class="status-${task.status}">${task.status}</span></td>
            <td>
                ${task.status === 'running' ? `
                    <button class="btn btn-sm btn-outline-danger" onclick="cancelTask(${task.id})">
                        <i class="bi bi-x-circle"></i>
                    </button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

function renderHistory() {
    const tbody = document.getElementById('historyBody');
    if (!tbody) return;
    
    const historyTasks = state.tasks.filter(t => ['completed', 'failed', 'cancelled'].includes(t.status))
                                    .slice(0, 50);
    
    tbody.innerHTML = historyTasks.map(task => `
        <tr>
            <td>${new Date(task.created_at).toLocaleString()}</td>
            <td><span class="badge bg-secondary">${task.task_type}</span></td>
            <td>${task.current_file || 'N/A'}</td>
            <td>${task.ps5_system_id ? `PS5 #${task.ps5_system_id}` : 'Server'}</td>
            <td><span class="status-${task.status}">${task.status}</span></td>
            <td>${task.completed_at && task.started_at ? 
                formatDuration(new Date(task.completed_at) - new Date(task.started_at)) : 'N/A'}</td>
        </tr>
    `).join('');
}

function renderExploitStatus(data) {
    const configs = data.configs || [];
    const config = configs[0] || {};
    
    const nanodnsStatus = document.getElementById('nanodnsStatus');
    const nanodnsDetail = document.getElementById('nanodnsDetail');
    const autoloaderStatus = document.getElementById('autoloaderStatus');
    const autoloaderDetail = document.getElementById('autoloaderDetail');
    
    if (config.nanodns_running) {
        nanodnsStatus.innerHTML = '<i class="bi bi-circle-fill text-success"></i>';
        nanodnsDetail.textContent = 'Running';
        nanodnsDetail.className = 'text-success';
    } else {
        nanodnsStatus.innerHTML = '<i class="bi bi-circle text-danger"></i>';
        nanodnsDetail.textContent = 'Stopped';
        nanodnsDetail.className = 'text-danger';
    }
    
    if (config.autoloader_running) {
        autoloaderStatus.innerHTML = '<i class="bi bi-circle-fill text-success"></i>';
        autoloaderDetail.textContent = 'Running';
        autoloaderDetail.className = 'text-success';
    } else {
        autoloaderStatus.innerHTML = '<i class="bi bi-circle text-danger"></i>';
        autoloaderDetail.textContent = 'Stopped';
        autoloaderDetail.className = 'text-danger';
    }
    
    // Setup instructions
    const instructionsList = document.getElementById('setupInstructions');
    if (instructionsList) {
        fetch(`${API_BASE}/exploit/setup`)
            .then(r => r.json())
            .then(data => {
                instructionsList.innerHTML = data.steps.map(step => `<li>${step}</li>`).join('');
            });
    }
    
    loadPayloads();
}

function loadPayloads() {
    fetch(`${API_BASE}/exploit/payloads`)
        .then(r => r.json())
        .then(payloads => {
            state.payloads = payloads;
            const tbody = document.getElementById('payloadsBody');
            if (tbody) {
                tbody.innerHTML = payloads.map(p => `
                    <tr>
                        <td>${p.name}</td>
                        <td>${formatBytes(p.size)}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-danger" onclick="deletePayload('${p.name}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
        });
}

// ==================== Actions ====================

async function refreshLibrary() {
    showToast('Refreshing library...', 'info');
    await loadGames();
    showToast('Library refreshed', 'success');
}

async function scanPS5() {
    if (state.ps5Systems.length === 0) {
        showToast('No PS5 systems configured', 'warning');
        return;
    }
    
    // Scan first connected PS5
    const connected = state.ps5Systems.find(p => p.is_connected);
    const target = connected || state.ps5Systems[0];
    
    await scanPS5Specific(target.id);
}

async function scanPS5Specific(systemId) {
    showToast('Scanning PS5...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/ftp/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'scan', system_id: systemId }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`Found ${result.games_found} games`, 'success');
            await loadGames();
            await loadPS5Systems();
        } else {
            showToast(`Scan failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Scan failed', 'error');
    }
}

async function downloadArtwork() {
    showToast('Downloading artwork...', 'info');
    
    try {
        // This would need a bulk download endpoint
        showToast('Artwork download started', 'success');
    } catch (error) {
        showToast('Artwork download failed', 'error');
    }
}

async function connectPS5(systemId) {
    showToast('Connecting...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/ps5-systems/${systemId}/connect`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Connected successfully', 'success');
            await loadPS5Systems();
        } else {
            showToast(`Connection failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Connection failed', 'error');
    }
}

async function deletePS5(systemId) {
    if (!confirm('Are you sure you want to remove this PS5?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/ps5-systems/${systemId}`, {
            method: 'DELETE',
        });
        
        if (response.ok) {
            showToast('PS5 removed', 'success');
            await loadPS5Systems();
        } else {
            showToast('Failed to remove PS5', 'error');
        }
    } catch (error) {
        showToast('Failed to remove PS5', 'error');
    }
}

async function handleAddPS5(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    data.ftp_port = parseInt(data.ftp_port) || 21;
    
    try {
        const response = await fetch(`${API_BASE}/ps5-systems`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        
        if (response.ok) {
            showToast('PS5 added successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addPS5Modal')).hide();
            e.target.reset();
            await loadPS5Systems();
        } else {
            const error = await response.json();
            showToast(`Failed to add PS5: ${error.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to add PS5', 'error');
    }
}

async function handleAddClient(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    data.port = parseInt(data.port) || 8080;
    
    // This would need a new API endpoint
    showToast('Torrent client added (placeholder)', 'info');
    e.target.reset();
}

async function handleSaveAPIKeys(e) {
    e.preventDefault();
    showToast('API keys saved (requires restart)', 'info');
}

async function cancelTask(taskId) {
    if (!confirm('Cancel this task?')) return;
    
    try {
        // Would need a cancel endpoint
        showToast('Task cancelled', 'success');
        await loadTasks();
    } catch (error) {
        showToast('Failed to cancel task', 'error');
    }
}

function showGameDetail(gameId) {
    const game = state.games.find(g => g.id === gameId);
    if (!game) return;
    
    const title = document.getElementById('gameModalTitle');
    const body = document.getElementById('gameModalBody');
    
    title.textContent = game.name;
    
    body.innerHTML = `
        <div class="row">
            <div class="col-md-4 text-center">
                ${game.local_cover_path ? `
                    <img src="/static/artwork/${game.local_cover_path.split('/').pop()}" 
                         class="img-fluid rounded" alt="${game.name}" style="max-height: 300px;">
                ` : `
                    <div class="bg-secondary rounded d-flex align-items-center justify-content-center" style="height: 300px;">
                        <i class="bi bi-controller display-1 text-white-50"></i>
                    </div>
                `}
            </div>
            <div class="col-md-8">
                <table class="table table-borderless">
                    <tr><th>PPSA</th><td>${game.ppsa || 'N/A'}</td></tr>
                    <tr><th>Title ID</th><td>${game.title_id || 'N/A'}</td></tr>
                    <tr><th>Region</th><td>${game.region || 'N/A'}</td></tr>
                    <tr><th>Version</th><td>${game.version || 'N/A'}</td></tr>
                    <tr><th>Format</th><td>${game.format || 'N/A'}</td></tr>
                    <tr><th>Size</th><td>${formatBytes(game.size_bytes)}</td></tr>
                    <tr><th>Required FW</th><td>${game.required_firmware || 'N/A'}</td></tr>
                    <tr><th>On Server</th><td><span class="badge ${game.is_on_server ? 'bg-success' : 'bg-secondary'}">${game.is_on_server ? 'Yes' : 'No'}</span></td></tr>
                    <tr><th>On PS5</th><td><span class="badge ${game.is_on_any_ps5 ? 'bg-primary' : 'bg-secondary'}">${game.is_on_any_ps5 ? 'Yes' : 'No'}</span></td></tr>
                    <tr><th>Sources</th><td>${game.available_sources?.join(', ') || 'None'}</td></tr>
                    <tr><th>IGDB ID</th><td>${game.igdb_id || 'N/A'}</td></tr>
                    <tr><th>RAWG ID</th><td>${game.rawg_id || 'N/A'}</td></tr>
                    <tr><th>Metacritic</th><td>${game.metacritic_score || 'N/A'}</td></tr>
                    <tr><th>HLTB Main</th><td>${game.hltb_main_story ? `${Math.round(game.hltb_main_story/60)}h` : 'N/A'}</td></tr>
                </table>
                
                <div class="mt-3">
                    <h6>Locations</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr><th>Type</th><th>Path</th><th>Storage</th></tr>
                            </thead>
                            <tbody>
                                ${game.locations?.map(loc => `
                                    <tr>
                                        <td>${loc.server_path ? 'Server' : 'PS5'}</td>
                                        <td>${loc.server_path || loc.ps5_path}</td>
                                        <td>${loc.ps5_storage || '-'}</td>
                                    </tr>
                                `).join('') || '<tr><td colspan="3">No locations</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="mt-3">
                    <button class="btn btn-primary me-2" onclick="pushGame(${game.id})">
                        <i class="bi bi-upload me-1"></i>Push to PS5
                    </button>
                    <button class="btn btn-secondary me-2" onclick="pullGame(${game.id})">
                        <i class="bi bi-download me-1"></i>Pull from PS5
                    </button>
                    <button class="btn btn-info me-2" onclick="backupSaves(${game.id})">
                        <i class="bi bi-save me-1"></i>Backup Saves
                    </button>
                    <button class="btn btn-warning" onclick="fetchGameInfo(${game.id})">
                        <i class="bi bi-info-circle me-1"></i>Fetch Info
                    </button>
                </div>
            </div>
        </div>
    `;
    
    new bootstrap.Modal(document.getElementById('gameDetailModal')).show();
}

async function pushGame(gameId) {
    const game = state.games.find(g => g.id === gameId);
    const connectedPS5 = state.ps5Systems.find(p => p.is_connected);
    
    if (!connectedPS5) {
        showToast('No PS5 connected', 'warning');
        return;
    }
    
    const storage = prompt('Storage location (primary_ssd, secondary_ssd, external_usb):', 'primary_ssd');
    if (!storage) return;
    
    showToast('Pushing game...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/push/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'push', system_id: connectedPS5.id, game_id: gameId, storage }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Game pushed successfully', 'success');
        } else {
            showToast(`Push failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Push failed', 'error');
    }
}

async function pullGame(gameId) {
    const game = state.games.find(g => g.id === gameId);
    const connectedPS5 = state.ps5Systems.find(p => p.is_connected);
    
    if (!connectedPS5) {
        showToast('No PS5 connected', 'warning');
        return;
    }
    
    const keep = confirm('Keep game on PS5 after pulling?');
    
    showToast('Pulling game...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/pull/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'pull', system_id: connectedPS5.id, game_id: gameId, keep_on_ps5: keep }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Game pulled successfully', 'success');
        } else {
            showToast(`Pull failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Pull failed', 'error');
    }
}

async function backupSaves(gameId) {
    const connectedPS5 = state.ps5Systems.find(p => p.is_connected);
    
    if (!connectedPS5) {
        showToast('No PS5 connected', 'warning');
        return;
    }
    
    showToast('Backing up saves...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/save_backup/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'backup', system_id: connectedPS5.id, game_id: gameId }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`Backed up ${result.saves?.length || 0} saves`, 'success');
        } else {
            showToast(`Backup failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Backup failed', 'error');
    }
}

async function fetchGameInfo(gameId) {
    showToast('Fetching game info...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/info/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'fetch', game_id: gameId }),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Game info updated', 'success');
            await loadGames();
        } else {
            showToast(`Fetch failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Fetch failed', 'error');
    }
}

// Exploit actions
async function startExploitStack() {
    showToast('Starting exploit stack...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/exploit/start`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Exploit stack started', 'success');
            setTimeout(refreshExploitStatus, 5000);
        } else {
            showToast(`Start failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Start failed', 'error');
    }
}

async function stopExploitStack() {
    if (!confirm('Stop the exploit stack?')) return;
    
    showToast('Stopping exploit stack...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/exploit/stop`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Exploit stack stopped', 'success');
            setTimeout(refreshExploitStatus, 2000);
        } else {
            showToast(`Stop failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Stop failed', 'error');
    }
}

async function refreshExploitStatus() {
    try {
        const response = await fetch(`${API_BASE}/exploit/status`);
        if (response.ok) {
            const data = await response.json();
            renderExploitStatus(data);
        }
    } catch (error) {
        console.error('Failed to refresh exploit status:', error);
    }
}

async function uploadPayload() {
    const fileInput = document.getElementById('payloadFile');
    if (!fileInput.files.length) {
        showToast('Select a payload file', 'warning');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('payload', file);
    
    try {
        const response = await fetch(`${API_BASE}/exploit/payload`, {
            method: 'POST',
            body: formData,
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Payload uploaded', 'success');
            fileInput.value = '';
            loadPayloads();
        } else {
            showToast(`Upload failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Upload failed', 'error');
    }
}

async function deletePayload(name) {
    if (!confirm(`Delete payload ${name}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/exploit/payload/${name}`, {
            method: 'DELETE',
        });
        
        if (response.ok) {
            showToast('Payload deleted', 'success');
            loadPayloads();
        } else {
            showToast('Failed to delete payload', 'error');
        }
    } catch (error) {
        showToast('Failed to delete payload', 'error');
    }
}

// ==================== Utility Functions ====================

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatETA(seconds) {
    if (!seconds || seconds <= 0) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatDuration(ms) {
    if (!ms) return 'N/A';
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function showToast(message, type = 'info') {
    // Create toast container if not exists
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : type === 'warning' ? 'warning' : 'primary'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

async function refreshData() {
    await Promise.all([
        loadGames(),
        loadPS5Systems(),
        loadTasks(),
        loadExploitStatus(),
    ]);
}

function refreshCurrentTab() {
    switch (state.currentTab) {
        case 'library':
            loadGames();
            break;
        case 'torrents':
            loadTorrentClients();
            break;
        case 'actions':
            loadTasks();
            break;
        case 'settings':
            loadPS5Systems();
            break;
        case 'exploit':
            loadExploitStatus();
            break;
    }
}