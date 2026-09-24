'use strict';

var API_BASE = 'https://api.vietdataverse.online/api/v1';
var _period = '1y';
var _apiKey = '';

Office.onReady(function (info) {
    if (info.host === Office.HostType.Excel) {
        _loadSavedKey();
        _loadWorkbookPeriod();
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
        // Key validation is deliberately unmetered. Using a data endpoint here
        // would consume one of the free tier's two monthly calls before the
        // user even refreshes a workbook.
        var res = await fetch(API_BASE + '/developer/verify-key', {
            headers: { 'X-API-Key':key }
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
        'gold':       'sub-gold',
        'silver':     'sub-silver',
        'sbv-rate':   'sub-sbvrate',
        'termdepo':   'sub-termdepo',
        'global':     'sub-global',
    };
    if (map[val]) document.getElementById(map[val]).classList.remove('hidden');
}

function setPeriod(btn, p) {
    _period = p;
    document.querySelectorAll('.btn-period').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
}

async function _loadWorkbookPeriod() {
    try {
        await Excel.run(async function (ctx) {
            var sheets = ctx.workbook.worksheets;
            sheets.load('items/name');
            await ctx.sync();
            var cover = sheets.items.find(function (sheet) { return sheet.name === 'Bắt đầu'; });
            if (!cover) return;
            var periodCell = cover.getRange('C7');
            periodCell.load('values');
            await ctx.sync();
            var period = String(periodCell.values[0][0] || '');
            if (!/^(7d|1m|1y|all)$/.test(period)) return;
            _period = period;
            document.querySelectorAll('.btn-period').forEach(function (button) {
                button.classList.toggle('active', button.getAttribute('data-p') === period);
            });
        });
    } catch (error) {
        // The add-in also works in arbitrary workbooks, which have no VDV cover.
    }
}

// ── Fetch data from API ───────────────────────────────────────────────────────

async function _fetchData() {
    if (!_apiKey) { return { error: 'Chưa nhập API key. Nhập key ở trên rồi nhấn Lưu.' }; }

    var dtype = document.getElementById('sel-datatype').value;
    var params = new URLSearchParams();

    if (_period !== 'all') params.set('period', _period);
    params.set('page', '1');
    params.set('limit', '500');

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
    } else if (dtype === 'global') {
        var sym = document.getElementById('sel-global').value;
        params.set('symbol', sym);
    }

    var url = API_BASE + '/' + endpoint + '?' + params.toString();

    try {
        var res = await fetch(url, { headers: { 'X-API-Key':_apiKey } });
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

function _excelDateSerial(value) {
    var match = typeof value === 'string' && value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return value;
    return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])) / 86400000 + 25569;
}

function _workbookRows(item) {
    var dateColumns = [];
    (item.headers || []).forEach(function (_, column) {
        if ((item.rows || []).some(function (row) {
            return typeof row[column] === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(row[column]);
        })) dateColumns.push(column);
    });
    return {
        dateColumns: dateColumns,
        values: (item.rows || []).map(function (row) {
            return row.map(_excelDateSerial);
        })
    };
}

async function _fetchWorkbookData() {
    if (!_apiKey) return { error: 'Chưa nhập API key. Nhập key ở trên rồi nhấn Lưu.' };
    try {
        var response = await fetch(API_BASE + '/excel/refresh-data?period=' + encodeURIComponent(_period), {
            headers: { 'X-API-Key': _apiKey }
        });
        var payload = await response.json();
        if (!response.ok) return { error: payload.detail || ('Lỗi ' + response.status) };
        return { data: payload };
    } catch (error) {
        return { error: 'Không kết nối được API.' };
    }
}

async function refreshWorkbook() {
    var button = document.getElementById('btn-refresh-workbook');
    button.disabled = true;
    button.textContent = '⏳ Đang tải dữ liệu...';
    _setRefreshStatus('Đang gọi API cho toàn bộ workbook...', 'info');

    var result = await _fetchWorkbookData();
    if (result.error) {
        _setRefreshStatus('⚠️ ' + result.error, 'err');
        button.disabled = false;
        button.textContent = '↻ Refresh toàn bộ workbook';
        return;
    }

    var payload = result.data;
    try {
        await Excel.run(async function (ctx) {
            var sheets = ctx.workbook.worksheets;
            var tables = ctx.workbook.tables;
            sheets.load('items/name');
            tables.load('items/name');
            await ctx.sync();

            var sheetByName = {};
            sheets.items.forEach(function (sheet) { sheetByName[sheet.name] = sheet; });
            var tableByName = {};
            tables.items.forEach(function (table) { tableByName[table.name] = table; });

            payload.data.forEach(function (item) {
                if (item.error || !item.headers || item.headers.length === 0) return;
                var sheet = sheetByName[item.sheet] || sheets.add(item.sheet);
                sheetByName[item.sheet] = sheet;
                var built = _workbookRows(item);
                var rowCount = Math.max(1, built.values.length);
                var target = sheet.getRangeByIndexes(3, 0, rowCount + 1, item.headers.length);
                var table = tableByName[item.table];

                if (table) {
                    table.getRange().clear('Contents');
                    table.resize(target);
                } else {
                    table = sheet.tables.add(target, true);
                    table.name = item.table;
                    table.style = 'TableStyleMedium2';
                    tableByName[item.table] = table;
                }

                var values = [item.headers].concat(built.values);
                if (built.values.length === 0) values.push(item.headers.map(function () { return ''; }));
                target.values = values;
                built.dateColumns.forEach(function (column) {
                    var dateRange = sheet.getRangeByIndexes(4, column, built.values.length, 1);
                    dateRange.numberFormat = built.values.map(function () { return ['dd/mm/yyyy']; });
                });
                sheet.getUsedRange().format.autofitColumns();
            });

            var cover = sheetByName['Bắt đầu'];
            if (cover) {
                cover.getRange('C7').values = [[payload.period]];
                cover.getRange('C8').values = [[new Date(payload.refreshed_at).toLocaleString('vi-VN')]];
            }
            await ctx.sync();
        });

        var failures = payload.data.filter(function (item) { return item.error; });
        if (failures.length) {
            _setRefreshStatus('Đã cập nhật ' + (payload.count - failures.length) + '/' + payload.count +
                              ' bộ dữ liệu. Thử lại các bộ còn lỗi.', 'err');
        } else {
            _setRefreshStatus('✓ Đã refresh ' + payload.count + ' bộ dữ liệu trong file.', 'ok');
        }
    } catch (error) {
        console.error('[vd-excel-refresh]', error);
        _setRefreshStatus('⚠️ Không ghi được dữ liệu vào workbook: ' + (error.message || error), 'err');
    }

    button.disabled = false;
    button.textContent = '↻ Refresh toàn bộ workbook';
}

function _setRefreshStatus(message, cls) {
    var element = document.getElementById('refresh-status');
    element.textContent = message;
    element.className = 'status-msg ' + (cls || '');
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
