const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'integrations/google-sheets/Code.gs'), 'utf8');
const store = new Map();
const requests = [];

function chain() { return this; }
function makeRange() {
  return {
    clearContent: chain, setValues: chain, setValue: chain, setBackground: chain,
    setFontColor: chain, setFontWeight: chain, setFontSize: chain, setNumberFormat: chain,
  };
}
function makeSheet(name) {
  return {
    name,
    getLastRow() { return 0; }, getLastColumn() { return 0; },
    getMaxRows() { return 1000; }, getMaxColumns() { return 26; },
    getRange() { return makeRange(); }, setFrozenRows: chain, autoResizeColumns: chain,
    setHiddenGridlines: chain, setColumnWidth: chain,
    insertRowsAfter: chain, insertColumnsAfter: chain,
  };
}
const sheets = new Map([['Bắt đầu', makeSheet('Bắt đầu')]]);
const spreadsheet = {
  getSheetByName(name) { return sheets.get(name) || null; },
  insertSheet(name) { const sheet = makeSheet(name); sheets.set(name, sheet); return sheet; },
  toast() {},
};
const datasets = Array.from({length: 9}, (_, index) => ({
  id: `dataset-${index}`,
  sheet: `Dữ liệu ${index}`,
  headers: ['date', 'value'],
  rows: [['2026-09-25', index]],
  error: null,
}));

const context = {
  Array, Boolean, Date, Error, JSON, String, encodeURIComponent,
  PropertiesService: {getUserProperties() { return {
    getProperty(key) { return store.get(key) || null; },
    setProperty(key, value) { store.set(key, value); return this; },
    deleteProperty(key) { store.delete(key); return this; },
  }; }},
  SpreadsheetApp: {
    getActive() { return spreadsheet; }, flush() {},
    getUi() { return {createMenu() { return {addItem: chain, addSeparator: chain, addToUi: chain}; }}; },
  },
  LockService: {getDocumentLock() { return {tryLock() { return true; }, releaseLock() {}}; }},
  UrlFetchApp: {fetch(url, options) {
    requests.push({url, options});
    const payload = url.includes('/verify-key')
      ? {valid: true}
      : {success: true, period: '1y', data: datasets};
    return {getResponseCode() { return 200; }, getContentText() { return JSON.stringify(payload); }};
  }},
};
vm.createContext(context);
vm.runInContext(source, context);

context.saveSettings('secret-test-key', '1y');
const result = context.refreshAllData();

assert.equal(result.updated, 9);
assert.equal(result.failures.length, 0);
assert.equal(sheets.size, 10);
assert.equal(requests.length, 2);
assert.equal(requests[0].options.headers['X-API-Key'], 'secret-test-key');
assert.equal(requests[1].options.headers['X-API-Key'], 'secret-test-key');
assert.doesNotMatch(requests[1].url, /secret-test-key/);
assert.doesNotMatch(source, /HtmlService|Sidebar\.html/);
assert.equal(context.safeCell_('=IMPORTXML("x")'), "'=IMPORTXML(\"x\")");
assert.equal(context.normalizePeriod_('bad'), '1y');

const manifest = JSON.parse(fs.readFileSync(path.join(root, 'integrations/google-sheets/appsscript.json'), 'utf8'));
assert.deepEqual(manifest.oauthScopes, [
  'https://www.googleapis.com/auth/spreadsheets.currentonly',
  'https://www.googleapis.com/auth/script.external_request',
]);

console.log('PASS: Google Sheets connector stores the key per user and refreshes nine tabs in one call.');
