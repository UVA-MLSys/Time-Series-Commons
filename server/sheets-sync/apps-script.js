/**
 * Time Series Commons — Google Sheets → SQL Sync
 *
 * Setup instructions
 * ------------------
 * 1. Open the Google Sheet.
 * 2. Go to Extensions → Apps Script and paste this entire file.
 * 3. Fill in VM_IP and WEBHOOK_SECRET below.
 * 4. Click "Save", then run syncToDatabase() once manually via Run → syncToDatabase
 *    to perform the initial full sync (brings the DB in line with the current sheet).
 * 5. Add an installable trigger:
 *      Triggers (clock icon) → + Add Trigger
 *        Function:        syncToDatabase
 *        Event source:    From spreadsheet
 *        Event type:      On change
 *    This fires automatically on every subsequent edit, row insertion, or deletion.
 *
 * How it works
 * ------------
 * On each trigger fire the script:
 *   a) Exports the active sheet as CSV via the Sheets export URL.
 *   b) POSTs the CSV to the VM's /ingest-from-sheets endpoint.
 *   c) The endpoint upserts all rows, deletes orphaned rows, rebuilds
 *      data/models.json, and pushes to GitHub — updating the live site.
 */

// ---------------------------------------------------------------------------
// Configuration — fill these in before saving
// ---------------------------------------------------------------------------
var VM_IP         = '<YOUR_VM_EXTERNAL_IP>';   // e.g. '34.11.116.241'
var WEBHOOK_SECRET = '<YOUR_WEBHOOK_SECRET>';   // value from server/updater/.env

var ENDPOINT = 'http://' + VM_IP + ':8081/ingest-from-sheets';

// ---------------------------------------------------------------------------
// Main sync function
// ---------------------------------------------------------------------------
function syncToDatabase() {
  // Debounce: if another execution is already running, skip this one.
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) {
    Logger.log('[syncToDatabase] Skipped — another run is in progress.');
    return;
  }

  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheets()[0];  // adjust index if your data is on a different tab

    // Export the sheet as CSV using the Sheets built-in export URL.
    // ScriptApp.getOAuthToken() authenticates the fetch as the script owner.
    var csvUrl = 'https://docs.google.com/spreadsheets/d/' + ss.getId()
               + '/export?format=csv&gid=' + sheet.getSheetId();

    var csvResponse = UrlFetchApp.fetch(csvUrl, {
      headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
      muteHttpExceptions: true
    });

    if (csvResponse.getResponseCode() !== 200) {
      Logger.log('[syncToDatabase] Failed to export CSV: ' + csvResponse.getContentText());
      return;
    }

    var csv = csvResponse.getContentText();

    // POST the CSV to the VM endpoint.
    var response = UrlFetchApp.fetch(ENDPOINT, {
      method:      'post',
      contentType: 'text/csv',
      headers:     { Authorization: 'Bearer ' + WEBHOOK_SECRET },
      payload:     csv,
      muteHttpExceptions: true
    });

    var code = response.getResponseCode();
    var body = response.getContentText();
    Logger.log('[syncToDatabase] Response ' + code + ': ' + body);

    if (code !== 200) {
      Logger.log('[syncToDatabase] WARNING: endpoint returned non-200 status.');
    }
  } catch (e) {
    Logger.log('[syncToDatabase] Error: ' + e.toString());
  } finally {
    lock.releaseLock();
  }
}
