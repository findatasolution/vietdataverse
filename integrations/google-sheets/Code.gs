/**
 * @OnlyCurrentDoc
 * Viet Dataverse Google Sheets connector.
 *
 * The API key is stored in UserProperties, so it is not written to cells or
 * shared with other editors. Refresh uses one API request for all datasets.
 */

var VDV_API_BASE = 'https://api.vietdataverse.online/api/v1';
var VDV_KEY_PROPERTY = 'VDV_API_KEY';
var VDV_PERIOD_PROPERTY = 'VDV_PERIOD';
var VDV_DEFAULT_PERIOD = '1y';
var VDV_ALLOWED_PERIODS = ['7d', '1m', '1y', 'all'];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Viet Dataverse')
    .addItem('Thiết lập API key', 'setupConnection')
    .addItem('Refresh toàn bộ dữ liệu', 'refreshAllData')
    .addSeparator()
    .addItem('Xóa API key đã lưu', 'clearApiKey')
    .addToUi();
}

function onInstall() {
  onOpen();
}

function setupConnection() {
  var ui = SpreadsheetApp.getUi();
  var keyResponse = ui.prompt(
    'Thiết lập Viet Dataverse',
    'Dán API key của bạn. Key được lưu riêng cho tài khoản Google và không ghi vào ô của file.',
    ui.ButtonSet.OK_CANCEL
  );
  if (keyResponse.getSelectedButton() !== ui.Button.OK) return;

  var apiKey = keyResponse.getResponseText().trim();
  if (!apiKey) {
    ui.alert('Hãy nhập API key.');
    return;
  }

  var periodResponse = ui.prompt(
    'Khoảng thời gian',
    'Nhập một trong các giá trị: 7d, 1m, 1y hoặc all. Để trống sẽ dùng 1y.',
    ui.ButtonSet.OK_CANCEL
  );
  if (periodResponse.getSelectedButton() !== ui.Button.OK) return;

  try {
    saveSettings(apiKey, periodResponse.getResponseText().trim() || VDV_DEFAULT_PERIOD);
    var refreshNow = ui.alert(
      'Đã lưu kết nối',
      'API key hợp lệ. Refresh toàn bộ dữ liệu ngay bây giờ?',
      ui.ButtonSet.YES_NO
    );
    if (refreshNow === ui.Button.YES) refreshAllData();
  } catch (error) {
    ui.alert('Không lưu được kết nối', error.message || String(error), ui.ButtonSet.OK);
  }
}

function getSettings() {
  var properties = PropertiesService.getUserProperties();
  return {
    hasApiKey: Boolean(properties.getProperty(VDV_KEY_PROPERTY)),
    period: normalizePeriod_(properties.getProperty(VDV_PERIOD_PROPERTY)),
  };
}

function saveSettings(apiKey, period) {
  var key = String(apiKey || '').trim();
  var normalizedPeriod = normalizePeriod_(period);
  if (!key) {
    throw new Error('Hãy nhập API key.');
  }

  verifyApiKey_(key);
  var properties = PropertiesService.getUserProperties();
  properties.setProperty(VDV_KEY_PROPERTY, key);
  properties.setProperty(VDV_PERIOD_PROPERTY, normalizedPeriod);
  return {ok: true, period: normalizedPeriod};
}

function updatePeriod(period) {
  var normalizedPeriod = normalizePeriod_(period);
  PropertiesService.getUserProperties()
    .setProperty(VDV_PERIOD_PROPERTY, normalizedPeriod);
  return {ok: true, period: normalizedPeriod};
}

function clearApiKey() {
  PropertiesService.getUserProperties().deleteProperty(VDV_KEY_PROPERTY);
  SpreadsheetApp.getActive().toast(
    'Đã xóa API key lưu cho tài khoản Google này.',
    'Viet Dataverse',
    5
  );
}

function refreshAllData() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(5000)) {
    throw new Error('File đang được refresh ở cửa sổ khác. Hãy thử lại sau.');
  }

  try {
    var properties = PropertiesService.getUserProperties();
    var apiKey = properties.getProperty(VDV_KEY_PROPERTY);
    var period = normalizePeriod_(properties.getProperty(VDV_PERIOD_PROPERTY));
    if (!apiKey) {
      SpreadsheetApp.getUi().alert(
        'Chưa có API key',
        'Mở menu Viet Dataverse → Thiết lập API key trước khi refresh.',
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return {ok: false, updated: 0, failures: []};
    }

    var spreadsheet = SpreadsheetApp.getActive();
    spreadsheet.toast('Đang tải 9 bộ dữ liệu...', 'Viet Dataverse', -1);
    var payload = fetchJson_(
      VDV_API_BASE + '/excel/refresh-data?period=' + encodeURIComponent(period),
      apiKey
    );
    if (!payload || !Array.isArray(payload.data)) {
      throw new Error('Phản hồi API không đúng định dạng.');
    }

    var updated = 0;
    var failures = [];
    payload.data.forEach(function (item) {
      if (item.error || !item.headers || !item.headers.length) {
        failures.push(item.sheet || item.id || 'Không rõ');
        return;
      }
      writeDataset_(spreadsheet, item);
      updated += 1;
    });
    updateCover_(spreadsheet, payload, updated, failures);
    SpreadsheetApp.flush();

    var message = failures.length
      ? 'Đã cập nhật ' + updated + '/' + payload.data.length + ' bộ dữ liệu. Lỗi: ' + failures.join(', ')
      : 'Đã refresh ' + updated + ' bộ dữ liệu.';
    spreadsheet.toast(message, 'Viet Dataverse', 8);
    return {ok: failures.length === 0, updated: updated, failures: failures};
  } finally {
    lock.releaseLock();
  }
}

function verifyApiKey_(apiKey) {
  var result = fetchJson_(VDV_API_BASE + '/developer/verify-key', apiKey);
  if (!result.valid) {
    throw new Error('API key không hợp lệ hoặc đã hết hạn.');
  }
}

function fetchJson_(url, apiKey) {
  var response;
  try {
    response = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: {'X-API-Key': apiKey},
      muteHttpExceptions: true,
    });
  } catch (error) {
    throw new Error('Không kết nối được máy chủ Viet Dataverse.');
  }

  var status = response.getResponseCode();
  var body = response.getContentText();
  var payload = {};
  try {
    payload = JSON.parse(body || '{}');
  } catch (error) {
    throw new Error('Máy chủ trả về dữ liệu không đọc được.');
  }

  if (status >= 200 && status < 300) return payload;
  if (status === 401 || status === 403) {
    throw new Error('API key không hợp lệ hoặc đã hết hạn.');
  }
  if (status === 429) {
    throw new Error('Bạn đã dùng hết lượt API trong kỳ hiện tại.');
  }
  var detail = typeof payload.detail === 'string' ? payload.detail : 'Lỗi API ' + status;
  throw new Error(detail);
}

function writeDataset_(spreadsheet, item) {
  var sheet = spreadsheet.getSheetByName(item.sheet);
  if (!sheet) sheet = spreadsheet.insertSheet(item.sheet);

  var headers = item.headers.map(safeCell_);
  var rows = (item.rows || []).map(function (row) {
    return row.map(safeCell_);
  });
  var width = headers.length;
  var height = Math.max(1, rows.length + 1);
  ensureSheetSize_(sheet, height, width);

  var previousRows = Math.max(sheet.getLastRow(), height);
  var previousColumns = Math.max(sheet.getLastColumn(), width);
  if (previousRows && previousColumns) {
    sheet.getRange(1, 1, previousRows, previousColumns).clearContent();
  }

  sheet.getRange(1, 1, 1, width).setValues([headers]);
  if (rows.length) sheet.getRange(2, 1, rows.length, width).setValues(rows);

  var header = sheet.getRange(1, 1, 1, width);
  header
    .setBackground('#2f5fde')
    .setFontColor('#ffffff')
    .setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, width);
}

function updateCover_(spreadsheet, payload, updated, failures) {
  var cover = spreadsheet.getSheetByName('Bắt đầu');
  if (!cover) {
    cover = spreadsheet.insertSheet('Bắt đầu', 0);
    initializeCover_(cover);
  }
  cover.getRange('B12').setValue('Khoảng thời gian');
  cover.getRange('C12').setValue(payload.period || VDV_DEFAULT_PERIOD);
  cover.getRange('B13').setValue('Cập nhật gần nhất');
  cover.getRange('C13').setValue(new Date()).setNumberFormat('dd/MM/yyyy HH:mm');
  cover.getRange('B14').setValue('Trạng thái');
  cover.getRange('C14').setValue(
    failures.length ? 'Đã cập nhật ' + updated + ' bộ; lỗi ' + failures.length + ' bộ' : 'Đã cập nhật ' + updated + ' bộ dữ liệu'
  );
}

function initializeCover_(sheet) {
  sheet.setHiddenGridlines(true);
  sheet.getRange('B2').setValue('Viet Dataverse — Dữ liệu kinh tế Việt Nam')
    .setFontSize(16).setFontWeight('bold');
  sheet.getRange('B3').setValue('Dùng menu Viet Dataverse để thiết lập API key và refresh dữ liệu.');
  sheet.getRange('B5').setValue('REFRESH TRONG GOOGLE SHEETS')
    .setFontColor('#2f5fde').setFontWeight('bold');
  sheet.getRange('B7').setValue('Bước 1');
  sheet.getRange('C7').setValue('Mở menu Viet Dataverse → Thiết lập API key.');
  sheet.getRange('B8').setValue('Bước 2');
  sheet.getRange('C8').setValue('Cấp quyền một lần, sau đó nhập API key.');
  sheet.getRange('B9').setValue('Bước 3');
  sheet.getRange('C9').setValue('Bấm Refresh toàn bộ dữ liệu khi cần cập nhật.');
  sheet.setColumnWidth(2, 220);
  sheet.setColumnWidth(3, 520);
}

function ensureSheetSize_(sheet, rows, columns) {
  if (sheet.getMaxRows() < rows) {
    sheet.insertRowsAfter(sheet.getMaxRows(), rows - sheet.getMaxRows());
  }
  if (sheet.getMaxColumns() < columns) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), columns - sheet.getMaxColumns());
  }
}

function normalizePeriod_(period) {
  var value = String(period || VDV_DEFAULT_PERIOD);
  return VDV_ALLOWED_PERIODS.indexOf(value) >= 0 ? value : VDV_DEFAULT_PERIOD;
}

function safeCell_(value) {
  if (typeof value !== 'string') return value;
  return /^[=+@]/.test(value) ? "'" + value : value;
}
