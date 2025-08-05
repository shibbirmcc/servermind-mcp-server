# Splunk Local Setup for Log Ingestion (Free Tier)

## 📌 Background

Splunk Enterprise Free Tier **does not support cloud-based ingestion** — it only accepts logs **locally**. For our use case (MCP log analysis), this is sufficient.

There are two ways to run Splunk locally:

* **Recommended:** Docker (leaner, easier to manage and reset)
* **Alternative:** Native desktop install (not tested)

---

## ✅ Option 1: Docker Setup (Recommended for Mac)

### Step 1: Start the Splunk container

Run this in your terminal:

```bash
docker run -d \
  --platform linux/amd64 \
  --name splunk \
  -p 8000:8000 \
  -p 8088:8088 \
  -p 8089:8089 \
  -e SPLUNK_START_ARGS="--accept-license" \
  -e SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
  -e SPLUNK_PASSWORD="changeme" \
  splunk/splunk:latest
```

* The `--platform linux/amd64` flag is needed for Apple Silicon (M1/M2/M3/M4).
* The container usually takes **\~4 minutes** to become healthy on first boot.

> 🔍 Check container status with `docker ps`. Wait until the `STATUS` shows `healthy`.

---

### Step 2: Access the Splunk UI

Once the container is healthy, open:

👉 [http://localhost:8000](http://localhost:8000)

Login with:

* **Username:** `admin`
* **Password:** `changeme` (or whatever you set in `SPLUNK_PASSWORD`)

---

### Step 3: Enable HTTP Event Collector (HEC)

1. Go to **Settings > Data Inputs**
2. Select **HTTP Event Collector**
3. Click **"New Token"**
4. Name it something like `mcp-logs`
5. Use the default index (e.g. `main`)
6. Click **Save**
7. Copy the generated **token**

---

### Step 4: Send Logs from Your Services

You can now send logs via HTTP POST:

```http
POST http://localhost:8088/services/collector
Headers:
  Authorization: Splunk <your-token>
Body:
{
  "event": "something bad happened",
  "sourcetype": "manual"
}
```

---

## 🔮 Option 2: Desktop Install (Not Tested)

If you prefer to install Splunk directly on your machine:

* Download from: [https://www.splunk.com/en\_us/download/splunk-enterprise.html](https://www.splunk.com/en_us/download/splunk-enterprise.html)

> ⚠️ This method was **not tested by us**. Docker is the recommended and tested path.

---

