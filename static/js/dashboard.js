/**
 * ダッシュボード JavaScript
 */

// グローバル変数
let socket = null;
let currentSymbol = null;
let pnlChart = null;

// 初期化
$(document).ready(function() {
    initializeSocket();
    initializeEventHandlers();
    loadDashboardData();
    initializeCharts();
});

// Socket.IO初期化
function initializeSocket() {
    socket = io();

    socket.on('connect', function() {
        console.log('Connected to server');
        showAlert('サーバーに接続しました', 'success');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        showAlert('サーバーから切断されました', 'warning');
    });

    socket.on('monitoring_update', function(data) {
        updateMonitoringTable(data);
        updateStatusCards(data);
    });

    socket.on('screening_update', function(data) {
        updateScreeningResults(data);
    });

    socket.on('alert', function(data) {
        showAlert(data.message, 'danger');
    });
}

// イベントハンドラー初期化
function initializeEventHandlers() {
    // ナビゲーション
    $('#nav-dashboard').click(function(e) {
        e.preventDefault();
        showTab('dashboard');
    });

    $('#nav-screening').click(function(e) {
        e.preventDefault();
        showTab('screening');
        loadScreeningResults();
    });

    $('#nav-monitoring').click(function(e) {
        e.preventDefault();
        showTab('monitoring');
        loadMonitoringStatus();
    });

    $('#nav-positions').click(function(e) {
        e.preventDefault();
        showTab('positions');
        loadPositions();
    });

    // スクリーニング実行
    $('#run-screening').click(function() {
        runScreening();
    });

    // モニタリング制御
    $('#start-monitoring').click(function() {
        socket.emit('start_monitoring');
    });

    $('#stop-monitoring').click(function() {
        socket.emit('stop_monitoring');
    });

    // 監視リストに追加
    $('#add-to-monitoring').click(function() {
        if (currentSymbol) {
            addToMonitoring(currentSymbol);
        }
    });
}

// タブ表示
function showTab(tabName) {
    $('.tab-content').hide();
    $(`#${tabName}-tab`).show();

    $('.nav-link').removeClass('active');
    $(`#nav-${tabName}`).addClass('active');
}

// ダッシュボードデータ読み込み
function loadDashboardData() {
    // パフォーマンス統計
    $.get('/api/performance', function(response) {
        if (response.status === 'success') {
            // ステータスカード更新
            $('#win-rate').text(`${(response.stats_30d.win_rate * 100).toFixed(1)}%`);

            // トップパフォーマー表示
            displayTopPerformers(response.top_performers);
        }
    });

    // 最新のスクリーニング結果
    $.get('/api/screening/latest', function(response) {
        if (response.status === 'success') {
            $('#today-picks').text(response.count);
        }
    });

    // モニタリング状況
    $.get('/api/monitoring/status', function(response) {
        if (response.status === 'success') {
            $('#monitoring-count').text(response.monitoring.monitoring_count);
            $('#today-pnl').text(formatCurrency(response.portfolio.realized_pnl));
        }
    });
}

// チャート初期化
function initializeCharts() {
    // 損益推移チャート
    const ctx = document.getElementById('pnl-chart').getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '累積損益',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '¥' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

// スクリーニング結果読み込み
function loadScreeningResults() {
    $.get('/api/screening/latest', function(response) {
        if (response.status === 'success') {
            displayScreeningResults(response);
        }
    });
}

// スクリーニング結果表示
function displayScreeningResults(response) {
    // 新しい構造に対応
    if (response.under_3000) {
        displayCategoryResults(response.under_3000, '#under-3000-table tbody', '#under-3000-count');
    }

    if (response.range_3000_10000) {
        displayCategoryResults(response.range_3000_10000, '#range-3000-10000-table tbody', '#range-3000-10000-count');
    }

    // 全体ランキングも表示
    if (response.top_picks && response.watch_list) {
        const allResults = [...response.top_picks, ...response.watch_list];
        displayAllScreeningResults(allResults);
    }
}

// カテゴリー別結果表示
function displayCategoryResults(categoryData, tableSelector, countSelector) {
    const tbody = $(tableSelector);
    tbody.empty();

    // 件数表示を更新
    $(countSelector).text(categoryData.count);

    categoryData.stocks.forEach(function(stock) {
        const signals = stock.signals ? stock.signals.join(', ') : '';
        const row = `
            <tr>
                <td>${stock.category_rank || stock.rank || '-'}</td>
                <td class="fw-bold text-primary">${stock.stock_code}</td>
                <td><span class="badge bg-secondary">${stock.exchange}</span></td>
                <td>${stock.name || '-'}</td>
                <td><span class="badge bg-success">${stock.total_score ? stock.total_score.toFixed(1) : '-'}</span></td>
                <td class="fw-bold">${formatCurrency(stock.current_price)}</td>
                <td class="${stock.gap_ratio > 0 ? 'text-success' : 'text-danger'}">
                    ${stock.gap_ratio ? (stock.gap_ratio * 100).toFixed(2) + '%' : '-'}
                </td>
                <td>${stock.volume_ratio ? stock.volume_ratio.toFixed(1) + '倍' : '-'}</td>
                <td><small class="text-info">${signals}</small></td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="showStockDetails('${stock.symbol}')">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button class="btn btn-sm btn-success" onclick="addToMonitoring('${stock.symbol}')">
                        <i class="fas fa-plus"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// 全体ランキング表示
function displayAllScreeningResults(allResults) {
    const tbody = $('#screening-table tbody');
    tbody.empty();

    allResults.forEach(function(stock) {
        const signals = stock.signals ? stock.signals.join(', ') : '';
        const row = `
            <tr>
                <td>${stock.rank || '-'}</td>
                <td class="fw-bold text-primary">${stock.stock_code}</td>
                <td><span class="badge bg-secondary">${stock.exchange}</span></td>
                <td>${stock.name || '-'}</td>
                <td><span class="badge bg-success">${stock.total_score ? stock.total_score.toFixed(1) : '-'}</span></td>
                <td class="fw-bold">${formatCurrency(stock.current_price)}</td>
                <td class="${stock.gap_ratio > 0 ? 'text-success' : 'text-danger'}">
                    ${stock.gap_ratio ? (stock.gap_ratio * 100).toFixed(2) + '%' : '-'}
                </td>
                <td>${stock.volume_ratio ? stock.volume_ratio.toFixed(1) + '倍' : '-'}</td>
                <td><small class="text-info">${signals}</small></td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="showStockDetails('${stock.symbol}')">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button class="btn btn-sm btn-success" onclick="addToMonitoring('${stock.symbol}')">
                        <i class="fas fa-plus"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// 銘柄詳細表示
function showStockDetails(symbol) {
    currentSymbol = symbol;
    $('#stockModalLabel').text(`銘柄詳細: ${symbol}`);

    $.get(`/api/stock/${symbol}`, function(response) {
        if (response.status === 'success') {
            // テクニカル指標表示
            displayIndicators(response.indicators);

            // 推奨アクション表示
            displayRecommendation(response);
        }
    });

    // チャートデータ取得
    $.get(`/api/chart/${symbol}`, function(response) {
        if (response.status === 'success') {
            Plotly.newPlot('stock-chart', response.chart.data, response.chart.layout);
        }
    });

    $('#stockModal').modal('show');
}

// テクニカル指標表示
function displayIndicators(indicators) {
    const tbody = $('#indicators-table tbody');
    tbody.empty();

    if (indicators.rsi) {
        tbody.append(`<tr><td>RSI</td><td>${indicators.rsi.value.toFixed(2)}</td></tr>`);
    }
    if (indicators.macd) {
        tbody.append(`<tr><td>MACD</td><td>${indicators.macd.macd.toFixed(2)}</td></tr>`);
    }
    if (indicators.bollinger) {
        tbody.append(`<tr><td>BB位置</td><td>${(indicators.bollinger.position * 100).toFixed(1)}%</td></tr>`);
    }
    if (indicators.adx) {
        tbody.append(`<tr><td>ADX</td><td>${indicators.adx.value.toFixed(2)}</td></tr>`);
    }
}

// 推奨アクション表示
function displayRecommendation(data) {
    const panel = $('#recommendation-panel');
    panel.empty();

    const signal = data.indicators.signal_summary || {};
    const recommendation = signal.recommendation || 'hold';
    const confidence = signal.confidence || 0;

    let badgeClass = 'secondary';
    let badgeText = 'ホールド';

    if (recommendation.includes('buy')) {
        badgeClass = 'success';
        badgeText = recommendation === 'strong_buy' ? '強い買い' : '買い';
    } else if (recommendation.includes('sell')) {
        badgeClass = 'danger';
        badgeText = recommendation === 'strong_sell' ? '強い売り' : '売り';
    }

    const html = `
        <div class="alert alert-info">
            <h6>シグナル: <span class="badge bg-${badgeClass}">${badgeText}</span></h6>
            <p>信頼度: ${(confidence * 100).toFixed(0)}%</p>
            <p>現在値: ${formatCurrency(data.current_price)}</p>
        </div>
    `;

    panel.html(html);
}

// 監視リストに追加
function addToMonitoring(symbol) {
    const currentPrice = prompt(`${symbol}のエントリー価格を入力してください:`);

    if (currentPrice) {
        const data = {
            symbol: symbol,
            entry_price: parseFloat(currentPrice),
            stop_loss: parseFloat(currentPrice) * 0.97,
            take_profit: parseFloat(currentPrice) * 1.05
        };

        $.ajax({
            url: '/api/monitoring/add',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                showAlert(`${symbol}を監視リストに追加しました`, 'success');
                loadMonitoringStatus();
            },
            error: function(error) {
                showAlert('エラーが発生しました', 'danger');
            }
        });
    }
}

// モニタリング状況読み込み
function loadMonitoringStatus() {
    $.get('/api/monitoring/status', function(response) {
        if (response.status === 'success') {
            updateMonitoringTable(response.monitoring);
            updatePortfolioStatus(response.portfolio);
        }
    });
}

// モニタリングテーブル更新
function updateMonitoringTable(data) {
    const tbody = $('#monitoring-table tbody');
    tbody.empty();

    if (data.stocks) {
        data.stocks.forEach(function(stock) {
            const pnlClass = stock.pnl > 0 ? 'text-success' : 'text-danger';
            const statusBadge = getStatusBadge(stock.status);

            const row = `
                <tr>
                    <td>${stock.symbol}</td>
                    <td>${formatCurrency(stock.entry_price)}</td>
                    <td>${formatCurrency(stock.current_price)}</td>
                    <td class="${pnlClass}">${formatCurrency(stock.pnl)}</td>
                    <td class="${pnlClass}">${stock.pnl_percentage.toFixed(2)}%</td>
                    <td>${formatCurrency(stock.stop_loss)}</td>
                    <td>${formatCurrency(stock.take_profit)}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="removeFromMonitoring('${stock.symbol}')">
                            <i class="fas fa-times"></i>
                        </button>
                    </td>
                </tr>
            `;
            tbody.append(row);
        });
    }
}

// 監視リストから削除
function removeFromMonitoring(symbol) {
    if (confirm(`${symbol}を監視リストから削除しますか？`)) {
        $.ajax({
            url: `/api/monitoring/remove/${symbol}`,
            method: 'DELETE',
            success: function(response) {
                showAlert(`${symbol}を監視リストから削除しました`, 'info');
                loadMonitoringStatus();
            },
            error: function(error) {
                showAlert('エラーが発生しました', 'danger');
            }
        });
    }
}

// ポジション読み込み
function loadPositions() {
    $.get('/api/positions', function(response) {
        if (response.status === 'success') {
            displayOpenPositions(response.open_positions);
            displayClosedPositions(response.closed_positions);
        }
    });
}

// オープンポジション表示
function displayOpenPositions(positions) {
    const tbody = $('#open-positions-table tbody');
    tbody.empty();

    positions.forEach(function(pos) {
        const pnlClass = pos.pnl > 0 ? 'text-success' : 'text-danger';

        const row = `
            <tr>
                <td>${pos.symbol}</td>
                <td>${formatDateTime(pos.entry_time)}</td>
                <td>${formatCurrency(pos.entry_price)}</td>
                <td>${pos.shares}</td>
                <td class="${pnlClass}">${formatCurrency(pos.pnl)}</td>
                <td class="${pnlClass}">${pos.pnl_percentage ? pos.pnl_percentage.toFixed(2) : '0.00'}%</td>
                <td>
                    <button class="btn btn-sm btn-warning" onclick="closePosition('${pos.symbol}')">
                        決済
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// クローズドポジション表示
function displayClosedPositions(positions) {
    const tbody = $('#closed-positions-table tbody');
    tbody.empty();

    positions.forEach(function(pos) {
        const pnlClass = pos.pnl > 0 ? 'text-success' : 'text-danger';

        const row = `
            <tr>
                <td>${pos.symbol}</td>
                <td>${formatCurrency(pos.entry_price)}</td>
                <td>${formatCurrency(pos.exit_price)}</td>
                <td>${pos.holding_period ? pos.holding_period.toFixed(1) + '時間' : '-'}</td>
                <td class="${pnlClass}">${formatCurrency(pos.pnl)}</td>
                <td class="${pnlClass}">${pos.pnl_percentage ? pos.pnl_percentage.toFixed(2) : '0.00'}%</td>
                <td>${pos.exit_reason || '-'}</td>
            </tr>
        `;
        tbody.append(row);
    });
}

// トップパフォーマー表示
function displayTopPerformers(performers) {
    const tbody = $('#top-performers-table tbody');
    tbody.empty();

    performers.forEach(function(stock) {
        const row = `
            <tr>
                <td>${stock.symbol}</td>
                <td>${stock.appearance_count}</td>
                <td>${stock.avg_score.toFixed(1)}</td>
                <td>${stock.avg_volume_ratio.toFixed(1)}倍</td>
            </tr>
        `;
        tbody.append(row);
    });
}

// ステータスカード更新
function updateStatusCards(data) {
    $('#monitoring-count').text(data.monitoring_count || 0);

    if (data.total_pnl !== undefined) {
        const pnlElement = $('#today-pnl');
        pnlElement.text(formatCurrency(data.total_pnl));
        pnlElement.removeClass('text-success text-danger');
        pnlElement.addClass(data.total_pnl >= 0 ? 'text-success' : 'text-danger');
    }
}

// ポートフォリオ状況更新
function updatePortfolioStatus(portfolio) {
    if (portfolio.win_rate !== undefined) {
        $('#win-rate').text(`${(portfolio.win_rate * 100).toFixed(1)}%`);
    }
}

// ステータスバッジ取得
function getStatusBadge(status) {
    const badges = {
        'monitoring': '<span class="badge bg-primary">監視中</span>',
        'stop_loss_triggered': '<span class="badge bg-danger">損切り</span>',
        'take_profit_triggered': '<span class="badge bg-success">利確</span>',
        'open': '<span class="badge bg-info">オープン</span>',
        'closed': '<span class="badge bg-secondary">クローズ</span>'
    };
    return badges[status] || '<span class="badge bg-secondary">不明</span>';
}

// 通貨フォーマット
function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '-';
    return '¥' + amount.toLocaleString('ja-JP', { maximumFractionDigits: 0 });
}

// 日時フォーマット
function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return '-';
    const dt = new Date(dateTimeStr);
    return dt.toLocaleString('ja-JP', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// アラート表示
function showAlert(message, type) {
    const toast = new bootstrap.Toast(document.getElementById('alertToast'));
    $('#alertMessage').text(message);

    const toastElement = $('#alertToast');
    toastElement.removeClass('bg-success bg-danger bg-warning bg-info');
    toastElement.addClass(`bg-${type === 'success' ? 'success' : type === 'danger' ? 'danger' : 'warning'}`);

    toast.show();
}

// スクリーニング実行
function runScreening() {
    $('#run-screening').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> 実行中...');

    // サーバー側でスクリーニング実行
    $.post('/api/screening/run', function(response) {
        if (response.status === 'success') {
            showAlert('スクリーニングが完了しました', 'success');
            loadScreeningResults();
        }
    }).always(function() {
        $('#run-screening').prop('disabled', false).html('<i class="fas fa-play"></i> スクリーニング実行');
    });
}