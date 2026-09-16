const NFL_USAGE_CSV_URL =
  'https://raw.githubusercontent.com/thedirtymike/NFL-Usage/main/redzone_usage.csv';
const SPREADSHEET_ID = '1rhr56JhDE31GxeNSu8OakiIQsZbfmcM8vOrRDIISoMA';
const SHEET_NAME = 'Redzone_usage';

function updateRedzoneUsage() {
  const response = UrlFetchApp.fetch(NFL_USAGE_CSV_URL);
  const rows = Utilities.parseCsv(response.getContentText());
  if (rows.length < 2) {
    throw new Error('The redzone_usage.csv file did not contain any data rows.');
  }

  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = spreadsheet.getSheetByName(SHEET_NAME) ||
    spreadsheet.insertSheet(SHEET_NAME);

  sheet.clearContents();
  sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, rows[0].length).setFontWeight('bold');
  sheet.autoResizeColumns(1, rows[0].length);
}
