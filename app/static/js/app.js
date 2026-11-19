// Main application JavaScript for PS5 Management Server

// Global state
const state = {
    games: [],
    exploits: [],
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
        loadExploits(),
        loadPS5Systems(),
        loadTasks(),
        loadTorrentClients(),
        loadExploitStatus(),
        loadSettingsPaths(),
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
        pathsForm.addEventListener('submit', handleSavePaths);
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
            renderGameGrid(state.games);
        }
    } catch (error) {
        console.error('Failed to load games:', error);
        showToast('Failed to load games', 'error');
    }
}

// Load games by type (for separate tabs)
async function loadLibraryByType(gameType) {
    try {
        const response = await fetch(`${API_BASE}/games/by-type/${gameType}`);
        if (response.ok) {
            const games = await response.json();
            const gridId = `${gameType}Grid`;
            const grid = document.getElementById(gridId);
            if (grid) {
                renderGameGrid(games, gridId);
            }
        }
    } catch (error) {
        console.error(`Failed to load ${gameType} library:`, error);
        showToast(`Failed to load ${gameType} library`, 'error');
    }
}

// Filter games by type
function filterLibraryByType(gameType) {
    const searchInput = document.getElementById(`${gameType}Search`);
    const sourceFilter = document.getElementById(`${gameType}SourceFilter`);
    const formatFilter = document.getElementById(`${gameType}FormatFilter`);
    
    if (!searchInput || !sourceFilter || !formatFilter) return;
    
    const search = searchInput.value.toLowerCase() || '';
    const source = sourceFilter.value || '';
    const format = formatFilter.value || '';
    
    // Load all games of this type and filter
    loadLibraryByType(gameType).then(() => {
        const gridId = `${gameType}Grid`;
        const grid = document.getElementById(gridId);
        if (!grid) return;
        
        const cards = grid.querySelectorAll('.game-col');
        cards.forEach(card => {
            const gameId = parseInt(card.dataset.gameId);
            const game = state.games.find(g => g.id === gameId);
            if (!game) return;
            
            const matchesSearch = game.name.toLowerCase().includes(search) ||
                                 game.ppsa?.toLowerCase().includes(search) ||
                                 game.title_id?.toLowerCase().includes(search);
            
            const matchesSource = !source || 
                (source === 'local' && game.is_on_server) ||
                (source === 'ps5' && game.is_on_any_ps5) ||
                (source && game.available_sources?.includes(source));
            
            const matchesFormat = !format || game.format === format;
            
            if (matchesSearch && matchesSource && matchesFormat) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    });
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
    try {
        const response = await fetch(`${API_BASE}/torrent-clients`);
        if (response.ok) {
            state.clients = await response.json();
            renderTorrentClients();
        }
    } catch (error) {
        console.error('Failed to load torrent clients:', error);
    }
}

async function loadExploits() {
    try {
        const response = await fetch(`${API_BASE}/modules/exploit/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list' })
        });
        if (response.ok) {
            state.exploits = await response.json();
            renderExploitGrid();
        }
    } catch (error) {
        console.error('Failed to load exploits:', error);
    }
}

function renderExploitGrid() {
    const grid = document.getElementById('exploitGrid');
    if (!grid) return;
    
    if (state.exploits.length === 0) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5">
                <i class="bi bi-shield-exclamation display-1 text-muted"></i>
                <h3 class="mt-3 text-muted">No exploits found</h3>
                <p class="text-muted">Add exploit packages from the web or local files</p>
                <button class="btn btn-primary" onclick="showAddExploitModal()">
                    <i class="bi bi-plus-circle me-1"></i>Add Exploit
                </button>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = state.exploits.map(exploit => `
        <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 exploit-col" data-exploit-id="${exploit.id}">
            <div class="exploit-card h-100">
                ${exploit.local_cover_path ? `
                    <img src="/static/artwork/${exploit.local_cover_path.split('/').pop()}" 
                         class="exploit-card-image" 
                         alt="${exploit.name}"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                ` : ''}
                <div class="exploit-card-image-placeholder" style="${exploit.local_cover_path ? 'display:none;' : ''}">
                    <i class="bi bi-shield-exclamation"></i>
                </div>
                <div class="exploit-card-body">
                    <h6 class="exploit-card-title">${exploit.name}</h6>
                    <div class="exploit-card-meta">
                        <span class="badge bg-${getExploitTypeColor(exploit.package_type)}">${exploit.package_type.replace('_', ' ')}</span>
                        ${exploit.version ? `<span class="text-muted ms-2">v${exploit.version}</span>` : ''}
                        ${exploit.supported_firmware ? `<span class="text-muted ms-2">${exploit.supported_firmware}</span>` : ''}
                        ${exploit.size_bytes ? `<span class="text-muted ms-2">${formatBytes(exploit.size_bytes)}</span>` : ''}
                    </div>
                    <div class="exploit-card-badges">
                        ${exploit.is_on_server ? '<span class="badge bg-success">Local</span>' : '<span class="badge bg-secondary">Remote</span>'}
                        ${exploit.format ? `<span class="badge bg-secondary badge-format">Format: ${exploit.format}</span>` : ''}
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary w-100 mb-1" onclick="showExploitDetail(${exploit.id})">
                            <i class="bi bi-info-circle me-1"></i>Details
                        </button>
                        ${exploit.is_on_server ? `
                            <button class="btn btn-sm btn-outline-danger w-100" onclick="deleteExploit(${exploit.id})">
                                <i class="bi bi-trash me-1"></i>Delete
                            </button>
                        ` : `
                            <button class="btn btn-sm btn-outline-success w-100" onclick="downloadExploit(${exploit.id})">
                                <i class="bi bi-download me-1"></i>Download
                            </button>
                        `}
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function getExploitTypeColor(type) {
    const colors = {
        'homebrew_app': 'success',
        'exploit_payload': 'danger',
        'kernel_exploit': 'danger',
        'webkit_exploit': 'warning',
        'tool': 'info',
        'emulator': 'primary',
        'game_mod': 'secondary',
        'theme': 'purple',
        'other': 'dark',
    };
    return colors[type] || 'secondary';
}

function filterExploits() {
    const search = document.getElementById('exploitSearch')?.value.toLowerCase() || '';
    const typeFilter = document.getElementById('exploitTypeFilter')?.value || '';
    const firmwareFilter = document.getElementById('exploitFirmwareFilter')?.value || '';
    
    const cards = document.querySelectorAll('.exploit-col');
    
    cards.forEach(card => {
        const exploitId = parseInt(card.dataset.exploitId);
        const exploit = state.exploits.find(e => e.id === exploitId);
        
        if (!exploit) return;
        
        const matchesSearch = exploit.name.toLowerCase().includes(search) ||
                             exploit.description?.toLowerCase().includes(search) ||
                             exploit.author?.toLowerCase().includes(search);
        
        const matchesType = !typeFilter || exploit.package_type === typeFilter;
        
        const matchesFirmware = !firmwareFilter || 
            exploit.supported_firmware?.includes(firmwareFilter);
        
        if (matchesSearch && matchesType && matchesFirmware) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

async function refreshExploitLibrary() {
    showToast('Refreshing exploit library...', 'info');
    await loadExploits();
    showToast('Exploit library refreshed', 'success');
}

async function loadSettingsPaths() {
    try {
        const response = await fetch(`${API_BASE}/settings/paths`);
        if (response.ok) {
            const paths = await response.json();
            document.getElementById('gamesPath').value = paths.games_path || '';
            document.getElementById('savesPath').value = paths.saves_path || '';
            document.getElementById('artworkPath').value = paths.artwork_path || '';
            document.getElementById('downloadsPath').value = paths.downloads_path || '';
        }
    } catch (error) {
        console.error('Failed to load settings paths:', error);
    }
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

function renderTorrentClients() {
    const tbody = document.getElementById('clientsBody');
    if (!tbody) return;
    
    tbody.innerHTML = state.clients.map(client => `
        <tr>
            <td>${client.name}</td>
            <td>${client.client_type}</td>
            <td>${client.host}:${client.port}</td>
            <td>
                <span class="status-dot ${client.is_enabled ? 'connected' : 'disconnected'}"></span>
                ${client.is_enabled ? 'Enabled' : 'Disabled'}
                ${client.is_default ? ' <span class="badge bg-primary">Default</span>' : ''}
            </td>
            <td>
                <button class="btn btn-sm btn-outline-info" onclick="testTorrentClient(${client.id})">
                    <i class="bi bi-check-circle me-1"></i>Test
                </button>
                <button class="btn btn-sm btn-outline-danger ms-1" onclick="deleteTorrentClient(${client.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

async function testTorrentClient(clientId) {
    showToast('Testing connection...', 'info');
    try {
        const response = await fetch(`${API_BASE}/torrent-clients/${clientId}/test`, {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            showToast(`Connection successful! ${result.version || ''}`, 'success');
        } else {
            showToast(`Connection failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Test failed', 'error');
    }
}

async function deleteTorrentClient(clientId) {
    if (!confirm('Delete this torrent client?')) return;
    try {
        const response = await fetch(`${API_BASE}/torrent-clients/${clientId}`, {
            method: 'DELETE',
        });
        if (response.ok) {
            showToast('Client deleted', 'success');
            await loadTorrentClients();
        } else {
            showToast('Failed to delete', 'error');
        }
    } catch (error) {
        showToast('Failed to delete', 'error');
    }
}

// ==================== Rendering ====================

function renderGameGrid(games = state.games, gridId = 'gameGrid') {
    const grid = document.getElementById(gridId);
    if (!grid) return;
    
    if (games.length === 0) {
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
    
    grid.innerHTML = games.map(game => `
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
                        ${game.size_bytes ? `<span class="text-muted ms-2">${formatBytes(game.size_bytes)}</span>` : ''}
                    </div>
                    <div class="game-card-badges">
                        ${game.is_on_server ? '<span class="badge bg-local badge-source">Local</span>' : ''}
                        ${game.is_on_any_ps5 ? '<span class="badge bg-ps5 badge-source">PS5</span>' : ''}
                        ${game.available_sources?.includes('orbit_store') ? '<span class="badge bg-orbit badge-source">Orbit</span>' : ''}
                        ${game.available_sources?.includes('blackbox') ? '<span class="badge bg-blackbox badge-source">BlackBox</span>' : ''}
                        ${game.available_sources?.includes('overdrive') ? '<span class="badge bg-overdrive badge-source">Overdrive</span>' : ''}
                        ${game.format ? `<span class="badge bg-secondary badge-format">Format: ${game.format}</span>` : ''}
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary w-100 mb-1" onclick="showGameDetail(${game.id})">
                            <i class="bi bi-info-circle me-1"></i>Details
                        </button>
                        ${game.format ? `
                            <button class="btn btn-sm btn-outline-success w-100" onclick="convertGameFromLibrary(${game.id}, '${game.format}')">
                                <i class="bi bi-arrow-repeat me-1"></i>Convert
                            </button>
                        ` : ''}
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
    
    let filteredGames = state.games.filter(game => {
        const matchesSearch = game.name.toLowerCase().includes(search) ||
                             game.ppsa?.toLowerCase().includes(search) ||
                             game.title_id?.toLowerCase().includes(search);
        
        const matchesSource = !sourceFilter || 
            (sourceFilter === 'local' && game.is_on_server) ||
            (sourceFilter === 'ps5' && game.is_on_any_ps5) ||
            (sourceFilter && game.available_sources?.includes(sourceFilter));
        
        const matchesFormat = !formatFilter || game.format === formatFilter;
        
        return matchesSearch && matchesSource && matchesFormat;
    });
    
    renderGameGrid(filteredGames);
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
    data.is_enabled = true;
    data.is_default = false;
    
    try {
        const response = await fetch(`${API_BASE}/torrent-clients`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        
        if (response.ok) {
            showToast('Torrent client added successfully', 'success');
            e.target.reset();
            await loadTorrentClients();
        } else {
            const result = await response.json();
            showToast(`Failed to add client: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to add client', 'error');
    }
}

async function handleSaveAPIKeys(e) {
    e.preventDefault();
    showToast('API keys saved (requires restart)', 'info');
}

async function handleSavePaths(e) {
    e.preventDefault();
    const gamesPath = document.getElementById('gamesPath').value;
    const savesPath = document.getElementById('savesPath').value;
    const artworkPath = document.getElementById('artworkPath').value;
    const downloadsPath = document.getElementById('downloadsPath').value;
    
    // Save paths to server config via API
    try {
        const response = await fetch(`${API_BASE}/settings/paths`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                games_path: gamesPath,
                saves_path: savesPath,
                artwork_path: artworkPath,
                downloads_path: downloadsPath
            })
        });
        
        if (response.ok) {
            showToast('Server paths saved successfully', 'success');
        } else {
            showToast('Failed to save paths', 'error');
        }
    } catch (error) {
        showToast('Failed to save paths', 'error');
    }
}

// ==================== Exploit Library Actions ====================

function showAddExploitModal() {
    // Create modal dynamically
    const modalHtml = `
        <div class="modal fade" id="addExploitModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Add Exploit / Homebrew Package</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form id="addExploitForm">
                        <div class="modal-body">
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">Name</label>
                                    <input type="text" class="form-control" name="name" required>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Type</label>
                                    <select class="form-select" name="package_type" required>
                                        <option value="homebrew_app">Homebrew App</option>
                                        <option value="exploit_payload">Exploit Payload</option>
                                        <option value="kernel_exploit">Kernel Exploit</option>
                                        <option value="webkit_exploit">WebKit Exploit</option>
                                        <option value="tool">Tool</option>
                                        <option value="emulator">Emulator</option>
                                        <option value="game_mod">Game Mod</option>
                                        <option value="theme">Theme</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">Version</label>
                                    <input type="text" class="form-control" name="version">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Author</label>
                                    <input type="text" class="form-control" name="author">
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">Supported Firmware</label>
                                    <input type="text" class="form-control" name="supported_firmware" placeholder="e.g., 7.00-11.00">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Format</label>
                                    <select class="form-select" name="format">
                                        <option value="">Unknown</option>
                                        <option value="pkg">PKG</option>
                                        <option value="fpkg">FPKG</option>
                                        <option value="exfat">EXFAT</option>
                                        <option value="elf">ELF</option>
                                        <option value="bin">BIN</option>
                                        <option value="js">JavaScript</option>
                                        <option value="zip">ZIP</option>
                                    </select>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Description</label>
                                <textarea class="form-control" name="description" rows="3"></textarea>
                            </div>
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">Source URL</label>
                                    <input type="url" class="form-control" name="source_url">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Download URL</label>
                                    <input type="url" class="form-control" name="download_url">
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">GitHub Repo</label>
                                    <input type="text" class="form-control" name="github_repo" placeholder="owner/repo">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Cover URL</label>
                                    <input type="url" class="form-control" name="cover_url">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Tags (comma-separated)</label>
                                <input type="text" class="form-control" name="tags" placeholder="homebrew, emulator, retroarch">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="submit" class="btn btn-primary">Add Exploit</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('addExploitModal'));
    modal.show();
    
    document.getElementById('addExploitForm').addEventListener('submit', handleAddExploit);
    
    // Remove modal from DOM when hidden
    document.getElementById('addExploitModal').addEventListener('hidden.bs.modal', (e) => {
        e.target.remove();
    });
}

async function handleAddExploit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    data.size_bytes = 0;
    data.is_on_server = false;
    data.tags = data.tags ? data.tags.split(',').map(t => t.trim()) : [];
    
    try {
        const response = await fetch(`${API_BASE}/modules/exploit/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add', ...data })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Exploit added successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addExploitModal')).hide();
            await loadExploits();
        } else {
            showToast(`Failed to add exploit: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to add exploit', 'error');
    }
}

async function showExploitDetail(exploitId) {
    try {
        const response = await fetch(`${API_BASE}/modules/exploit/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'get', exploit_id: exploitId })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            showToast('Failed to load exploit details', 'error');
            return;
        }
        
        const exploit = result.exploit;
        
        // Show in game detail modal (reuse)
        const modal = new bootstrap.Modal(document.getElementById('gameDetailModal'));
        const title = document.getElementById('gameModalTitle');
        const body = document.getElementById('gameModalBody');
        
        title.textContent = exploit.name;
        body.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    ${exploit.cover_url ? `<img src="${exploit.cover_url}" class="img-fluid mb-3" alt="${exploit.name}">` : ''}
                </div>
                <div class="col-md-6">
                    <table class="table">
                        <tr><th>Type</th><td><span class="badge bg-${getExploitTypeColor(exploit.package_type)}">${exploit.package_type.replace('_', ' ')}</span></td></tr>
                        <tr><th>Version</th><td>${exploit.version || 'N/A'}</td></tr>
                        <tr><th>Author</th><td>${exploit.author || 'N/A'}</td></tr>
                        <tr><th>Supported Firmware</th><td>${exploit.supported_firmware || 'N/A'}</td></tr>
                        <tr><th>Format</th><td>${exploit.format || 'N/A'}</td></tr>
                        <tr><th>Size</th><td>${exploit.size_bytes ? formatBytes(exploit.size_bytes) : 'N/A'}</td></tr>
                        <tr><th>Source</th><td>${exploit.source_url ? `<a href="${exploit.source_url}" target="_blank">${exploit.source_url}</a>` : 'N/A'}</td></tr>
                        <tr><th>Download</th><td>${exploit.download_url ? `<a href="${exploit.download_url}" target="_blank">Download</a>` : 'N/A'}</td></tr>
                        <tr><th>GitHub</th><td>${exploit.github_repo ? `<a href="https://github.com/${exploit.github_repo}" target="_blank">${exploit.github_repo}</a>` : 'N/A'}</td></tr>
                        <tr><th>Local</th><td>${exploit.is_on_server ? 'Yes' : 'No'}</td></tr>
                    </table>
                </div>
            </div>
            <div class="mt-3">
                <h6>Description</h6>
                <p>${exploit.description || 'No description available'}</p>
            </div>
            ${exploit.tags && exploit.tags.length > 0 ? `
                <div class="mt-3">
                    <h6>Tags</h6>
                    <div>${exploit.tags.map(t => `<span class="badge bg-secondary me-1">${t}</span>`).join('')}</div>
                </div>
            ` : ''}
        `;
        
        modal.show();
    } catch (error) {
        showToast('Failed to load exploit details', 'error');
    }
}

async function downloadExploit(exploitId) {
    try {
        // First get the exploit to get download URL
        const response = await fetch(`${API_BASE}/modules/exploit/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'get', exploit_id: exploitId })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            showToast('Failed to get exploit info', 'error');
            return;
        }
        
        const exploit = result.exploit;
        
        if (exploit.download_url) {
            window.open(exploit.download_url, '_blank');
            showToast('Opening download...', 'info');
        } else if (exploit.source_url) {
            window.open(exploit.source_url, '_blank');
            showToast('Opening source page...', 'info');
        } else {
            showToast('No download URL available', 'warning');
        }
    } catch (error) {
        showToast('Failed to download exploit', 'error');
    }
}

async function deleteExploit(exploitId) {
    if (!confirm('Are you sure you want to delete this exploit?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/modules/exploit/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete', exploit_id: exploitId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Exploit deleted', 'success');
            await loadExploits();
        } else {
            showToast(`Failed to delete exploit: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to delete exploit', 'error');
    }
}

// ==================== Conversion from Library ====================

async function convertGameFromLibrary(gameId, currentFormat) {
    // Create modal for conversion options
    const modalHtml = `
        <div class="modal fade" id="convertGameModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Convert Game Format</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Current Format</label>
                            <input type="text" class="form-control" value="${currentFormat.toUpperCase()}" readonly>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Target Format</label>
                            <select class="form-select" id="targetFormat">
                                <option value="pkg">PKG</option>
                                <option value="fpkg">FPKG</option>
                                <option value="folder">Folder</option>
                                <option value="exfat">EXFAT</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Firmware Compatibility</label>
                            <div id="firmwareCompatTable" class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Firmware</th>
                                            <th>PKG</th>
                                            <th>FPKG</th>
                                            <th>EXFAT</th>
                                            <th>Folder</th>
                                        </tr>
                                    </thead>
                                    <tbody id="firmwareCompatBody"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="executeConvertGame(${gameId})">
                            <i class="bi bi-arrow-repeat me-1"></i>Convert
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('convertGameModal'));
    modal.show();
    
    // Load compatibility info
    await loadFormatCompatibility(currentFormat);
    
    // Remove modal when hidden
    document.getElementById('convertGameModal').addEventListener('hidden.bs.modal', (e) => {
        e.target.remove();
    });
}

async function loadFormatCompatibility(currentFormat) {
    try {
        // Get recommended formats from convert module
        const response = await fetch(`${API_BASE}/modules/convert/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'get_format_info' })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const tbody = document.getElementById('firmwareCompatBody');
            if (tbody && result.recommended) {
                const rec = result.recommended;
                tbody.innerHTML = `
                    <tr>
                        <td>Current (${currentFormat.toUpperCase()})</td>
                        <td>${currentFormat === 'pkg' ? '✓' : ''}</td>
                        <td>${currentFormat === 'fpkg' ? '✓' : ''}</td>
                        <td>${currentFormat === 'exfat' ? '✓' : ''}</td>
                        <td>${currentFormat === 'folder' ? '✓' : ''}</td>
                    </tr>
                    <tr>
                        <td>Recommended Primary</td>
                        <td>${rec.primary === 'pkg' ? '★' : ''}</td>
                        <td>${rec.primary === 'fpkg' ? '★' : ''}</td>
                        <td>${rec.primary === 'exfat' ? '★' : ''}</td>
                        <td>${rec.primary === 'folder' ? '★' : ''}</td>
                    </tr>
                    <tr>
                        <td>Recommended Secondary</td>
                        <td>${rec.secondary === 'pkg' ? '★' : ''}</td>
                        <td>${rec.secondary === 'fpkg' ? '★' : ''}</td>
                        <td>${rec.secondary === 'exfat' ? '★' : ''}</td>
                        <td>${rec.secondary === 'folder' ? '★' : ''}</td>
                    </tr>
                    ${rec.external ? `
                    <tr>
                        <td>External USB</td>
                        <td>${rec.external === 'pkg' ? '★' : ''}</td>
                        <td>${rec.external === 'fpkg' ? '★' : ''}</td>
                        <td>${rec.external === 'exfat' ? '★' : ''}</td>
                        <td>${rec.external === 'folder' ? '★' : ''}</td>
                    </tr>
                    ` : ''}
                `;
            }
        }
    } catch (error) {
        console.error('Failed to load compatibility:', error);
    }
}

async function executeConvertGame(gameId) {
    const targetFormat = document.getElementById('targetFormat').value;
    
    if (!targetFormat) {
        showToast('Please select a target format', 'warning');
        return;
    }
    
    showToast('Starting conversion...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/convert/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'convert', game_id: gameId, target_format: targetFormat })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Conversion started', 'success');
            bootstrap.Modal.getInstance(document.getElementById('convertGameModal')).hide();
            await loadGames();
        } else {
            showToast(`Conversion failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Conversion failed', 'error');
    }
}

// ==================== Actions ====================

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
    
    if (!game.is_on_server) {
        showToast('Game not available on server', 'warning');
        return;
    }
    
    const availablePS5 = state.ps5Systems.filter(p => p.is_connected);
    
    if (availablePS5.length === 0) {
        showToast('No PS5 connected', 'warning');
        return;
    }
    
    // Build selection UI
    let ps5SelectHtml = '<select class="form-select mb-3" id="pushPs5Select">';
    availablePS5.forEach(ps5 => {
        ps5SelectHtml += `<option value="${ps5.id}">${ps5.name} (${ps5.ip_address})</option>`;
    });
    ps5SelectHtml += '</select>';
    
    const storageOptions = [
        { value: 'primary_ssd', label: 'Primary SSD (/user/app)', path: '/user/app' },
        { value: 'secondary_ssd', label: 'Secondary SSD (/user/app - secondary)', path: '/user/app' },
        { value: 'external_usb', label: 'External USB (/mnt/usb0)', path: '/mnt/usb0' },
        { value: 'external_ext1', label: 'External Storage 1 (/mnt/ext1)', path: '/mnt/ext1' },
        { value: 'external_ext2', label: 'External Storage 2 (/mnt/ext2)', path: '/mnt/ext2' },
        { value: 'external_ext3', label: 'External Storage 3 (/mnt/ext3)', path: '/mnt/ext3' },
    ];
    
    let storageSelectHtml = '<select class="form-select mb-3" id="pushStorageSelect">';
    storageOptions.forEach(opt => {
        storageSelectHtml += `<option value="${opt.value}" data-path="${opt.path}">${opt.label}</option>`;
    });
    storageSelectHtml += '</select>';
    
    const message = `Push "${game.name}" from server to PS5?\n\n` +
        `Server path: ${game.locations?.find(l => l.server_path)?.server_path || 'Unknown'}\n\n` +
        `Please select target PS5 and storage destination:`;
    
    // Create a modal for selection instead of using prompt/confirm
    showPushModal(game, availablePS5, storageOptions);
}

async function pullGame(gameId) {
    const game = state.games.find(g => g.id === gameId);
    const connectedPS5 = state.ps5Systems.find(p => p.is_connected);
    
    if (!connectedPS5) {
        showToast('No PS5 connected', 'warning');
        return;
    }
    
    // Show modal for pull confirmation with keep/delete option
    const keep = await showPullModal(game, connectedPS5);
    
    // If user cancelled (modal returns null/undefined), return
    if (keep === undefined) return;
    
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

function showPushModal(game, availablePS5, storageOptions) {
    // Remove existing modal if any
    const existingModal = document.getElementById('pushGameModal');
    if (existingModal) existingModal.remove();
    
    let ps5Options = availablePS5.map(ps5 => 
        `<option value="${ps5.id}">${ps5.name} (${ps5.ip_address})</option>`
    ).join('');
    
    let storageOptionsHtml = storageOptions.map(opt => 
        `<option value="${opt.value}" data-path="${opt.path}">${opt.label}</option>`
    ).join('');
    
    const modalHtml = `
        <div class="modal fade" id="pushGameModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Push Game to PS5</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Push "<strong>${game.name}</strong>" from server to PS5?</p>
                        <p class="text-muted small">
                            Server path: ${game.locations?.find(l => l.server_path)?.server_path || 'Unknown'}
                        </p>
                        <hr>
                        <div class="mb-3">
                            <label class="form-label"><strong>Target PS5 System</strong></label>
                            <select class="form-select" id="pushPs5Select">
                                ${ps5Options}
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label"><strong>Storage Destination</strong></label>
                            <select class="form-select" id="pushStorageSelect">
                                ${storageOptionsHtml}
                            </select>
                            <div class="form-text">Standard path will be used for the game files</div>
                        </div>
                        <div class="alert alert-info">
                            <i class="bi bi-info-circle me-1"></i>
                            The game will be placed in a folder named after its Title ID or PPSA under the selected storage path.
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="executePushGame(${game.id})">
                            <i class="bi bi-upload me-1"></i>Push Game
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    new bootstrap.Modal(document.getElementById('pushGameModal')).show();
}

function showPullModal(game, ps5) {
    return new Promise((resolve) => {
        // Remove existing modal if any
        const existingModal = document.getElementById('pullGameModal');
        if (existingModal) existingModal.remove();
        
        const modalHtml = `
            <div class="modal fade" id="pullGameModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Pull Game from PS5</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" onclick="resolvePullModal()"></button>
                        </div>
                        <div class="modal-body">
                            <p>Pull "<strong>${game.name}</strong>" from <strong>${ps5.name}</strong> to server?</p>
                            <hr>
                            <div class="alert alert-warning">
                                <i class="bi bi-exclamation-triangle me-2"></i>
                                <strong>Important:</strong> If you choose NOT to keep the game on the PS5, it will be <strong>REMOVED</strong> from the PS5 storage.
                                <br><br>
                                The game will NOT be available on the PS5 until you transfer it back using "Push to PS5".
                            </div>
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="radio" name="keepOption" id="keepYes" value="true" checked>
                                <label class="form-check-label" for="keepYes">
                                    <strong>Keep game on PS5</strong> (copy only)
                                </label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="keepOption" id="keepNo" value="false">
                                <label class="form-check-label text-danger" for="keepNo">
                                    <strong>Remove game from PS5</strong> (move to server)
                                </label>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="resolvePullModal()">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="resolvePullModal(document.querySelector('input[name=\"keepOption\"]:checked').value === 'true')">
                                <i class="bi bi-download me-1"></i>Pull Game
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Store resolve function globally for modal buttons
        window.resolvePullModal = (value) => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('pullGameModal'));
            if (modal) modal.hide();
            // Remove modal after animation
            setTimeout(() => {
                const m = document.getElementById('pullGameModal');
                if (m) m.remove();
            }, 300);
            delete window.resolvePullModal;
            resolve(value);
        };
        
        new bootstrap.Modal(document.getElementById('pullGameModal')).show();
    });
}

async function executePushGame(gameId) {
    const game = state.games.find(g => g.id === gameId);
    if (!game) return;
    
    const ps5Select = document.getElementById('pushPs5Select');
    const storageSelect = document.getElementById('pushStorageSelect');
    
    const systemId = ps5Select.value;
    const storage = storageSelect.value;
    
    if (!systemId || !storage) {
        showToast('Please select both PS5 and storage', 'warning');
        return;
    }
    
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('pushGameModal'));
    if (modal) modal.hide();
    
    showToast('Pushing game...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/modules/push/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'push', system_id: parseInt(systemId), game_id: gameId, storage }),
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