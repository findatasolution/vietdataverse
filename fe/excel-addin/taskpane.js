'use strict';

var API_BASE = 'https://api.vietdataverse.online/api/v1';
var _period = '30d';
var _apiKey = '';

Office.onReady(function (info) {
    if (info.host === Office.HostType.Excel) {
        _loadSavedKey();
    }
});

// ── API Key ───────────────────────────────────────────────────────────────────

function _loadSavedKey() {
    var saved = localStorage.getItem('vd_api_key') || '';
    if (saved) {
        document.getElementById('inp-apikey').value = saved;
        _apiKey = saved;
        _setKeyStatus('✓ Đã lưu key', 'ok');
    }
}

function saveApiKey() {
    var key = document.getElementById('inp-apikey').value.trim();
    if (!key) { _setKeyStatus('Nhập API key trước.', 'err'); return; }
    _apiKey = key;
    localStorage.setItem('vd_api_key', key);
    _setKeyStatus('Đang kiểm tra...', '');
    _verifyKey(key);
}

async function _verifyKey(key) {
    try {
        var res = await fetch(API_BASE + '/gold?limit=1', {
            headers: { 'Authorization': 'Bearer ' + key }
        });
        if (res.ok) {
            _setKeyStatus('✓ Key hợp lệ — sẵn sàng nhập dữ liệu', 'ok');
        } else if (res.status === 401 || res.status === 403) {
            _setKeyStatus('Key không hợp lệ hoặc hết hạn.', 'err');
        } else {
            _setKeyStatus('Kết nối OK (status ' + res.status + ')', 'ok');
        }
    } catch (e) {
        _setKeyStatus('Không kết nối được server.', 'err');
    }
}

function _setKeyStatus(msg, cls) {
    var el = document.getElementById('key-status');
    el.textContent = msg;
    el.className = 'hint ' + (cls || '');
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function onDatatypeChange() {
    var val = document.getElementById('sel-datatype').value;
    document.querySelectorAll('.sub-opts').forEach(function (el) { el.classList.add('hidden'); });
    var map = {
        'gold': 'sub-gold',
        'sbv-rate': 'sub-sbvrate',
        'termdepo': 'sub-termdepo',
        'vn30/ohlcv': 'sub-vn30',
        'global': 'sub-global',
    };
    if (map[val]) document.getElementById(map[val]).classList.remove('hidden');
}

function setPeriod(btn, p) {
    _period = p;
    document.querySelectorAll('.btn-period').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
}

// ── Fetch data from API ───────────────────────────────────────────────────────

async function _fetchData() {
    if (!_apiKey) { return { error: 'Chưa nhập API key. Nhập key ở trên rồi nhấn Lưu.' }; }

    var dtype = document.getElementById('sel-datatype').value;
    var params = new URLSearchParams();

    if (_period !== 'all') params.set('period', _period);

    // Build endpoint + params per data type
    var endpoint = dtype;
    if (dtype === 'gold') {
        var gt = document.getElementById('sel-gold-type').value;
        if (gt) params.set('type', gt);
    } else if (dtype === 'sbv-rate') {
        var bank = document.getElementById('sel-bank').value;
        if (bank) params.set('bank', bank);
        params.set('currency', 'USD');
    } else if (dtype === 'termdepo') {
        var term = document.getElementById('sel-term').value;
        if (term) params.set('term', term);
    } else if (dtype === 'vn30/ohlcv') {
        var ticker = document.getElementById('inp-ticker').value.trim().toUpperCase();
        if (ticker) params.set('ticker', ticker);
    } else if (dtype === 'global') {
        var sym = document.getElementById('sel-global').value;
        params.set('symbol', sym);
    }

    var url = API_BASE + '/' + endpoint + '?' + params.toString();

    try {
        var res = await fetch(url, { headers: { 'Authorization': 'Bearer ' + _apiKey } });
        var json = await res.json();
        if (!res.ok) {
            var msg = (json.detail && typeof json.detail === 'string') ? json.detail : ('Lỗi ' + res.status);
            return { error: msg };
        }
        return { data: json.data || json };
    } catch (e) {
        return { error: 'Không kết nối được API.' };
    }
}

// ── Build rows for Excel ──────────────────────────────────────────────────────

function _toRows(data, dtype) {
    if (!data || data.length === 0) return { headers: [], rows: [] };

    // Flatten first row to detect columns
    var sample = data[0];
    var headers = Object.keys(sample);

    var rows = data.map(function (item) {
        return headers.map(function (h) {
            var v = item[h];
            if (v === null || v === undefined) return '';
            return v;
        });
    });

    return { headers: headers, rows: rows };
}

// ── Write to Excel ────────────────────────────────────────────────────────────

async function importData() {
    var btn = document.getElementById('btn-import');
    var statusEl = document.getElementById('import-status');

    btn.disabled = true;
    btn.textContent = '⏳ Đang lấy dữ liệu...';
    _setStatus('Đang gọi API...', 'info');

    var result = await _fetchData();
    if (result.error) {
        _setStatus('⚠️ ' + result.error, 'err');
        btn.disabled = false;
        btn.textContent = '⬇ Nhập vào Excel';
        return;
    }

    var data = result.data;
    if (!Array.isArray(data) || data.length === 0) {
        _setStatus('Không có dữ liệu trong khoảng thời gian này.', 'err');
        btn.disabled = false;
        btn.textContent = '⬇ Nhập vào Excel';
        return;
    }

    var dtype = document.getElementById('sel-datatype').value;
    var built = _toRows(data, dtype);

    btn.textContent = '✏️ Đang ghi vào sheet...';

    try {
        await Excel.run(async function (ctx) {
            var sheet = ctx.workbook.worksheets.getActiveWorksheet();

            // Determine start cell
            var cellAddr = document.getElementById('inp-cell').value.trim();
            var startRange;
            if (cellAddr) {
                startRange = sheet.getRange(cellAddr);
            } else {
                // Use current selection top-left
                var sel = ctx.workbook.getSelectedRange();
                sel.load('address');
                await ctx.sync();
                // Take only the first cell of selection
                startRange = sheet.getRange(sel.address.split(':')[0]);
            }

            startRange.load('address');
            await ctx.sync();

            var baseAddr = startRange.address.replace(/^[^!]+!/, ''); // strip sheet name
            var startCell = sheet.getRange(baseAddr);

            // Write headers row
            var headerRange = startCell.getResizedRange(0, built.headers.length - 1);
            headerRange.values = [built.headers];
            headerRange.format.font.bold = true;
            headerRange.format.fill.color = '#141413';
            headerRange.format.font.color = '#FAFAF5';

            // Write data rows
            var dataRange = startCell.getOffsetRange(1, 0).getResizedRange(built.rows.length - 1, built.headers.length - 1);
            dataRange.values = built.rows;
            dataRange.format.autofitColumns();

            // Zebra rows (light alternating)
            for (var i = 0; i < built.rows.length; i++) {
                if (i % 2 === 0) {
                    startCell.getOffsetRange(i + 1, 0)
                             .getResizedRange(0, built.headers.length - 1)
                             .format.fill.color = '#F5F4ED';
                }
            }

            await ctx.sync();
        });

        _setStatus('✓ Đã nhập ' + data.length + ' dòng dữ liệu vào sheet.', 'ok');
    } catch (e) {
        console.error('[vd-excel]', e);
        _setStatus('⚠️ Lỗi khi ghi vào Excel: ' + (e.message || e), 'err');
    }

    btn.disabled = false;
    btn.textContent = '⬇ Nhập vào Excel';
}

function _setStatus(msg, cls) {
    var el = document.getElementById('import-status');
    el.textContent = msg;
    el.className = 'status-msg ' + (cls || '');
}
