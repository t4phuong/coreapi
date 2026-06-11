# T4 Core API (`t4_coreapi`)

Secure API gateway for external devices and services on Odoo 19.

## Purpose (Mục đích)

| Capability | Description |
|------------|-------------|
| **Connection management** | Register external devices/services, issue Client ID/Secret |
| **Token management** | OAuth2-style access tokens with TTL, revoke, auto-expiry |
| **Authentication** | Client credentials + Bearer token gatekeeper |
| **API access control** | Per-device allowed endpoint catalog |
| **DDoS protection** | Per-device rate limits + per-IP auth throttle |
| **Audit** | Full request/auth log (route, IP, status, duration) |

---

## Requirements coverage

| Requirement | Status |
|-------------|--------|
| Cấp và quản lý token – thiết bị ngoài | Done |
| Quản lý, kiểm soát, xác thực | Done |
| Kiểm soát API call theo thiết bị | Done |
| Kiểm soát DDoS (rate limit) | Done |
| IP allowlist | Done |
| Audit log | Done |

---

## Architecture — Main server + branch controllers (tree)

```
                    ┌─────────────────────────────┐
                    │   MAIN SERVER (Odoo HQ)      │
                    │   Module: t4_coreapi         │
                    │   - Register devices         │
                    │   - Issue tokens             │
                    │   - Validate + accept data   │
                    └──────────────┬──────────────┘
                                   │ HTTPS API
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌────────▼────────┐          ...
    │ Branch Controller │ │ Branch Controller│
    │ (core.api.device) │ │ (core.api.device)│
    │ Client ID/Secret  │ │ Client ID/Secret │
    └─────────┬─────────┘ └────────┬────────┘
              │                    │
     ┌────────┼────────┐          ...
     │        │        │
  Device   Device   Device   (local POS / IoT — do NOT call HQ directly)
```

**How it works**

1. Admin registers each **branch controller** on the main server as one **API Device**.
2. Controller calls `POST /api/v1/auth/token` with its Client ID/Secret → gets **access_token**.
3. Controller sends data to main server: `POST /api/v1/orders?db=...` with `Authorization: Bearer <access_token>`.
4. Main server **gatekeeper** checks:
   - Token valid and not revoked?
   - Device active?
   - IP allowed? Rate limit OK?
   - Device allowed to call this API endpoint?
5. If all pass → accept data. Otherwise → `401` / `403` / `429`.

> Register **one device per branch controller**, not per small POS terminal. The controller forwards data on behalf of its local devices.

### Request flow

```
Branch Controller                          Main Server
      │                                         │
      │  (1) POST /api/v1/auth/token?db=...     │
      │      client_id + client_secret          │
      │ ───────────────────────────────────────►│  Verify device credentials
      │◄─────────────────────────────────────── │  Return access_token
      │                                         │
      │  (2) POST /api/v1/orders?db=...         │
      │      Bearer <access_token> + JSON body  │
      │ ───────────────────────────────────────►│  Validate token → device → permission
      │◄─────────────────────────────────────── │  Accept or reject
```

### Credential layers

| Layer | Purpose | Lifetime |
|-------|---------|----------|
| **Client ID** | Device identity | Permanent |
| **Client Secret** | Device password | Permanent (rotate via Regenerate Secret) |
| **Access Token** | API calls | Token TTL hours (default 24h) |

---

## Install

1. **Apps** → Update Apps List
2. Install / Upgrade **T4 Core API**
3. **Restart Odoo service** after code changes (Windows: `Restart-Service odoo-server-19.0`)

---

## Odoo admin setup

### 1. Review API catalog

**Core API → API Endpoints**

| Code | Route | Use case |
|------|-------|----------|
| `health` | `/api/v1/health` | Connectivity test |
| `orders` | `/api/v1/orders` | Order APIs |
| `hr` | `/api/v1/hr` | HR APIs |

### 2. Create a device

**Core API → Devices → New**

| Field | Example | Notes |
|-------|---------|-------|
| Name | `POS Terminal 1` | Required |
| Token TTL (hours) | `24` | Access token lifetime |
| Allowed APIs | Health Check | Required for testing |
| API Rate Limit (/min) | `60` | Max API calls/min (0 = unlimited) |
| Auth Rate Limit (/min) | `10` | Max token requests/min |
| Allowed IPs | *(empty)* | One IP/CIDR per line; empty = any |

Click **Save** → **Regenerate Secret** → copy **Client ID** and **Client Secret** using the **copy icon** next to each field in the popup.

> Client ID/Secret are auto-generated. You cannot type them manually.  
> **Client Secret is NOT the same as Client ID** — it is a longer random string shown only in the popup.

### 3. Buttons on device form

| Button | Action |
|--------|--------|
| **View Credentials** | Show Client ID/Secret once after create |
| **Regenerate Secret** | New secret (invalidates old one) |
| **Revoke Token** | Invalidate current access token immediately |
| **Tokens** (stat) | List issued tokens |
| **Logs** (stat) | Request/auth audit for this device |

---

## Multi-database note

If your Odoo server has **multiple databases**, every API call must specify the database:

- Query string: `?db=t4_coreapi`
- Or header: `X-Odoo-Database: t4_coreapi`

---

## Postman guide

### Environment variables

| Variable | Example |
|----------|---------|
| `base_url` | `http://localhost:8069` |
| `db` | `t4_coreapi` |
| `client_id` | `dev_a1b2c3...` |
| `client_secret` | `from-credentials-popup` |
| `access_token` | *(set by script)* |

### Request 1 — Get access token

```
POST {{base_url}}/api/v1/auth/token?db={{db}}
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "{{client_id}}",
  "client_secret": "{{client_secret}}"
}
```

**Tests script:**
```javascript
if (pm.response.code === 200) {
    pm.environment.set("access_token", pm.response.json().access_token);
}
```

**Expected:** `200` with `access_token`, `token_type`, `expires_in`

| Error | Cause |
|-------|-------|
| `404` | Missing `?db=` |
| `401` | Wrong client_secret (must differ from client_id) |
| `403` | IP not in allowlist |
| `429` | Auth rate limit exceeded |

### Request 2 — Health check

> **Important:** Always add `?db={{db}}` to the URL. Without it you get `404 No database is selected`.  
> Use **`access_token`** from Request 1 in Bearer — NOT the client_secret.

```
GET {{base_url}}/api/v1/health?db={{db}}
Authorization: Bearer {{access_token}}
```

**Expected:** `200` — `{"status": "ok", ...}`

### Request 3 — Permission denied test

Call `GET /api/v1/hr/employees` without **HR** in Allowed APIs.

**Expected:** `403 Forbidden`

### Request 4 — Revoke token test

1. Odoo → device → **Revoke Token**
2. Repeat Request 2 with same token → `401`
3. Repeat Request 1 → new token works

### Request 5 — Rate limit test

Set **Auth Rate Limit** to `3`, call Request 1 more than 3 times in one minute.

**Expected:** `429 Too Many Requests`

---

## PowerShell quick test

```powershell
$db = "t4_coreapi"

# 1. Get token
$body = @{
    grant_type    = "client_credentials"
    client_id     = "YOUR_CLIENT_ID"
    client_secret = "YOUR_CLIENT_SECRET"
} | ConvertTo-Json

$token = Invoke-RestMethod `
    -Uri "http://localhost:8069/api/v1/auth/token?db=$db" `
    -Method POST -Body $body -ContentType "application/json"

# 2. Health check
Invoke-RestMethod `
    -Uri "http://localhost:8069/api/v1/health?db=$db" `
    -Headers @{ Authorization = "Bearer $($token.access_token)" }
```

---

## Security features

### Rate limiting (DDoS)

| Scope | Default | Config field |
|-------|---------|--------------|
| API calls per device | 60/min | `rate_limit_per_minute` |
| Token requests per device | 10/min | `auth_rate_limit_per_minute` |
| Token requests per IP (unknown device) | 30/min | Global (code constant) |

Set limit to `0` for unlimited.

### IP allowlist

On device form → **Allowed IPs** — one entry per line:

```
203.0.113.10
198.51.100.0/24
```

Empty = allow all IPs.

### Audit log

**Core API → Request Logs** — every auth and API call:

- Device, route, method, IP, status code, success, duration (ms), errors

Logs older than 90 days are auto-deleted (autovacuum).

---

## Built-in API endpoints

| Method | Path | Auth | Permission |
|--------|------|------|------------|
| `POST` | `/api/v1/auth/token` | None | — |
| `GET` | `/api/v1/health` | Bearer | `health` |
| `GET` | `/api/v1/orders` | Bearer | `orders` |
| `GET` | `/api/v1/hr/employees` | Bearer | `hr` |

---

## Extend in other modules

```python
from odoo import http
from odoo.addons.t4_coreapi.controllers.main import CoreApiController
from odoo.addons.t4_coreapi.utils.decorators import validate_core_api
from odoo.addons.t4_coreapi.utils.logging import log_core_api

class MyApiController(CoreApiController):

    @http.route('/api/v1/partners', type='http',
                auth='core_api', methods=['GET'], csrf=False, save_session=False)
    @validate_core_api('partners')
    @log_core_api('api')
    def list_partners(self, **kw):
        ...
```

1. Add `core.api.endpoint` record (`code=partners`, route pattern)
2. Assign endpoint to devices that should access it

---

## Module structure

```
t4_coreapi/
├── models/
│   ├── core_api_device.py      # Devices + security settings
│   ├── core_api_token.py       # Access tokens
│   ├── core_api_endpoint.py    # API catalog
│   ├── core_api_log.py         # Audit log
│   └── ir_http.py              # Bearer auth gatekeeper
├── controllers/
│   ├── auth.py                 # POST /api/v1/auth/token
│   └── main.py                 # Demo protected routes
├── utils/
│   ├── decorators.py           # @validate_core_api
│   ├── security.py             # IP + rate limit helpers
│   └── logging.py              # @log_core_api
└── hooks.py                      # ?db= support (multi-database)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cannot save device — missing Client | Upgrade module; Client ID is auto-generated on save |
| `404` on API | Add `?db=your_database` |
| `401 Invalid credentials` | Use secret from popup, not client_id |
| `403` on health | Add Health Check to Allowed APIs |
| `429` | Wait 1 minute or increase rate limits |
| Changes not applied | Restart Odoo service + upgrade module |

---

## License

LGPL-3
