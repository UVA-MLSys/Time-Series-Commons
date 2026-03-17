# Google Sheets → SQL Auto-Sync

Whenever the Google Sheet is edited, a Google Apps Script trigger automatically
mirrors its full contents into Cloud SQL, which then propagates through the
existing pipeline to update the live site.

```
Google Sheets edit
  → Apps Script onChange → POST CSV to VM:8081/ingest-from-sheets
  → upsert all rows + delete orphaned rows
  → rebuild data/models.json + git push
  → GitHub Pages redeploys (~1–3 min lag)
```

---

## Deployment checklist

### Step 1 — Generate a webhook secret and add it to the VM

**Why:** The `/ingest-from-sheets` endpoint is exposed to the internet (so that
Google's servers can reach it). A shared secret token prevents anyone else from
hitting the endpoint and modifying your database. Every request from Apps Script
includes `Authorization: Bearer <secret>`, and the server rejects anything that
doesn't match.

**How:**

SSH into your GCP VM, then run:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

This prints a 64-character random hex string, for example:
`a3f1b2c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1`

Copy that value, then open the updater's `.env` file:

```bash
nano /home/ryangoudjil/Time-Series-Commons/server/updater/.env
```

Add this line (replacing the example with your actual generated value):

```
WEBHOOK_SECRET=a3f1b2c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1
```

Save the file, then restart the updater service so it reads the new variable:

```bash
sudo systemctl restart timeseries-updater
```

Verify it came back up cleanly:

```bash
sudo systemctl status timeseries-updater
```

You should see `Active: active (running)`.

---

### Step 2 — Open port 8081 in the GCP firewall

**Why:** Your VM runs behind GCP's VPC firewall, which blocks all inbound traffic
by default except for ports you explicitly allow. The updater service listens on
port 8081, but right now that port is only reachable from within the VM itself
(localhost). For Apps Script (running on Google's servers) to POST data to the
VM, port 8081 needs to be open to inbound internet traffic.

**How (GCP Console):**

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Navigate to **VPC network → Firewall rules → Create firewall rule**.
3. Fill in these fields:

| Field            | Value                        |
|------------------|------------------------------|
| Name             | `allow-sheets-webhook`       |
| Direction        | Ingress                      |
| Action on match  | Allow                        |
| Targets          | All instances in the network |
| Source IP ranges | `0.0.0.0/0`                  |
| Protocols/ports  | TCP, port `8081`             |

4. Click **Create**.

**How (gcloud CLI, if you prefer):**

Run this from any terminal where you have `gcloud` authenticated:

```bash
gcloud compute firewall-rules create allow-sheets-webhook \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:8081 \
  --source-ranges=0.0.0.0/0
```

**Optional hardening:** Instead of `0.0.0.0/0` (all IPs), you can restrict the
source range to Google's IP addresses only, so only Google's servers can reach
the port. Download the current list from
`https://www.gstatic.com/ipranges/goog.json` and use those CIDR ranges. This is
extra protection but is not strictly required since the bearer token already
authenticates every request.

**Verify it worked** by hitting the health check from your local machine:

```bash
curl http://<VM_EXTERNAL_IP>:8081/
# Expected: {"repo": "...", "status": "running"}
```

---

### Step 3 — Set up Apps Script in the Google Sheet

**Why:** Google Apps Script is a JavaScript environment that runs inside Google
Workspace. You'll add a small script to the spreadsheet that exports its own
CSV content and POSTs it to your VM whenever the sheet changes. This is the
"push notification" that triggers the sync.

**How:**

1. Open the Google Sheet.
2. Click **Extensions → Apps Script**. A new browser tab opens with a code editor.
3. Delete any placeholder code in the editor.
4. Open `apps-script.js` from this directory and paste its entire contents into
   the editor.
5. At the top of the pasted script, fill in your two configuration values:

   ```javascript
   var VM_IP          = '34.11.116.241';   // your VM's external IP (find it in GCP Console → VM instances)
   var WEBHOOK_SECRET = 'a3f1b2...';       // the secret you generated in Step 1
   ```

6. Click the **Save** icon (or Ctrl+S / Cmd+S). Name the project anything you
   like, e.g. `TimeSeries DB Sync`.

**Finding your VM's external IP:** In the GCP Console go to
**Compute Engine → VM instances**. The `External IP` column shows the public IP.

---

### Step 4 — Initial full sync (one-time)

**Why:** The current database is out of date — it was seeded from an older
version of the CSV and doesn't reflect recent changes to the sheet. Before the
automatic trigger takes over, you need to run one full sync to bring the
database in line with the current sheet. This uses the exact same
`/ingest-from-sheets` endpoint and does a full mirror: every row in the sheet is
upserted into SQL, and any rows in SQL that no longer exist in the sheet are
deleted.

**How:**

In the Apps Script editor (from Step 3), make sure `syncToDatabase` is selected
in the function dropdown at the top of the toolbar, then click **Run ▶**.

Google will ask you to authorize the script the first time — click through the
permission prompts (the script needs access to the spreadsheet and to make
external HTTP requests).

After it runs, check the **Execution log** panel at the bottom. You should see
something like:

```
[syncToDatabase] Response 200: {"status": "ok", "upserted": 832, "deleted": 14}
```

The numbers tell you how many rows were upserted (all rows currently in the
sheet) and how many stale rows were deleted from SQL. The database and live site
are now in sync with the sheet.

If you see a non-200 response or an error, double-check:
- `VM_IP` and `WEBHOOK_SECRET` are correct in the script
- The firewall port is open (Step 2 check above)
- The updater service is running (`sudo systemctl status timeseries-updater`)

---

### Step 5 — Add the installable onChange trigger

**Why:** The manual run in Step 4 was a one-off. To make the sync happen
automatically on every future edit, you need to register an "installable trigger"
that tells Apps Script to call `syncToDatabase` whenever the spreadsheet changes.
This is different from a simple `onEdit` function — an installable trigger runs
with your authorization (so it can make external HTTP calls), and it fires on
*any* change type: cell edits, row insertions, row deletions, paste operations,
and so on.

**How:**

1. In the Apps Script editor, click the **clock icon** (Triggers) in the left
   sidebar, or go to **Edit → Current project's triggers**.
2. Click **+ Add Trigger** (bottom-right corner).
3. Fill in:

| Setting                        | Value                |
|--------------------------------|----------------------|
| Choose which function to run   | `syncToDatabase`     |
| Choose which deployment to run | Head                 |
| Select event source            | From spreadsheet     |
| Select event type              | On change            |
| Failure notification           | Notify me daily *(optional)* |

4. Click **Save**.

From this point on, every change to the spreadsheet automatically calls
`syncToDatabase`, which exports the sheet as CSV, POSTs it to the VM, and the
full pipeline runs: SQL is updated, `models.json` is rebuilt, and the site
redeploys within ~1–3 minutes.

---

## Endpoint reference

`POST http://<VM_IP>:8081/ingest-from-sheets`

| Header          | Value                     |
|-----------------|---------------------------|
| Authorization   | `Bearer <WEBHOOK_SECRET>` |
| Content-Type    | `text/csv`                |

Body: full CSV export of the sheet (same column layout as the source spreadsheet).

Response:
```json
{"status": "ok", "upserted": 820, "deleted": 3}
```

**Trigger manually from the VM** (useful for testing without Apps Script):
```bash
# Export the sheet to a local CSV first, then:
curl -X POST http://127.0.0.1:8081/ingest-from-sheets \
  -H "Authorization: Bearer <WEBHOOK_SECRET>" \
  -H "Content-Type: text/csv" \
  --data-binary @/path/to/export.csv
```

**Check the updater logs** on the VM if something seems wrong:
```bash
sudo journalctl -u timeseries-updater -f
```
