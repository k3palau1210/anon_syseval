/* ==========================================
   マスキング評価システム - メインアプリケーションJS
   ========================================== */

// ---- API ヘルパー ----
const API = {
    async get(url) {
        const r = await fetch(url);
        return r.json();
    },
    async post(url, data) {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        return r.json();
    },
    async put(url, data) {
        const r = await fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        return r.json();
    },
    async del(url) {
        const r = await fetch(url, { method: 'DELETE' });
        return r.json();
    }
};

// ---- ナビゲーション ----
let currentPage = 'dashboard';

function navigateTo(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    document.getElementById(`nav-${page}`).classList.add('active');
    currentPage = page;
    loadPageData(page);
}

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        navigateTo(item.dataset.page);
    });
});

function loadPageData(page) {
    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'services': loadServices(); break;
        case 'rules': loadRules(); break;
        case 'data': loadTestData(); break;
        case 'benchmark': loadBenchmarkPage(); break;
        case 'results': loadResultsPage(); break;
        case 'detail': loadDetailPage(); break;
    }
}

// ---- トースト通知 ----
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateX(100%)'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// ---- モーダル ----
function openModal(title, bodyHTML, footerHTML) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = bodyHTML;
    document.getElementById('modal-footer').innerHTML = footerHTML || '';
    document.getElementById('modal-overlay').classList.add('active');
}
function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}
document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
});

// ---- ダッシュボード ----
async function loadDashboard() {
    const [services, testData, runs] = await Promise.all([
        API.get('/api/slm-services'),
        API.get('/api/test-data'),
        API.get('/api/benchmark/runs')
    ]);

    document.getElementById('stat-services').textContent = services.length;
    document.getElementById('stat-running').textContent = services.filter(s => s.status === 'running').length;
    document.getElementById('stat-testdata').textContent = testData.length;
    document.getElementById('stat-benchmarks').textContent = runs.length;

    // サービス一覧
    const svcList = document.getElementById('dashboard-services-list');
    if (services.length === 0) {
        svcList.innerHTML = '<div class="empty-state small">サービスが登録されていません</div>';
    } else {
        svcList.innerHTML = services.slice(0, 5).map(s => `
            <div class="service-item">
                <div class="service-item-left">
                    <span class="status-dot ${s.status}"></span>
                    <div>
                        <div class="service-item-name">${esc(s.name)}</div>
                        <div class="service-item-type">${esc(s.model_name || s.type)}</div>
                    </div>
                </div>
                <span class="badge badge-${s.status}">${statusLabel(s.status)}</span>
            </div>
        `).join('');
    }

    // 最近のベンチマーク
    const recentList = document.getElementById('dashboard-recent-list');
    if (runs.length === 0) {
        recentList.innerHTML = '<div class="empty-state small">ベンチマーク結果がありません</div>';
    } else {
        recentList.innerHTML = runs.slice(0, 5).map(r => `
            <div class="service-item">
                <div class="service-item-left">
                    <div>
                        <div class="service-item-name">${esc(r.name || '名称なし')}</div>
                        <div class="service-item-type">${formatDate(r.created_at)}</div>
                    </div>
                </div>
                <span class="badge badge-${r.status}">${runStatusLabel(r.status)}</span>
            </div>
        `).join('');
    }
}

// ---- SLMサービス管理 ----
async function loadServices() {
    const services = await API.get('/api/slm-services');
    const container = document.getElementById('services-list');
    if (services.length === 0) {
        container.innerHTML = '<div class="empty-state">SLMサービスが登録されていません<br>「サービス追加」ボタンから登録してください</div>';
        return;
    }
    container.innerHTML = services.map(s => `
        <div class="service-card" data-id="${s.id}">
            <div class="service-card-header">
                <div>
                    <div class="service-card-title">${esc(s.name)}</div>
                    <div class="service-card-model">${esc(s.model_name || '')}</div>
                </div>
                <div style="display:flex;gap:6px;align-items:center">
                    <span class="badge badge-${s.type}">${typeLabel(s.type)}</span>
                    <span class="badge badge-${s.status}"><span class="status-dot ${s.status}" style="width:6px;height:6px"></span>${statusLabel(s.status)}</span>
                </div>
            </div>
            ${s.endpoint ? `<div class="service-card-endpoint">${esc(s.endpoint)}</div>` : ''}
            <div class="service-card-actions">
                ${s.type !== 'reference' ? `
                    <button class="btn btn-sm ${s.status === 'running' ? 'btn-danger' : 'btn-primary'}" onclick="toggleService(${s.id}, '${s.status}')">
                        ${s.status === 'running' ? '⏹ 停止' : '▶ 起動'}
                    </button>
                ` : ''}
                <button class="btn btn-sm btn-secondary" onclick="editService(${s.id})">編集</button>
                <button class="btn btn-sm btn-danger" onclick="deleteService(${s.id})">削除</button>
            </div>
        </div>
    `).join('');
}

document.getElementById('btn-add-service').addEventListener('click', () => showServiceModal());

function showServiceModal(service = null) {
    const isEdit = !!service;
    const body = `
        <div class="form-group">
            <label>サービス名 *</label>
            <input type="text" id="svc-name" class="form-input" value="${esc(service?.name || '')}" placeholder="例: Ollama Gemma2">
        </div>
        <div class="form-group">
            <label>タイプ *</label>
            <select id="svc-type" class="form-input">
                <option value="local" ${service?.type === 'local' ? 'selected' : ''}>ローカル (Ollama等)</option>
                <option value="api" ${service?.type === 'api' ? 'selected' : ''}>API (OpenAI互換等)</option>
                <option value="remote" ${service?.type === 'remote' ? 'selected' : ''}>リモート (Mac mini M4Pro等)</option>
                <option value="reference" ${service?.type === 'reference' ? 'selected' : ''}>リファレンス (Gemini/Claude)</option>
            </select>
        </div>
        <div class="form-group">
            <label>モデル名</label>
            <input type="text" id="svc-model" class="form-input" value="${esc(service?.model_name || '')}" placeholder="例: gemma2:2b">
        </div>
        <div class="form-group">
            <label>エンドポイント</label>
            <input type="text" id="svc-endpoint" class="form-input" value="${esc(service?.endpoint || '')}" placeholder="例: http://localhost:11434">
        </div>
        <div class="form-group">
            <label>APIキー（必要な場合）</label>
            <input type="password" id="svc-apikey" class="form-input" value="${esc(service?.api_key || '')}" placeholder="APIキー">
        </div>
        <div class="form-group">
            <label>起動コマンド（ローカルの場合）</label>
            <input type="text" id="svc-startcmd" class="form-input" value="${esc(parseConfig(service?.config_json).start_command || '')}" placeholder="例: ollama serve">
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="saveService(${service?.id || 'null'})">${isEdit ? '更新' : '追加'}</button>
    `;
    openModal(isEdit ? 'サービス編集' : 'サービス追加', body, footer);
}

async function saveService(id) {
    const data = {
        name: document.getElementById('svc-name').value,
        type: document.getElementById('svc-type').value,
        model_name: document.getElementById('svc-model').value,
        endpoint: document.getElementById('svc-endpoint').value,
        api_key: document.getElementById('svc-apikey').value,
        config: { start_command: document.getElementById('svc-startcmd').value }
    };
    if (!data.name) { showToast('サービス名を入力してください', 'error'); return; }
    if (id) {
        await API.put(`/api/slm-services/${id}`, data);
        showToast('サービスを更新しました', 'success');
    } else {
        await API.post('/api/slm-services', data);
        showToast('サービスを追加しました', 'success');
    }
    closeModal();
    loadServices();
    if (currentPage === 'dashboard') loadDashboard();
}

async function editService(id) {
    const svc = await API.get(`/api/slm-services/${id}`);
    showServiceModal(svc);
}

async function deleteService(id) {
    if (!confirm('このサービスを削除しますか？')) return;
    await API.del(`/api/slm-services/${id}`);
    showToast('サービスを削除しました', 'success');
    loadServices();
}

async function toggleService(id, status) {
    const action = status === 'running' ? 'stop' : 'start';
    const result = await API.post(`/api/slm-services/${id}/${action}`);
    showToast(result.message, result.success ? 'success' : 'error');
    loadServices();
    if (currentPage === 'dashboard') loadDashboard();
}

// ---- マスキングルール ----
async function loadRules() {
    const rules = await API.get('/api/masking-rules');
    const tbody = document.getElementById('rules-tbody');
    tbody.innerHTML = rules.map(r => `
        <tr>
            <td>
                <label class="toggle">
                    <input type="checkbox" ${r.is_active ? 'checked' : ''} onchange="toggleRule(${r.id}, this.checked)">
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td><strong>${esc(r.category)}</strong></td>
            <td><span class="text-truncate" style="display:inline-block">${esc(r.pattern || '—')}</span></td>
            <td>${esc(r.description || '')}</td>
            <td>${r.priority}</td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm btn-ghost" onclick="editRule(${r.id})">編集</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRule(${r.id})">削除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

document.getElementById('btn-add-rule').addEventListener('click', () => showRuleModal());

function showRuleModal(rule = null) {
    const isEdit = !!rule;
    const body = `
        <div class="form-group">
            <label>カテゴリ名 *</label>
            <input type="text" id="rule-category" class="form-input" value="${esc(rule?.category || '')}" placeholder="例: 氏名">
        </div>
        <div class="form-group">
            <label>パターン（正規表現 or キーワード）</label>
            <input type="text" id="rule-pattern" class="form-input" value="${esc(rule?.pattern || '')}" placeholder="例: \\d{3}-\\d{4}-\\d{4}">
        </div>
        <div class="form-group">
            <label>説明</label>
            <input type="text" id="rule-desc" class="form-input" value="${esc(rule?.description || '')}" placeholder="ルールの説明">
        </div>
        <div class="form-group">
            <label>優先度</label>
            <input type="number" id="rule-priority" class="form-input" value="${rule?.priority || 0}">
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="saveRule(${rule?.id || 'null'})">${isEdit ? '更新' : '追加'}</button>
    `;
    openModal(isEdit ? 'ルール編集' : 'ルール追加', body, footer);
}

async function saveRule(id) {
    const data = {
        category: document.getElementById('rule-category').value,
        pattern: document.getElementById('rule-pattern').value,
        description: document.getElementById('rule-desc').value,
        priority: parseInt(document.getElementById('rule-priority').value) || 0,
        is_active: true
    };
    if (!data.category) { showToast('カテゴリ名を入力してください', 'error'); return; }
    if (id) {
        await API.put(`/api/masking-rules/${id}`, data);
        showToast('ルールを更新しました', 'success');
    } else {
        await API.post('/api/masking-rules', data);
        showToast('ルールを追加しました', 'success');
    }
    closeModal();
    loadRules();
}

async function editRule(id) {
    const rules = await API.get('/api/masking-rules');
    const rule = rules.find(r => r.id === id);
    showRuleModal(rule);
}

async function toggleRule(id, checked) {
    const rules = await API.get('/api/masking-rules');
    const rule = rules.find(r => r.id === id);
    if (rule) {
        rule.is_active = checked;
        await API.put(`/api/masking-rules/${id}`, rule);
    }
}

async function deleteRule(id) {
    if (!confirm('このルールを削除しますか？')) return;
    await API.del(`/api/masking-rules/${id}`);
    showToast('ルールを削除しました', 'success');
    loadRules();
}

// ---- テストデータ ----
async function loadTestData() {
    const [data, stats] = await Promise.all([
        API.get('/api/test-data'),
        API.get('/api/test-data/stats')
    ]);

    // 統計カード更新
    document.getElementById('data-stat-total').textContent = stats.total || 0;
    document.getElementById('data-stat-avglen').textContent = stats.avg_length || 0;
    document.getElementById('data-stat-expected').textContent = stats.with_expected || 0;
    document.getElementById('data-stat-totalchars').textContent = stats.total_chars ? stats.total_chars.toLocaleString() : '0';

    // 全削除ボタン
    const deleteAllBtn = document.getElementById('btn-delete-all-data');
    deleteAllBtn.style.display = data.length > 0 ? 'inline-flex' : 'none';

    // 文字数分布チャート
    const distCard = document.getElementById('data-dist-card');
    if (stats.total > 0 && stats.length_distribution) {
        distCard.style.display = 'block';
        renderDistributionChart(stats.length_distribution);
    } else {
        distCard.style.display = 'none';
    }

    // データテーブル
    const tbody = document.getElementById('data-tbody');
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state small">テストデータがありません<br>「ファイル取込」「フォルダ取込」「JSON入力」「データ追加」からデータを登録してください</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(d => `
        <tr>
            <td><input type="checkbox" class="data-check" value="${d.id}"></td>
            <td><strong>${esc(d.title)}</strong></td>
            <td><span class="text-truncate" style="display:inline-block;max-width:300px;cursor:pointer" title="${esc(d.original_text)}" onclick="viewTestData(${d.id})">${esc(truncate(d.original_text, 60))}</span></td>
            <td style="text-align:center"><span class="badge">${d.original_text ? d.original_text.length : 0}</span></td>
            <td>${d.expected_masked_text ? '✅ あり' : '—'}</td>
            <td>${formatDate(d.created_at)}</td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm btn-ghost" onclick="viewTestData(${d.id})">表示</button>
                    <button class="btn btn-sm btn-ghost" onclick="editTestData(${d.id})">編集</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteTestData(${d.id})">削除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function renderDistributionChart(dist) {
    const chartArea = document.getElementById('data-distribution-chart');
    const maxVal = Math.max(...dist.values, 1);
    chartArea.innerHTML = `
        <div class="chart-bar-group">
            ${dist.labels.map((label, i) => {
        const h = Math.max((dist.values[i] / maxVal) * 120, 2);
        const color = dist.values[i] > 0 ? '#2563eb' : '#e5e7eb';
        return `
                    <div class="chart-bar-wrapper">
                        <div class="chart-bar-value">${dist.values[i]}</div>
                        <div class="chart-bar" style="height:${h}px;background:${color}" title="${label}: ${dist.values[i]}件"></div>
                        <div class="chart-bar-label">${label}</div>
                    </div>`;
    }).join('')}
        </div>
    `;
}

// ファイル取込
document.getElementById('btn-upload-file').addEventListener('click', () => {
    document.getElementById('file-upload-input').click();
});

document.getElementById('file-upload-input').addEventListener('change', async function () {
    const files = this.files;
    if (!files || files.length === 0) return;

    let totalImported = 0;
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch('/api/test-data/upload', { method: 'POST', body: formData });
            const result = await res.json();
            if (result.success) {
                totalImported += result.imported;
            } else {
                showToast(`${file.name}: ${result.error}`, 'error');
            }
        } catch (e) {
            showToast(`${file.name}: アップロードエラー`, 'error');
        }
    }
    if (totalImported > 0) {
        showToast(`${totalImported}件のデータを取り込みました`, 'success');
        loadTestData();
    }
    this.value = '';
});

// フォルダ取込
document.getElementById('btn-import-folder').addEventListener('click', () => {
    const body = `
        <div class="form-group">
            <label>フォルダパス *</label>
            <input type="text" id="folder-path" class="form-input" placeholder="例: /Users/user/testdata">
            <p style="font-size:0.8rem;color:var(--text-tertiary);margin-top:4px">
                サーバー上のフォルダパスを指定してください。<br>
                対応形式: .json, .csv, .txt<br>
                フォルダ内の全対応ファイルを一括取り込みます。
            </p>
        </div>
        <div class="form-group" style="margin-top:12px">
            <label>CSVファイルの形式</label>
            <div class="result-box" style="font-size:0.8rem;line-height:1.6">
                <strong>ヘッダー行：</strong> title (またはタイトル), original_text (またはtext/テキスト), expected_masked_text (またはexpected/期待結果)<br>
                <strong>JSON形式：</strong> 配列 [{"title":"...", "original_text":"..."}] または {"items":[...]} / {"data":[...]}
            </div>
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="importFromFolder()">取込実行</button>
    `;
    openModal('フォルダからデータ取込', body, footer);
});

async function importFromFolder() {
    const folderPath = document.getElementById('folder-path').value;
    if (!folderPath) { showToast('フォルダパスを入力してください', 'error'); return; }

    try {
        const result = await API.post('/api/test-data/import-folder', { folder_path: folderPath });
        if (result.success) {
            let msg = `${result.imported}件のデータを取り込みました`;
            if (result.errors && result.errors.length > 0) {
                msg += `（エラー: ${result.errors.length}件）`;
            }
            showToast(msg, result.imported > 0 ? 'success' : 'warning');
            closeModal();
            loadTestData();
        } else {
            showToast(result.error || 'フォルダ取込に失敗しました', 'error');
        }
    } catch (e) {
        showToast('フォルダ取込に失敗しました', 'error');
    }
}

// 全データ削除
document.getElementById('btn-delete-all-data').addEventListener('click', async () => {
    if (!confirm('全テストデータを削除しますか？この操作は取り消せません。')) return;
    await API.post('/api/test-data/delete-all');
    showToast('全テストデータを削除しました', 'success');
    loadTestData();
});

document.getElementById('btn-add-data').addEventListener('click', () => showDataModal());
document.getElementById('btn-import-data').addEventListener('click', () => showImportModal());

function showDataModal(data = null) {
    const isEdit = !!data;
    const body = `
        <div class="form-group">
            <label>タイトル *</label>
            <input type="text" id="td-title" class="form-input" value="${esc(data?.title || '')}" placeholder="例: テスト通話001">
        </div>
        <div class="form-group">
            <label>テキスト（音声認識テキスト） *</label>
            <textarea id="td-text" class="form-input" rows="6" placeholder="音声認識テキストを入力...">${esc(data?.original_text || '')}</textarea>
        </div>
        <div class="form-group">
            <label>期待されるマスキング結果（オプション）</label>
            <textarea id="td-expected" class="form-input" rows="4" placeholder="正解のマスキング結果があれば入力...">${esc(data?.expected_masked_text || '')}</textarea>
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="saveTestData(${data?.id || 'null'})">${isEdit ? '更新' : '追加'}</button>
    `;
    openModal(isEdit ? 'テストデータ編集' : 'テストデータ追加', body, footer);
}

function showImportModal() {
    const body = `
        <div class="form-group">
            <label>JSON形式で一括インポート</label>
            <textarea id="import-json" class="form-input" rows="10" placeholder='[
  {"title": "テスト1", "original_text": "お電話ありがとうございます。田中太郎と申します。"},
  {"title": "テスト2", "original_text": "住所は東京都渋谷区..."}
]'></textarea>
        </div>
        <p style="font-size:0.8rem;color:var(--text-tertiary)">配列形式のJSONで、各要素に title と original_text を含めてください。</p>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="importTestData()">インポート</button>
    `;
    openModal('テストデータインポート', body, footer);
}

async function saveTestData(id) {
    const data = {
        title: document.getElementById('td-title').value,
        original_text: document.getElementById('td-text').value,
        expected_masked_text: document.getElementById('td-expected').value
    };
    if (!data.title || !data.original_text) { showToast('タイトルとテキストは必須です', 'error'); return; }
    if (id) {
        await API.put(`/api/test-data/${id}`, data);
        showToast('テストデータを更新しました', 'success');
    } else {
        await API.post('/api/test-data', data);
        showToast('テストデータを追加しました', 'success');
    }
    closeModal();
    loadTestData();
}

async function editTestData(id) {
    const allData = await API.get('/api/test-data');
    const data = allData.find(d => d.id === id);
    showDataModal(data);
}

async function viewTestData(id) {
    const allData = await API.get('/api/test-data');
    const data = allData.find(d => d.id === id);
    if (!data) return;
    const charCount = data.original_text ? data.original_text.length : 0;
    const body = `
        <div class="form-group"><label>タイトル</label><div class="result-box">${esc(data.title)}</div></div>
        <div class="form-group"><label>テキスト <span class="badge">${charCount}文字</span></label><div class="result-box" style="max-height:300px;overflow-y:auto;white-space:pre-wrap">${esc(data.original_text)}</div></div>
        ${data.expected_masked_text ? `<div class="form-group"><label>期待結果</label><div class="result-box" style="max-height:200px;overflow-y:auto;white-space:pre-wrap">${esc(data.expected_masked_text)}</div></div>` : ''}
        <div class="form-group"><label>登録日</label><div class="result-box">${formatDate(data.created_at)}</div></div>
    `;
    openModal('テストデータ詳細', body, '<button class="btn btn-secondary" onclick="closeModal()">閉じる</button>');
}

async function deleteTestData(id) {
    if (!confirm('このテストデータを削除しますか？')) return;
    await API.del(`/api/test-data/${id}`);
    showToast('テストデータを削除しました', 'success');
    loadTestData();
}

async function importTestData() {
    const jsonText = document.getElementById('import-json').value;
    try {
        const items = JSON.parse(jsonText);
        const result = await API.post('/api/test-data/import', { items });
        showToast(`${result.imported}件のデータをインポートしました`, 'success');
        closeModal();
        loadTestData();
    } catch (e) {
        showToast('JSONの形式が正しくありません', 'error');
    }
}

document.getElementById('data-select-all').addEventListener('change', function () {
    document.querySelectorAll('.data-check').forEach(cb => cb.checked = this.checked);
});

// ---- ベンチマーク ----
async function loadBenchmarkPage() {
    const [services, testData] = await Promise.all([
        API.get('/api/slm-services'),
        API.get('/api/test-data')
    ]);

    // SLMリスト
    const slmList = document.getElementById('benchmark-slm-list');
    const activeServices = services.filter(s => s.type !== 'reference');
    slmList.innerHTML = activeServices.length === 0
        ? '<div class="empty-state small">SLMサービスを先に登録してください</div>'
        : activeServices.map(s => `
            <label class="checkbox-item">
                <input type="checkbox" class="benchmark-slm-check" value="${s.id}">
                <span>${esc(s.name)}</span>
                <span class="badge badge-${s.type}" style="margin-left:auto;font-size:0.7rem">${typeLabel(s.type)}</span>
                <span class="badge badge-${s.status}" style="font-size:0.7rem">${statusLabel(s.status)}</span>
            </label>
        `).join('');

    // テストデータリスト
    const dataList = document.getElementById('benchmark-data-list');
    dataList.innerHTML = testData.length === 0
        ? '<div class="empty-state small">テストデータを先に登録してください</div>'
        : testData.map(d => `
            <label class="checkbox-item">
                <input type="checkbox" class="benchmark-data-check" value="${d.id}">
                <span>${esc(d.title)}</span>
            </label>
        `).join('');

    // 単体テスト用SLMセレクト
    const select = document.getElementById('test-slm-select');
    select.innerHTML = '<option value="">-- SLMを選択 --</option>' +
        activeServices.map(s => `<option value="${s.id}">${esc(s.name)} (${typeLabel(s.type)})</option>`).join('');
}

document.getElementById('btn-run-benchmark').addEventListener('click', async () => {
    const slmIds = Array.from(document.querySelectorAll('.benchmark-slm-check:checked')).map(c => parseInt(c.value));
    const dataIds = Array.from(document.querySelectorAll('.benchmark-data-check:checked')).map(c => parseInt(c.value));
    const name = document.getElementById('benchmark-name').value || `ベンチマーク ${new Date().toLocaleString('ja')}`;
    const desc = document.getElementById('benchmark-desc').value;

    if (slmIds.length === 0) { showToast('SLMサービスを選択してください', 'error'); return; }
    if (dataIds.length === 0) { showToast('テストデータを選択してください', 'error'); return; }

    const result = await API.post('/api/benchmark/run', {
        name, description: desc, slm_service_ids: slmIds, test_data_ids: dataIds
    });

    if (result.success) {
        showToast('ベンチマークを開始しました', 'success');
        pollBenchmarkProgress(result.run_id);
    } else {
        showToast(result.error || result.message || 'エラーが発生しました', 'error');
    }
});

async function pollBenchmarkProgress(runId) {
    const container = document.getElementById('benchmark-progress');
    const poll = async () => {
        const run = await API.get(`/api/benchmark/runs/${runId}`);
        const pct = run.progress ? Math.round((run.progress.completed / run.progress.total) * 100) : 0;
        container.innerHTML = `
            <div style="margin-bottom:12px">
                <strong>${esc(run.name || '')}</strong>
                <span class="badge badge-${run.status}" style="margin-left:8px">${runStatusLabel(run.status)}</span>
            </div>
            <div class="progress-bar"><div class="progress-bar-fill" style="width:${pct}%"></div></div>
            <div class="progress-info">
                <span>${run.progress?.completed || 0} / ${run.progress?.total || 0} 完了</span>
                <span>${pct}%</span>
            </div>
            ${run.status === 'completed' ? `<div style="margin-top:12px"><button class="btn btn-primary btn-sm" onclick="navigateTo('results')">結果を確認</button></div>` : ''}
            ${run.status === 'failed' ? '<div style="margin-top:8px;color:var(--danger);font-size:0.85rem">ベンチマーク実行中にエラーが発生しました</div>' : ''}
        `;
        if (run.status === 'running' || run.status === 'pending') {
            setTimeout(poll, 2000);
        }
    };
    poll();
}

// 単体テスト
document.getElementById('btn-test-masking').addEventListener('click', async () => {
    const slmId = document.getElementById('test-slm-select').value;
    const text = document.getElementById('test-input-text').value;
    if (!slmId) { showToast('SLMを選択してください', 'error'); return; }
    if (!text.trim()) { showToast('テストテキストを入力してください', 'error'); return; }

    const btn = document.getElementById('btn-test-masking');
    btn.disabled = true;
    btn.textContent = '処理中...';

    try {
        const result = await API.post('/api/masking/test', { slm_service_id: parseInt(slmId), text });
        const resultArea = document.getElementById('test-result');
        resultArea.style.display = 'block';
        if (result.success) {
            document.getElementById('test-output').textContent = result.masked_text;
            document.getElementById('test-time').textContent = `${result.processing_time_ms.toFixed(0)}ms`;
        } else {
            document.getElementById('test-output').textContent = `エラー: ${result.message || '不明なエラー'}`;
            document.getElementById('test-time').textContent = '';
        }
    } catch (e) {
        showToast('テスト実行に失敗しました', 'error');
    }
    btn.disabled = false;
    btn.textContent = 'マスキングテスト';
});

// ---- 結果比較 ----
async function loadResultsPage() {
    const [runs, refs] = await Promise.all([
        API.get('/api/benchmark/runs'),
        API.get('/api/reference')
    ]);

    // ベンチマーク実行一覧
    const tbody = document.getElementById('results-runs-tbody');
    tbody.innerHTML = runs.map(r => `
        <tr>
            <td><input type="checkbox" class="results-run-check" value="${r.id}"></td>
            <td><strong>${esc(r.name || '名称なし')}</strong></td>
            <td><span class="badge badge-${r.status}">${runStatusLabel(r.status)}</span></td>
            <td>${formatDate(r.created_at)}</td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm btn-ghost" onclick="viewRunDetails(${r.id})">詳細</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRun(${r.id})">削除</button>
                </div>
            </td>
        </tr>
    `).join('');

    // リファレンス結果
    const refTbody = document.getElementById('ref-tbody');
    if (refs.length === 0) {
        refTbody.innerHTML = '<tr><td colspan="5" class="empty-state small">リファレンス結果がありません</td></tr>';
    } else {
        refTbody.innerHTML = refs.map(r => `
            <tr>
                <td><strong>${esc(r.model_name)}</strong></td>
                <td>${esc(r.test_title || '')}</td>
                <td><span class="text-truncate" style="display:inline-block">${esc(truncate(r.masked_text, 50))}</span></td>
                <td>${formatDate(r.created_at)}</td>
                <td><button class="btn btn-sm btn-danger" onclick="deleteRef(${r.id})">削除</button></td>
            </tr>
        `).join('');
    }
}

document.getElementById('results-select-all').addEventListener('change', function () {
    document.querySelectorAll('.results-run-check').forEach(cb => cb.checked = this.checked);
});

document.getElementById('btn-compare').addEventListener('click', async () => {
    const runIds = Array.from(document.querySelectorAll('.results-run-check:checked')).map(c => parseInt(c.value));
    if (runIds.length === 0) { showToast('比較するベンチマークを選択してください', 'error'); return; }

    const results = await API.post('/api/benchmark/compare', { run_ids: runIds });
    displayComparison(results);
});

function displayComparison(results) {
    const card = document.getElementById('comparison-card');
    card.style.display = 'block';

    // チャート
    const chartColors = ['#2563eb', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16'];
    const chartArea = document.getElementById('comparison-chart');

    if (results.length > 0) {
        const maxF1 = Math.max(...results.map(r => r.avg_f1 || 0), 0.01);
        chartArea.innerHTML = `
            <div style="text-align:center;font-weight:600;font-size:0.9rem;margin-bottom:12px;color:var(--text-secondary)">F1スコア比較</div>
            <div class="chart-bar-group">
                ${results.map((r, i) => {
            const h = Math.max(((r.avg_f1 || 0) / 1) * 160, 4);
            const color = chartColors[i % chartColors.length];
            return `
                        <div class="chart-bar-wrapper">
                            <div class="chart-bar-value">${((r.avg_f1 || 0) * 100).toFixed(1)}%</div>
                            <div class="chart-bar" style="height:${h}px;background:${color}" title="${esc(r.slm_name)}: F1=${((r.avg_f1 || 0) * 100).toFixed(1)}%"></div>
                            <div class="chart-bar-label">${esc(r.slm_name)}</div>
                        </div>`;
        }).join('')}
            </div>
        `;
    }

    // テーブル
    const tbody = document.getElementById('comparison-tbody');
    tbody.innerHTML = results.map(r => `
        <tr>
            <td><strong>${esc(r.slm_name)}</strong><br><span style="font-size:0.75rem;color:var(--text-tertiary)">${esc(r.run_name || '')}</span></td>
            <td><span class="badge badge-${r.slm_type}">${typeLabel(r.slm_type)}</span></td>
            <td>${r.test_count}</td>
            <td>${formatPct(r.avg_precision)}</td>
            <td>${formatPct(r.avg_recall)}</td>
            <td><strong>${formatPct(r.avg_f1)}</strong></td>
            <td>${formatPct(r.avg_match_rate)}</td>
            <td>${r.avg_time_ms ? r.avg_time_ms.toFixed(0) + 'ms' : '—'}</td>
        </tr>
    `).join('');
}

async function viewRunDetails(runId) {
    const run = await API.get(`/api/benchmark/runs/${runId}`);
    if (!run || !run.results) return;

    const body = `
        <div style="margin-bottom:12px">
            <strong>${esc(run.name || '')}</strong>
            <span class="badge badge-${run.status}" style="margin-left:8px">${runStatusLabel(run.status)}</span>
        </div>
        <table class="data-table">
            <thead>
                <tr><th>SLM</th><th>テスト</th><th>F1</th><th>Precision</th><th>Recall</th><th>時間</th></tr>
            </thead>
            <tbody>
                ${run.results.map(r => `
                    <tr>
                        <td>${esc(r.slm_name)}</td>
                        <td>${esc(r.test_title)}</td>
                        <td><strong>${formatPct(r.f1_score)}</strong></td>
                        <td>${formatPct(r.precision_score)}</td>
                        <td>${formatPct(r.recall_score)}</td>
                        <td>${r.processing_time_ms ? r.processing_time_ms.toFixed(0) + 'ms' : '—'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    openModal('ベンチマーク詳細', body, '<button class="btn btn-secondary" onclick="closeModal()">閉じる</button>');
}

async function deleteRun(id) {
    if (!confirm('このベンチマーク結果を削除しますか？')) return;
    await API.del(`/api/benchmark/runs/${id}`);
    showToast('ベンチマークを削除しました', 'success');
    loadResultsPage();
}

// リファレンスアップロード
document.getElementById('btn-upload-ref').addEventListener('click', () => {
    const body = `
        <div class="form-group">
            <label>モデル名 *</label>
            <input type="text" id="ref-model" class="form-input" placeholder="例: Gemini 3.1 Pro (High)">
        </div>
        <div class="form-group">
            <label>結果データ（JSON）</label>
            <textarea id="ref-json" class="form-input" rows="8" placeholder='[
  {"test_data_id": 1, "masked_text": "お電話ありがとうございます。[氏名]と申します。"},
  {"test_data_id": 2, "masked_text": "住所は[住所]..."}
]'></textarea>
        </div>
        <p style="font-size:0.8rem;color:var(--text-tertiary)">各要素に test_data_id と masked_text を含めてください。</p>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">キャンセル</button>
        <button class="btn btn-primary" onclick="uploadReference()">アップロード</button>
    `;
    openModal('リファレンス結果アップロード', body, footer);
});

async function uploadReference() {
    const modelName = document.getElementById('ref-model').value;
    const jsonText = document.getElementById('ref-json').value;
    if (!modelName) { showToast('モデル名を入力してください', 'error'); return; }
    try {
        const results = JSON.parse(jsonText);
        const res = await API.post('/api/reference/upload', { model_name: modelName, results });
        showToast(`${res.uploaded}件のリファレンス結果をアップロードしました`, 'success');
        closeModal();
        loadResultsPage();
    } catch (e) {
        showToast('JSONの形式が正しくありません', 'error');
    }
}

async function deleteRef(id) {
    if (!confirm('このリファレンス結果を削除しますか？')) return;
    await API.del(`/api/reference/${id}`);
    showToast('リファレンスを削除しました', 'success');
    loadResultsPage();
}

// ---- 詳細比較 ----
async function loadDetailPage() {
    const runs = await API.get('/api/benchmark/runs');
    const container = document.getElementById('detail-run-list');
    const completedRuns = runs.filter(r => r.status === 'completed');
    if (completedRuns.length === 0) {
        container.innerHTML = '<div class="empty-state small">完了済みのベンチマークがありません</div>';
        return;
    }
    container.innerHTML = completedRuns.map(r => `
        <label class="checkbox-item">
            <input type="checkbox" class="detail-run-check" value="${r.id}">
            <span>${esc(r.name || '名称なし')}</span>
            <span class="badge badge-completed" style="margin-left:auto;font-size:0.7rem">${formatDate(r.created_at)}</span>
        </label>
    `).join('');
}

document.getElementById('btn-detail-compare').addEventListener('click', executeDetailCompare);

async function executeDetailCompare() {
    const runIds = Array.from(document.querySelectorAll('.detail-run-check:checked')).map(c => parseInt(c.value));
    if (runIds.length === 0) { showToast('比較するベンチマークを選択してください', 'error'); return; }

    const btn = document.getElementById('btn-detail-compare');
    btn.disabled = true;
    btn.textContent = '読み込み中...';

    try {
        const items = await API.post('/api/benchmark/detail-compare', { run_ids: runIds });
        renderDetailResults(items);
    } catch (e) {
        showToast('詳細比較の取得に失敗しました', 'error');
    }
    btn.disabled = false;
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="2" width="5" height="12" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="8" y="2" width="5" height="12" rx="1" stroke="currentColor" stroke-width="1.5"/></svg> 詳細比較を実行';
}

function renderDetailResults(items) {
    const area = document.getElementById('detail-results-area');
    if (!items || items.length === 0) {
        area.innerHTML = '<div class="empty-state">比較結果がありません</div>';
        return;
    }

    area.innerHTML = items.map((item, idx) => {
        const orig = item.original_text || '';

        // SLM結果カラム
        const slmCols = item.slm_results.map(sr => {
            const f1 = sr.f1 != null ? (sr.f1 * 100).toFixed(1) : '-';
            const match = sr.match_rate != null ? (sr.match_rate * 100).toFixed(1) : '-';
            const ms = sr.processing_time_ms != null ? sr.processing_time_ms.toFixed(0) : '-';
            return '<div class="detail-col">' +
                '<div class="detail-col-header">' +
                '<span class="detail-col-title">' + esc(sr.slm_name) + '</span>' +
                '<span class="badge badge-' + sr.slm_type + '" style="font-size:0.7rem">' + typeLabel(sr.slm_type) + '</span>' +
                '</div>' +
                '<div class="detail-metrics">' +
                '<span><strong>F1:</strong> ' + f1 + '%</span>' +
                '<span><strong>一致:</strong> ' + match + '%</span>' +
                '<span><strong>時間:</strong> ' + ms + 'ms</span>' +
                '</div>' +
                '<div class="detail-text-box">' + buildDiffHTML(orig, sr.masked_text || '') + '</div>' +
                '</div>';
        }).join('');

        // リファレンス結果
        const refCols = (item.reference_results || []).map(ref => {
            return '<div class="detail-col detail-col-ref">' +
                '<div class="detail-col-header">' +
                '<span class="detail-col-title">\u2605 ' + esc(ref.model_name) + '</span>' +
                '<span class="badge badge-reference" style="font-size:0.7rem">リファレンス</span>' +
                '</div>' +
                '<div class="detail-metrics"><span style="color:var(--text-tertiary);font-size:0.75rem">基準モデル（最高精度LLM）</span></div>' +
                '<div class="detail-text-box">' + buildDiffHTML(orig, ref.masked_text || '') + '</div>' +
                '</div>';
        }).join('');

        // 期待結果
        let expectedCol = '';
        if (item.expected_masked_text) {
            expectedCol = '<div class="detail-col detail-col-expected">' +
                '<div class="detail-col-header">' +
                '<span class="detail-col-title">期待結果</span>' +
                '<span class="badge" style="font-size:0.7rem">正解</span>' +
                '</div>' +
                '<div class="detail-metrics"><span style="color:var(--text-tertiary);font-size:0.75rem">手動設定された正解データ</span></div>' +
                '<div class="detail-text-box">' + buildDiffHTML(orig, item.expected_masked_text) + '</div>' +
                '</div>';
        }

        return '<div class="card detail-card" style="margin-bottom:24px">' +
            '<div class="card-header">' +
            '<h2>\uD83D\uDCC4 ' + esc(item.title) + ' <span style="font-size:0.8rem;color:var(--text-tertiary);font-weight:400">ID: ' + item.test_data_id + '</span></h2>' +
            '<span class="badge">' + orig.length + '文字</span>' +
            '</div>' +
            '<div class="card-body">' +
            '<div class="detail-grid">' +
            '<div class="detail-col detail-col-original">' +
            '<div class="detail-col-header"><span class="detail-col-title">元テキスト（マスキング前）</span></div>' +
            '<div class="detail-text-box detail-text-original">' + esc(orig) + '</div>' +
            '</div>' +
            slmCols + refCols + expectedCol +
            '</div>' +
            '</div>' +
            '</div>';
    }).join('');
}

/** 元テキストとマスキング結果の差分をハイライト表示 */
function buildDiffHTML(original, masked) {
    if (!masked) return '<span style="color:var(--text-tertiary)">結果なし</span>';
    if (!original) return esc(masked);

    // マスキングプレースホルダー（[xx]形式や《》形式）を検出しハイライト
    var maskPattern = /(\[.+?\]|\u300a.+?\u300b|\*{3,})/g;
    var result = '';
    var lastIdx = 0;
    var m;

    while ((m = maskPattern.exec(masked)) !== null) {
        if (m.index > lastIdx) {
            result += esc(masked.substring(lastIdx, m.index));
        }
        result += '<span class="mask-highlight">' + esc(m[0]) + '</span>';
        lastIdx = m.index + m[0].length;
    }
    if (lastIdx < masked.length) {
        result += esc(masked.substring(lastIdx));
    }

    // パターンが見つからなければ、単純な文字比較
    if (lastIdx === 0) {
        return buildCharDiffHTML(original, masked);
    }
    return result;
}

/** 文字単位の差分比較 */
function buildCharDiffHTML(original, masked) {
    if (original === masked) return esc(masked);
    var result = '';
    var oi = 0, mi = 0;
    while (mi < masked.length) {
        if (oi < original.length && original[oi] === masked[mi]) {
            var js = mi;
            while (oi < original.length && mi < masked.length && original[oi] === masked[mi]) { oi++; mi++; }
            result += esc(masked.substring(js, mi));
        } else {
            var ds = mi;
            while (mi < masked.length && (oi >= original.length || original[oi] !== masked[mi])) {
                mi++;
                if (mi < masked.length && oi < original.length) {
                    var look = 0;
                    for (var k = 0; k < 3 && mi + k < masked.length && oi + k < original.length; k++) {
                        if (original[oi + k] === masked[mi + k]) look++;
                    }
                    if (look >= 2) break;
                }
            }
            result += '<span class="mask-highlight">' + esc(masked.substring(ds, mi)) + '</span>';
        }
    }
    return result;
}

// ---- ユーティリティ ----
function esc(str) { if (!str) return ''; const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
function truncate(str, len) { if (!str) return ''; return str.length > len ? str.substring(0, len) + '...' : str; }
function parseConfig(json) { try { return JSON.parse(json || '{}'); } catch { return {}; } }
function formatDate(d) { if (!d) return '—'; try { return new Date(d).toLocaleString('ja'); } catch { return d; } }
function formatPct(v) { if (v == null) return '—'; return (v * 100).toFixed(1) + '%'; }
function statusLabel(s) {
    const m = { running: '稼働中', stopped: '停止', error: 'エラー', unknown: '不明' };
    return m[s] || s;
}
function runStatusLabel(s) {
    const m = { pending: '待機中', running: '実行中', completed: '完了', failed: '失敗' };
    return m[s] || s;
}
function typeLabel(t) {
    const m = { local: 'ローカル', api: 'API', remote: 'リモート', reference: 'リファレンス' };
    return m[t] || t;
}
function toggleAllCheckboxes(containerId, checked) {
    document.querySelectorAll(`#${containerId} input[type="checkbox"]`).forEach(cb => cb.checked = checked);
}

// ---- 初期ロード ----
loadDashboard();
