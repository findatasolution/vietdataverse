import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outputPath = new URL('./Viet-Dataverse-Google-Sheets-Template.xlsx', import.meta.url);
const workbook = Workbook.create();
const cover = workbook.worksheets.add('Bắt đầu');

cover.getRange('B2:C2').merge();
cover.getRange('B2').values = [['Viet Dataverse — Dữ liệu kinh tế Việt Nam']];
cover.getRange('B3:C3').merge();
cover.getRange('B3').values = [['Google Sheets có thể refresh 9 bộ dữ liệu bằng menu Viet Dataverse.']];
cover.getRange('B5:C5').merge();
cover.getRange('B5').values = [['REFRESH TRONG GOOGLE SHEETS']];
cover.getRange('B7:C10').values = [
  ['Bước 1', 'Mở menu Viet Dataverse → Thiết lập API key.'],
  ['Bước 2', 'Cấp quyền một lần, sau đó nhập API key và chọn khoảng thời gian.'],
  ['Bước 3', 'Bấm Refresh toàn bộ dữ liệu bất cứ khi nào cần cập nhật.'],
  ['Bảo mật', 'API key được lưu theo tài khoản Google và không nằm trong ô của file.'],
];
cover.getRange('B12:C14').values = [
  ['Khoảng thời gian', '1 năm'],
  ['Cập nhật gần nhất', 'Chưa refresh'],
  ['Trạng thái', 'Chưa kết nối'],
];
cover.getRange('B2:C12').format.font = {name: 'Arial', size: 11, color: '#141413'};
cover.getRange('B2').format.font = {name: 'Georgia', size: 18, bold: true, color: '#141413'};
cover.getRange('B3').format.font = {name: 'Arial', size: 11, color: '#5e5d59'};
cover.getRange('B5').format = {
  fill: '#eef2ff',
  font: {name: 'Arial', size: 12, bold: true, color: '#2f5fde'},
};
cover.getRange('B7:B10').format.font = {name: 'Arial', size: 11, bold: true, color: '#141413'};
cover.getRange('B12:C14').format = {
  fill: '#f6f7fb',
  font: {name: 'Arial', size: 11, bold: true, color: '#5e5d59'},
};
cover.getRange('A1:D16').format.rowHeight = 24;
cover.getRange('B:B').format.columnWidth = 18;
cover.getRange('C:C').format.columnWidth = 72;

const datasets = [
  ['Vàng SJC', 'Giá vàng SJC mua vào / bán ra theo ngày'],
  ['Bạc', 'Giá bạc Phú Quý theo ngày'],
  ['Lãi suất LNH', 'Lãi suất liên ngân hàng + lãi suất điều hành SBV'],
  ['Tỷ giá', 'Tỷ giá trung tâm USD/VND'],
  ['Tiền gửi ACB', 'Lãi suất tiền gửi theo kỳ hạn'],
  ['Thế giới', 'Vàng, bạc, NASDAQ thế giới'],
  ['CPI', 'Chỉ số giá tiêu dùng theo tháng'],
  ['GDP', 'GDP theo quý và khu vực'],
  ['Xuất nhập khẩu', 'Kim ngạch xuất nhập khẩu theo tháng'],
];

for (const [name, description] of datasets) {
  const sheet = workbook.worksheets.add(name);
  sheet.getRange('A1:B2').values = [
    ['Trạng thái', 'Chưa refresh'],
    ['Nội dung', description],
  ];
  sheet.getRange('A1:B2').format.font = {name: 'Arial', size: 10, color: '#5e5d59'};
  sheet.getRange('A1:A2').format.font = {name: 'Arial', size: 10, bold: true, color: '#141413'};
  sheet.getRange('A:A').format.columnWidth = 18;
  sheet.getRange('B:B').format.columnWidth = 60;
}

workbook.recalculate();
const inspection = await workbook.inspect({
  kind: 'sheet,region',
  sheetId: 'Bắt đầu',
  range: 'B2:C12',
  maxChars: 4000,
});
console.log(inspection.ndjson);
const preview = await workbook.render({
  sheetName: 'Bắt đầu',
  range: 'A1:D16',
  autoCrop: 'all',
  scale: 1.5,
  format: 'png',
});
await fs.writeFile(
  '/tmp/vdv-google-sheets-template-preview.png',
  new Uint8Array(await preview.arrayBuffer()),
);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath.pathname);
await fs.access(outputPath);
console.log(outputPath.pathname);
