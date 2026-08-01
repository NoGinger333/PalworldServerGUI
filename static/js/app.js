/**
 * PalServer Manager - フロントエンド JavaScript
 * パルワールド専用サーバー管理GUIのクライアントサイドロジック
 */
class PalServerManager {
    constructor() {
        this.socket = null;
        this.isAuthenticated = false;
        this.currentPage = 'dashboard';
        this.statusInterval = null;
        this.playerInterval = null;
        this.commandHistory = [];
        this.commandHistoryIndex = -1;
        this.autoScroll = true;
        this.currentSettings = {};
        this.settingsMetadata = [];
    }

    init() {
        this.bindEvents();
        this.checkAuth();
    }

    // ==========================================
    // イベントバインド
    // ==========================================
    bindEvents() {
        // ログイン
        document.getElementById('login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.login(document.getElementById('login-password').value);
        });

        document.getElementById('logout-btn').addEventListener('click', () => this.logout());

        // ナビゲーション
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                e.target.classList.add('active');
                this.showPage(e.target.dataset.target);
            });
        });

        // ダッシュボード操作
        document.getElementById('btn-start').addEventListener('click', () => this.startServer());
        document.getElementById('btn-stop').addEventListener('click', () => this.stopServer());
        document.getElementById('btn-restart').addEventListener('click', () => this.restartServer());
        document.getElementById('btn-update').addEventListener('click', () => this.updateServer());
        document.getElementById('btn-quick-save').addEventListener('click', () => this.saveWorld());

        // SteamCMDインストール
        document.getElementById('btn-install-steamcmd').addEventListener('click', () => this.installSteamCMD());
        document.getElementById('btn-install-server').addEventListener('click', () => this.installServer());

        // ブロードキャスト
        document.getElementById('btn-broadcast').addEventListener('click', () => {
            const input = document.getElementById('broadcast-input');
            if (input.value.trim()) {
                this.sendBroadcast(input.value);
                input.value = '';
            }
        });

        // コンソール
        document.getElementById('console-autoscroll').addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
        });
        document.getElementById('btn-console-clear').addEventListener('click', () => {
            document.getElementById('console-output').innerHTML = '';
        });

        const consoleInput = document.getElementById('console-input');
        consoleInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                if (consoleInput.value.trim()) {
                    this.sendRconCommand(consoleInput.value);
                    consoleInput.value = '';
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (this.commandHistory.length > 0 && this.commandHistoryIndex < this.commandHistory.length - 1) {
                    this.commandHistoryIndex++;
                    consoleInput.value = this.commandHistory[this.commandHistory.length - 1 - this.commandHistoryIndex];
                }
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (this.commandHistoryIndex > 0) {
                    this.commandHistoryIndex--;
                    consoleInput.value = this.commandHistory[this.commandHistory.length - 1 - this.commandHistoryIndex];
                } else if (this.commandHistoryIndex === 0) {
                    this.commandHistoryIndex = -1;
                    consoleInput.value = '';
                }
            }
        });
        document.getElementById('btn-console-send').addEventListener('click', () => {
            if (consoleInput.value.trim()) {
                this.sendRconCommand(consoleInput.value);
                consoleInput.value = '';
            }
        });

        // サーバー設定
        document.getElementById('btn-settings-save').addEventListener('click', () => this.saveSettings());
        document.getElementById('btn-settings-default').addEventListener('click', () => this.resetSettings());

        // プレイヤー
        document.getElementById('btn-players-refresh').addEventListener('click', () => this.refreshPlayers());

        // バックアップ
        document.getElementById('btn-backup-create').addEventListener('click', () => this.createBackup());

        // マネージャー設定
        document.getElementById('btn-manager-save').addEventListener('click', () => this.saveManagerConfig());

        // モーダル
        document.getElementById('modal-btn-cancel').addEventListener('click', () => {
            document.getElementById('confirm-modal').classList.remove('active');
        });
    }

    // ==========================================
    // API通信
    // ==========================================
    async apiCall(endpoint, method = 'GET', body = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin' // セッションCookieを送信
        };
        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`/api${endpoint}`, options);

            if (response.status === 401) {
                this.showLoginView();
                throw new Error('認証エラー: 再ログインしてください');
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || data.error || 'API Error');
            }

            return data;
        } catch (error) {
            if (error.message !== '認証エラー: 再ログインしてください') {
                console.error('API Error:', error);
            }
            throw error;
        }
    }

    // ==========================================
    // 認証
    // ==========================================
    async login(password) {
        try {
            const res = await this.apiCall('/login', 'POST', { password });
            if (res.success) {
                this.isAuthenticated = true;
                this.showToast('ログイン成功！', 'success');
                this.showAppView();
                this.onLoginSuccess();
            }
        } catch (e) {
            this.showToast('パスワードが正しくありません', 'error');
        }
    }

    async logout() {
        try {
            await this.apiCall('/logout', 'POST');
        } catch (e) { /* ignore */ }
        this.isAuthenticated = false;
        this.stopPolling();
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.showLoginView();
    }

    async checkAuth() {
        try {
            // ステータスAPIを叩いて認証確認
            await this.apiCall('/status');
            this.isAuthenticated = true;
            this.showAppView();
            this.onLoginSuccess();
        } catch (e) {
            this.showLoginView();
        }
    }

    showLoginView() {
        document.getElementById('login-view').classList.add('active');
        document.getElementById('app-view').classList.remove('active');
    }

    showAppView() {
        document.getElementById('login-view').classList.remove('active');
        document.getElementById('app-view').classList.add('active');
    }

    onLoginSuccess() {
        this.refreshStatus();
        this.startPolling();
        this.initWebSocket();
        this.loadInitialLogs();
    }

    // ==========================================
    // ナビゲーション
    // ==========================================
    showPage(page) {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(`page-${page}`);
        if (target) {
            target.classList.add('active');
        }
        this.currentPage = page;

        // ページ固有の初期化
        if (page === 'settings') this.loadSettings();
        if (page === 'players') this.refreshPlayers();
        if (page === 'backups') this.refreshBackups();
        if (page === 'manager-settings') this.loadManagerConfig();
    }

    // ==========================================
    // ポーリング
    // ==========================================
    startPolling() {
        this.stopPolling();
        this.statusInterval = setInterval(() => this.refreshStatus(), 5000);
        this.playerInterval = setInterval(() => {
            if (this.currentPage === 'players') this.refreshPlayers();
        }, 30000);
    }

    stopPolling() {
        if (this.statusInterval) clearInterval(this.statusInterval);
        if (this.playerInterval) clearInterval(this.playerInterval);
    }

    // ==========================================
    // ダッシュボード
    // ==========================================
    async refreshStatus() {
        try {
            const data = await this.apiCall('/status');
            this.updateDashboardUI(data);
        } catch (e) { /* ignore */ }
    }

    updateDashboardUI(data) {
        // サイドバーステータスバッジ
        const badge = document.getElementById('sidebar-status-badge');
        badge.className = `status-badge status-${data.status}`;
        badge.querySelector('.status-text').textContent =
            data.status.charAt(0).toUpperCase() + data.status.slice(1);

        // ダッシュボードの詳細ステータス
        const statusEl = document.getElementById('dash-status');
        statusEl.textContent = data.status.toUpperCase();
        const statusColorClass = data.status === 'running' ? 'success' :
            (data.status === 'stopped' ? 'danger' : 'warning');
        statusEl.className = `stat-value text-${statusColorClass}`;

        // 稼働時間
        document.getElementById('dash-uptime').textContent = this.formatUptime(data.uptime || 0);

        // プレイヤー数
        const maxPlayers = data.max_players || 32;
        document.getElementById('dash-players').textContent = `${data.player_count || 0} / ${maxPlayers}`;

        // CPU使用率
        const cpuVal = data.cpu_percent || 0;
        document.getElementById('cpu-bar').style.width = `${Math.min(cpuVal, 100)}%`;
        document.getElementById('cpu-val').textContent = `${cpuVal.toFixed(1)}%`;

        // メモリ使用量
        const memMb = data.memory_mb || 0;
        const memPct = Math.min((memMb / 16384) * 100, 100); // 16GB想定
        document.getElementById('mem-bar').style.width = `${memPct}%`;
        document.getElementById('mem-val').textContent = `${memMb.toFixed(0)} MB`;

        // サーバーコントロールボタンの有効/無効
        const isRunning = data.status === 'running';
        const isStopped = data.status === 'stopped';
        document.getElementById('btn-start').disabled = !isStopped;
        document.getElementById('btn-stop').disabled = !isRunning;
        document.getElementById('btn-restart').disabled = !isRunning;
        document.getElementById('btn-update').disabled = !isStopped;

        // SteamCMD/サーバーインストール状態
        if (data.steamcmd_installed !== undefined) {
            const scStatus = document.getElementById('steamcmd-status');
            scStatus.textContent = data.steamcmd_installed ? 'Installed ✓' : 'Not Installed';
            scStatus.className = `badge bg-${data.steamcmd_installed ? 'success' : 'warning'}`;

            const svStatus = document.getElementById('server-status');
            svStatus.textContent = data.server_installed ? 'Installed ✓' : 'Not Installed';
            svStatus.className = `badge bg-${data.server_installed ? 'success' : 'warning'}`;

            document.getElementById('btn-install-steamcmd').style.display =
                data.steamcmd_installed ? 'none' : 'inline-flex';
            document.getElementById('btn-install-server').disabled = !data.steamcmd_installed;
            document.getElementById('btn-install-server').style.display =
                data.server_installed ? 'none' : 'inline-flex';
        }
    }

    async startServer() {
        try {
            this.showToast('サーバーを起動しています...', 'info');
            await this.apiCall('/server/start', 'POST');
            setTimeout(() => this.refreshStatus(), 2000);
        } catch (e) {
            this.showToast('サーバー起動に失敗しました', 'error');
        }
    }

    async stopServer() {
        this.showConfirm('サーバーを停止しますか？セーブ後にシャットダウンします。', async () => {
            try {
                this.showToast('サーバーを停止しています...', 'info');
                await this.apiCall('/server/stop', 'POST');
                setTimeout(() => this.refreshStatus(), 3000);
            } catch (e) {
                this.showToast('サーバー停止に失敗しました', 'error');
            }
        });
    }

    async restartServer() {
        this.showConfirm('サーバーを再起動しますか？', async () => {
            try {
                this.showToast('サーバーを再起動しています...', 'info');
                await this.apiCall('/server/restart', 'POST', { update: false });
                setTimeout(() => this.refreshStatus(), 5000);
            } catch (e) {
                this.showToast('サーバー再起動に失敗しました', 'error');
            }
        });
    }

    async updateServer() {
        this.showConfirm('サーバーをアップデートしますか？（サーバーが停止中の場合のみ）', async () => {
            try {
                this.showToast('アップデートを開始しています...', 'info');
                await this.apiCall('/server/update', 'POST');
                this.showToast('アップデートを開始しました。コンソールで進捗を確認してください。', 'success');
            } catch (e) {
                this.showToast(e.message || 'アップデートに失敗しました', 'error');
            }
        });
    }

    async saveWorld() {
        try {
            this.showToast('ワールドをセーブしています...', 'info');
            await this.apiCall('/server/save', 'POST');
            this.showToast('ワールドをセーブしました', 'success');
        } catch (e) {
            this.showToast('セーブに失敗しました', 'error');
        }
    }

    async sendBroadcast(message) {
        try {
            await this.apiCall('/broadcast', 'POST', { message });
            this.showToast('メッセージを送信しました', 'success');
        } catch (e) {
            this.showToast('メッセージ送信に失敗しました', 'error');
        }
    }

    async installSteamCMD() {
        try {
            this.showToast('SteamCMDをインストールしています...', 'info');
            await this.apiCall('/steamcmd/install', 'POST');
            this.showToast('SteamCMDインストールを開始しました。コンソールで進捗を確認してください。', 'success');
        } catch (e) {
            this.showToast('SteamCMDインストールに失敗しました', 'error');
        }
    }

    async installServer() {
        try {
            this.showToast('パルワールドサーバーをインストールしています...', 'info');
            await this.apiCall('/steamcmd/install-server', 'POST');
            this.showToast('サーバーインストールを開始しました。コンソールで進捗を確認してください。', 'success');
        } catch (e) {
            this.showToast('サーバーインストールに失敗しました', 'error');
        }
    }

    // ==========================================
    // サーバー設定
    // ==========================================
    async loadSettings() {
        try {
            const data = await this.apiCall('/settings');
            this.currentSettings = data.settings || {};
            this.settingsMetadata = data.metadata || [];
            this.renderSettingsForm();
        } catch (e) {
            this.showToast('設定の読み込みに失敗しました', 'error');
        }
    }

    renderSettingsForm() {
        const tabsContainer = document.getElementById('settings-tabs');
        const contentContainer = document.getElementById('settings-content');

        tabsContainer.innerHTML = '';
        contentContainer.innerHTML = '';

        // メタデータをカテゴリ別にグループ化
        const categories = {};
        const categoryLabels = {
            server: '🖥️ サーバー',
            rates: '📊 レート',
            gameplay: '🎮 ゲームプレイ',
            environment: '🌍 環境',
            advanced: '⚙️ 詳細'
        };

        for (const item of this.settingsMetadata) {
            const cat = item.category || 'advanced';
            if (!categories[cat]) categories[cat] = [];
            categories[cat].push(item);
        }

        let first = true;
        for (const [category, items] of Object.entries(categories)) {
            // タブボタン
            const btn = document.createElement('button');
            btn.className = `tab-btn ${first ? 'active' : ''}`;
            btn.textContent = categoryLabels[category] || category;
            btn.onclick = () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.settings-group').forEach(g => g.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(`group-${category}`).classList.add('active');
            };
            tabsContainer.appendChild(btn);

            // 設定グループ
            const group = document.createElement('div');
            group.id = `group-${category}`;
            group.className = `settings-group ${first ? 'active' : ''}`;

            items.forEach(item => {
                const val = this.currentSettings[item.key] !== undefined ?
                    this.currentSettings[item.key] : (item.default || '');
                const div = document.createElement('div');
                div.className = 'setting-item';

                let inputHtml = '';

                if (item.type === 'bool') {
                    const checked = (val === true || val === 'True' || val === 'true') ? 'checked' : '';
                    inputHtml = `
                        <label class="toggle-switch-wrapper">
                            <label class="toggle-switch">
                                <input type="checkbox" id="set-${item.key}" ${checked}>
                                <span class="slider"></span>
                            </label>
                            <span class="label-text">${item.label}</span>
                        </label>
                    `;
                } else if (item.type === 'enum' && item.options) {
                    const opts = item.options.map(o =>
                        `<option value="${o}" ${String(val) === String(o) ? 'selected' : ''}>${o}</option>`
                    ).join('');
                    inputHtml = `<label>${item.label}</label><select id="set-${item.key}">${opts}</select>`;
                } else if (item.type === 'float' || item.type === 'int') {
                    const step = item.type === 'float' ? '0.01' : '1';
                    const min = item.min !== null && item.min !== undefined ? `min="${item.min}"` : '';
                    const max = item.max !== null && item.max !== undefined ? `max="${item.max}"` : '';
                    inputHtml = `
                        <label>${item.label}</label>
                        <div class="setting-input-wrap">
                            <input type="number" id="set-${item.key}" value="${val}" ${min} ${max} step="${step}">
                            ${item.min !== null && item.max !== null ?
                                `<input type="range" id="range-${item.key}" value="${val}" ${min} ${max} step="${step}"
                                    oninput="document.getElementById('set-${item.key}').value = this.value">` : ''}
                        </div>
                    `;
                } else {
                    inputHtml = `<label>${item.label}</label>
                        <input type="text" id="set-${item.key}" value="${this.escapeHtml(String(val))}">`;
                }

                div.innerHTML = inputHtml +
                    `<div class="setting-desc">${item.description || ''}</div>`;
                group.appendChild(div);
            });

            contentContainer.appendChild(group);
            first = false;
        }

        // 数値入力とスライダーの連動
        contentContainer.querySelectorAll('input[type="number"]').forEach(numInput => {
            const rangeId = numInput.id.replace('set-', 'range-');
            const rangeInput = document.getElementById(rangeId);
            if (rangeInput) {
                numInput.addEventListener('input', () => {
                    rangeInput.value = numInput.value;
                });
            }
        });
    }

    async saveSettings() {
        const newSettings = {};

        for (const item of this.settingsMetadata) {
            const el = document.getElementById(`set-${item.key}`);
            if (!el) continue;

            if (item.type === 'bool') {
                newSettings[item.key] = el.checked ? 'True' : 'False';
            } else if (item.type === 'int') {
                newSettings[item.key] = parseInt(el.value) || 0;
            } else if (item.type === 'float') {
                newSettings[item.key] = parseFloat(el.value) || 0.0;
            } else {
                newSettings[item.key] = el.value;
            }
        }

        try {
            await this.apiCall('/settings', 'POST', newSettings);
            this.showToast('サーバー設定を保存しました', 'success');
            this.currentSettings = newSettings;
        } catch (e) {
            this.showToast('設定の保存に失敗しました', 'error');
        }
    }

    async resetSettings() {
        this.showConfirm('全ての設定をデフォルトに戻しますか？', async () => {
            // メタデータからデフォルト値を取得して設定
            for (const item of this.settingsMetadata) {
                const el = document.getElementById(`set-${item.key}`);
                if (!el) continue;

                if (item.type === 'bool') {
                    el.checked = (item.default === true || item.default === 'True');
                } else {
                    el.value = item.default !== undefined ? item.default : '';
                    const rangeEl = document.getElementById(`range-${item.key}`);
                    if (rangeEl) rangeEl.value = el.value;
                }
            }
            this.showToast('デフォルト値に戻しました。保存ボタンで確定してください。', 'info');
        });
    }

    // ==========================================
    // コンソール
    // ==========================================
    initWebSocket() {
        if (!window.io) return;
        if (this.socket) {
            this.socket.disconnect();
        }

        this.socket = io('/console', {
            transports: ['websocket', 'polling']
        });

        this.socket.on('connect', () => {
            this.appendLog('コンソールに接続しました。', 'info');
        });

        this.socket.on('log', (data) => {
            this.appendLog(data.data || data.message || '', 'info');
        });

        this.socket.on('status_update', (data) => {
            this.updateDashboardUI(data);
        });

        this.socket.on('disconnect', () => {
            this.appendLog('コンソール接続が切断されました。', 'warning');
        });
    }

    async loadInitialLogs() {
        try {
            const logs = await this.apiCall('/logs');
            if (Array.isArray(logs)) {
                logs.forEach(line => this.appendLog(line, 'info'));
            }
        } catch (e) { /* ignore */ }
    }

    appendLog(msg, level = 'info') {
        const out = document.getElementById('console-output');
        const time = new Date().toLocaleTimeString();
        const div = document.createElement('div');

        // ログレベル自動検出
        if (msg.toLowerCase().includes('error') || msg.toLowerCase().includes('エラー')) {
            level = 'error';
        } else if (msg.toLowerCase().includes('warning') || msg.toLowerCase().includes('warn') || msg.toLowerCase().includes('警告')) {
            level = 'warning';
        }

        div.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-${level}">${this.escapeHtml(msg)}</span>`;
        out.appendChild(div);

        if (this.autoScroll) {
            out.scrollTop = out.scrollHeight;
        }

        // 最大1000行
        while (out.children.length > 1000) {
            out.removeChild(out.firstChild);
        }
    }

    async sendRconCommand(cmd) {
        if (!cmd.trim()) return;
        this.commandHistory.push(cmd);
        this.commandHistoryIndex = -1;
        this.appendLog(`> ${cmd}`, 'info');

        try {
            const res = await this.apiCall('/rcon', 'POST', { command: cmd });
            if (res.response) {
                this.appendLog(res.response, 'info');
            }
        } catch (e) {
            this.appendLog(`エラー: ${e.message}`, 'error');
        }
    }

    // ==========================================
    // プレイヤー管理
    // ==========================================
    async refreshPlayers() {
        try {
            const players = await this.apiCall('/players');
            this.renderPlayersTable(players);
        } catch (e) { /* ignore */ }
    }

    renderPlayersTable(players) {
        const tbody = document.querySelector('#players-table tbody');
        const emptyState = document.getElementById('players-empty');

        if (!players || players.length === 0) {
            tbody.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';
        tbody.innerHTML = players.map(p => `
            <tr>
                <td>${this.escapeHtml(p.name)}</td>
                <td><code>${this.escapeHtml(p.playeruid)}</code></td>
                <td><code>${this.escapeHtml(p.steamid)}</code></td>
                <td>
                    <button class="btn btn-warning btn-sm" onclick="app.kickPlayer('${this.escapeHtml(p.steamid)}', '${this.escapeHtml(p.name)}')">
                        Kick
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="app.banPlayer('${this.escapeHtml(p.steamid)}', '${this.escapeHtml(p.name)}')">
                        BAN
                    </button>
                </td>
            </tr>
        `).join('');
    }

    async kickPlayer(steamId, name) {
        this.showConfirm(`${name} をキックしますか？`, async () => {
            try {
                await this.apiCall('/players/kick', 'POST', { steam_id: steamId });
                this.showToast(`${name} をキックしました`, 'success');
                setTimeout(() => this.refreshPlayers(), 2000);
            } catch (e) {
                this.showToast('キックに失敗しました', 'error');
            }
        });
    }

    async banPlayer(steamId, name) {
        this.showConfirm(`${name} をBANしますか？この操作は元に戻せません。`, async () => {
            try {
                await this.apiCall('/players/ban', 'POST', { steam_id: steamId });
                this.showToast(`${name} をBANしました`, 'success');
                setTimeout(() => this.refreshPlayers(), 2000);
            } catch (e) {
                this.showToast('BANに失敗しました', 'error');
            }
        });
    }

    // ==========================================
    // バックアップ管理
    // ==========================================
    async refreshBackups() {
        try {
            const backups = await this.apiCall('/backups');
            this.renderBackupsTable(backups);
        } catch (e) { /* ignore */ }
    }

    renderBackupsTable(backups) {
        const tbody = document.querySelector('#backups-table tbody');

        if (!backups || backups.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">バックアップがありません</td></tr>';
            return;
        }

        tbody.innerHTML = backups.map(b => `
            <tr>
                <td>${this.escapeHtml(b.filename)}</td>
                <td>${this.formatBytes(b.size / (1024 * 1024))}</td>
                <td>${this.formatDate(b.created_at)}</td>
                <td>
                    <button class="btn btn-primary btn-sm" onclick="app.restoreBackup('${this.escapeHtml(b.filename)}')">
                        復元
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="app.deleteBackup('${this.escapeHtml(b.filename)}')">
                        削除
                    </button>
                </td>
            </tr>
        `).join('');
    }

    async createBackup() {
        try {
            this.showToast('バックアップを作成しています...', 'info');
            const res = await this.apiCall('/backups/create', 'POST');
            this.showToast('バックアップを作成しました', 'success');
            this.refreshBackups();
        } catch (e) {
            this.showToast('バックアップ作成に失敗しました', 'error');
        }
    }

    async restoreBackup(filename) {
        this.showConfirm(`${filename} からワールドを復元しますか？\n※サーバーが停止中である必要があります。`, async () => {
            try {
                await this.apiCall('/backups/restore', 'POST', { filename });
                this.showToast('バックアップから復元しました', 'success');
            } catch (e) {
                this.showToast(e.message || '復元に失敗しました', 'error');
            }
        });
    }

    async deleteBackup(filename) {
        this.showConfirm(`${filename} を削除しますか？`, async () => {
            try {
                await this.apiCall(`/backups/${encodeURIComponent(filename)}`, 'DELETE');
                this.showToast('バックアップを削除しました', 'success');
                this.refreshBackups();
            } catch (e) {
                this.showToast('削除に失敗しました', 'error');
            }
        });
    }

    // ==========================================
    // マネージャー設定
    // ==========================================
    async loadManagerConfig() {
        try {
            const config = await this.apiCall('/manager-config');
            this.renderManagerConfigForm(config);
        } catch (e) {
            this.showToast('マネージャー設定の読み込みに失敗しました', 'error');
        }
    }

    renderManagerConfigForm(config) {
        const form = document.getElementById('manager-config-form');

        const fields = [
            { key: 'server_path', label: 'サーバーパス', type: 'text', desc: 'パルワールドサーバーのインストール先パス' },
            { key: 'launch_params', label: '起動パラメータ', type: 'text', desc: 'PalServer.shに渡す起動オプション' },
            { key: 'server_port', label: 'サーバーポート', type: 'number', desc: 'ゲームサーバーのUDPポート' },
            { divider: true, label: '🔄 自動再起動設定' },
            { key: 'auto_restart_on_crash', label: 'クラッシュ時自動再起動', type: 'toggle', desc: 'サーバーが予期せず停止した場合に自動再起動します' },
            { key: 'auto_update_on_restart', label: '再起動時自動アップデート', type: 'toggle', desc: '再起動時に自動的にサーバーをアップデートします' },
            { key: 'restart_schedule_enabled', label: 'スケジュール再起動', type: 'toggle', desc: '定期的にサーバーを自動再起動します' },
            { key: 'restart_interval_hours', label: '再起動間隔（時間）', type: 'number', desc: 'スケジュール再起動の間隔' },
            { key: 'restart_warning_minutes', label: '再起動警告（分前）', type: 'number', desc: '再起動前にプレイヤーに通知する時間' },
            { divider: true, label: '💾 バックアップ設定' },
            { key: 'auto_backup', label: '自動バックアップ', type: 'toggle', desc: '定期的にワールドデータをバックアップします' },
            { key: 'backup_interval_hours', label: 'バックアップ間隔（時間）', type: 'number', desc: '自動バックアップの間隔' },
            { key: 'max_backups', label: '最大保持数', type: 'number', desc: 'バックアップの最大保持数（超過分は古いものから削除）' },
            { key: 'backup_path', label: 'バックアップ保存先', type: 'text', desc: 'バックアップファイルの保存ディレクトリ' },
            { divider: true, label: '🔌 RCON設定' },
            { key: 'rcon_enabled', label: 'RCON有効', type: 'toggle', desc: 'RCONプロトコルによるリモート管理を有効にします' },
            { key: 'rcon_port', label: 'RCONポート', type: 'number', desc: 'RCONの待ち受けポート' },
            { key: 'rcon_password', label: 'RCONパスワード', type: 'text', desc: 'RCON認証パスワード（AdminPasswordと同じ値を推奨）' },
            { divider: true, label: '🔐 Web管理設定' },
            { key: 'web_password', label: '管理画面パスワード', type: 'text', desc: 'この管理画面へのログインパスワード' },
        ];

        let html = '';

        for (const field of fields) {
            if (field.divider) {
                html += `<h3 class="form-divider">${field.label}</h3>`;
                continue;
            }

            const val = config[field.key] !== undefined ? config[field.key] : '';

            if (field.type === 'toggle') {
                const checked = val ? 'checked' : '';
                html += `
                    <div class="setting-item">
                        <label class="toggle-switch-wrapper">
                            <label class="toggle-switch">
                                <input type="checkbox" id="mc-${field.key}" ${checked}>
                                <span class="slider"></span>
                            </label>
                            <span class="label-text">${field.label}</span>
                        </label>
                        <div class="setting-desc">${field.desc}</div>
                    </div>
                `;
            } else if (field.type === 'number') {
                html += `
                    <div class="setting-item">
                        <label>${field.label}</label>
                        <input type="number" id="mc-${field.key}" value="${val}">
                        <div class="setting-desc">${field.desc}</div>
                    </div>
                `;
            } else {
                html += `
                    <div class="setting-item">
                        <label>${field.label}</label>
                        <input type="text" id="mc-${field.key}" value="${this.escapeHtml(String(val))}">
                        <div class="setting-desc">${field.desc}</div>
                    </div>
                `;
            }
        }

        form.innerHTML = html;
    }

    async saveManagerConfig() {
        const fields = [
            'server_path', 'launch_params', 'server_port',
            'auto_restart_on_crash', 'auto_update_on_restart',
            'restart_schedule_enabled', 'restart_interval_hours', 'restart_warning_minutes',
            'auto_backup', 'backup_interval_hours', 'max_backups', 'backup_path',
            'rcon_enabled', 'rcon_port', 'rcon_password',
            'web_password'
        ];
        const toggleFields = [
            'auto_restart_on_crash', 'auto_update_on_restart',
            'restart_schedule_enabled', 'auto_backup', 'rcon_enabled'
        ];
        const numberFields = [
            'server_port', 'restart_interval_hours', 'restart_warning_minutes',
            'backup_interval_hours', 'max_backups', 'rcon_port'
        ];

        const newConfig = {};

        for (const key of fields) {
            const el = document.getElementById(`mc-${key}`);
            if (!el) continue;

            if (toggleFields.includes(key)) {
                newConfig[key] = el.checked;
            } else if (numberFields.includes(key)) {
                newConfig[key] = parseInt(el.value) || 0;
            } else {
                newConfig[key] = el.value;
            }
        }

        try {
            await this.apiCall('/manager-config', 'POST', newConfig);
            this.showToast('マネージャー設定を保存しました', 'success');
        } catch (e) {
            this.showToast('設定の保存に失敗しました', 'error');
        }
    }

    // ==========================================
    // ユーティリティ
    // ==========================================
    showToast(msg, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️';
        toast.innerHTML = `<span>${icon}</span> <span>${msg}</span>`;

        container.appendChild(toast);
        setTimeout(() => {
            if (toast.parentNode) toast.remove();
        }, 3500);
    }

    showConfirm(msg, onConfirm) {
        const modal = document.getElementById('confirm-modal');
        document.getElementById('modal-message').textContent = msg;
        modal.classList.add('active');

        const confirmBtn = document.getElementById('modal-btn-confirm');
        const newBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

        newBtn.addEventListener('click', () => {
            modal.classList.remove('active');
            onConfirm();
        });
    }

    formatUptime(sec) {
        if (!sec || sec <= 0) return '00:00:00';
        const d = Math.floor(sec / 86400);
        const h = Math.floor((sec % 86400) / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return d > 0 ? `${d}d ${timeStr}` : timeStr;
    }

    formatBytes(mb) {
        if (!mb || mb <= 0) return '0 MB';
        if (mb < 1024) return `${mb.toFixed(0)} MB`;
        return `${(mb / 1024).toFixed(2)} GB`;
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('ja-JP');
        } catch (e) {
            return dateString;
        }
    }

    escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return String(unsafe);
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new PalServerManager();
    window.app.init();
});
