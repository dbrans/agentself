# Gemini CLI OAuth Token Extraction & API Usage

This document captures learnings from reverse-engineering how `gemini-cli` authenticates with Google and makes API requests when using "Login with Google" OAuth authentication.

## Overview

When using OAuth authentication (not API key), `gemini-cli` uses a **private Code Assist API** (`cloudcode-pa.googleapis.com`), NOT the public Gemini API (`generativelanguage.googleapis.com`).

## Token Storage

### Location
```
~/.gemini/oauth_creds.json
```

### Format (plain JSON, not encrypted)
```json
{
  "access_token": "ya29.a0AUM...",
  "expiry_date": 1769159945362.7791,
  "scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email",
  "refresh_token": "1//05KZEt...",
  "token_type": "Bearer",
  "id_token": "eyJhbG..."
}
```

### Token Lifetime
- Access tokens are valid for **~1 hour** (3600 seconds)
- `expiry_date` is Unix epoch in **milliseconds**
- Use the `refresh_token` to get new access tokens

### Extracting the Token
```bash
ACCESS_TOKEN=$(jq -r '.access_token' ~/.gemini/oauth_creds.json)
```

### Checking Token Expiry
```bash
EXPIRY=$(jq -r '.expiry_date' ~/.gemini/oauth_creds.json)
EXPIRY_SEC=$(echo "$EXPIRY / 1000" | bc)
echo "Token expires: $(date -r $EXPIRY_SEC)"
echo "Valid for: $(( ($EXPIRY_SEC - $(date +%s)) / 60 )) minutes"
```

## Project ID (Critical!)

### Where It Comes From
The project ID is **NOT stored locally**. It is returned by the `loadCodeAssist` API call on every session:

```
POST https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist
```

Response includes:
```json
{
  "currentTier": { ... },
  "cloudaicompanionProject": "mystical-reporter-sjkxm"
}
```

### How to Get It
You must call `loadCodeAssist` first to retrieve your project ID:

```bash
ACCESS_TOKEN=$(jq -r '.access_token' ~/.gemini/oauth_creds.json)

curl -s "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "metadata": {
      "ideType": "IDE_UNSPECIFIED",
      "platform": "PLATFORM_UNSPECIFIED",
      "pluginType": "GEMINI"
    }
  }' | jq -r '.cloudaicompanionProject'
```

### Override via Environment Variable
You can set `GOOGLE_CLOUD_PROJECT` or `GOOGLE_CLOUD_PROJECT_ID` to use a specific project instead of the auto-assigned one.

## API Endpoints

### Correct Endpoint (Code Assist API)
```
https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse
```

### Wrong Endpoint (Public API - won't work with OAuth)
```
https://generativelanguage.googleapis.com/v1beta/models/...
```

The public API returns `ACCESS_TOKEN_TYPE_UNSUPPORTED` when using OAuth tokens because it expects API keys.

## Making API Requests

### Required Headers
```
Content-Type: application/json
Authorization: Bearer {access_token}
User-Agent: GeminiCLI/0.25.1/gemini-3-pro-preview (darwin; arm64)
x-goog-api-client: gl-node/25.3.0
```

### Request Body Format
```json
{
  "model": "gemini-3-flash-preview",
  "project": "mystical-reporter-sjkxm",
  "request": {
    "contents": [
      {
        "role": "user",
        "parts": [{"text": "Your prompt here"}]
      }
    ],
    "systemInstruction": {
      "role": "user",
      "parts": [{"text": "System prompt here"}]
    },
    "tools": []
  }
}
```

### Working curl Example
```bash
ACCESS_TOKEN=$(jq -r '.access_token' ~/.gemini/oauth_creds.json)
PROJECT="mystical-reporter-sjkxm"  # Get this from loadCodeAssist

curl -s "https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "User-Agent: GeminiCLI/0.25.1/gemini-3-pro-preview (darwin; arm64)" \
  -H "x-goog-api-client: gl-node/25.3.0" \
  -d '{
    "model": "gemini-3-flash-preview",
    "project": "'"$PROJECT"'",
    "request": {
      "contents": [
        {"role": "user", "parts": [{"text": "Say hello"}]}
      ]
    }
  }'
```

### Response Format (SSE)
Response is Server-Sent Events format:
```
data: {"response": {"candidates": [{"content": {"role": "model", "parts": [{"text": "Hello!"}]}, "finishReason": "STOP"}], ...}}
```

## Complete Workflow

### Step 1: Extract Token
```bash
ACCESS_TOKEN=$(jq -r '.access_token' ~/.gemini/oauth_creds.json)
```

### Step 2: Get Project ID
```bash
PROJECT=$(curl -s "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"metadata": {"ideType": "IDE_UNSPECIFIED", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}}' \
  | jq -r '.cloudaicompanionProject')
```

### Step 3: Make Request
```bash
curl -s "https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "User-Agent: GeminiCLI/0.25.1/gemini-3-pro-preview (darwin; arm64)" \
  -d '{
    "model": "gemini-3-flash-preview",
    "project": "'"$PROJECT"'",
    "request": {
      "contents": [{"role": "user", "parts": [{"text": "Hello!"}]}]
    }
  }'
```

## Available Models (as of Jan 2026)

- `gemini-3-flash-preview` - Fast model (default)
- `gemini-3-pro-preview` - More capable model
- `gemini-2.5-flash` - Previous generation
- `gemini-2.0-flash` - Previous generation

## What NOT To Do

### Don't use the public API with OAuth tokens
```bash
# WRONG - will fail with ACCESS_TOKEN_TYPE_UNSUPPORTED
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent" \
  -H "Authorization: Bearer $ACCESS_TOKEN" ...
```

### Don't skip the project field
```bash
# WRONG - will return 500 Internal Error
curl "https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent" \
  -d '{"model": "gemini-3-flash-preview", "request": {...}}'
```

### Don't assume the project is stored locally
The project ID comes from the API, not from local config. You must call `loadCodeAssist` first.

### Don't forget to refresh expired tokens
Tokens expire after ~1 hour. Either:
- Re-run `gemini` CLI to refresh automatically
- Use the refresh_token to get a new access_token programmatically

## Debugging Tips

### Capture HTTP Traffic with mitmproxy
```bash
# Install
brew install mitmproxy

# Run gemini-cli through proxy
mitmdump -w /tmp/traffic.flow -p 8888 &
HTTPS_PROXY=http://localhost:8888 NODE_TLS_REJECT_UNAUTHORIZED=0 gemini -p "Hello"

# Analyze
mitmdump -r /tmp/traffic.flow --flow-detail 4
```

### Use Node.js HTTP debugging
```bash
NODE_DEBUG=http,https gemini -p "Hello" 2>&1 | grep pathname
```

### Check gemini-cli debug mode
```bash
gemini --debug -p "Hello"
```

## Other API Endpoints Used by gemini-cli

| Endpoint | Purpose |
|----------|---------|
| `oauth2.googleapis.com/tokeninfo` | Validate OAuth token |
| `v1internal:loadCodeAssist` | Get user tier and project ID |
| `v1internal:retrieveUserQuota` | Check usage quota |
| `v1internal:listExperiments` | Get A/B test flags |
| `v1internal:streamGenerateContent` | Generate content (streaming) |
| `v1internal:generateContent` | Generate content (non-streaming) |
| `v1internal:recordCodeAssistMetrics` | Send usage telemetry |

## User Tiers

The `loadCodeAssist` response includes tier information:

```json
{
  "currentTier": {
    "id": "standard-tier",
    "name": "Gemini Code Assist",
    "description": "Unlimited coding assistant with the most powerful Gemini models",
    "userDefinedCloudaicompanionProject": true,
    "usesGcpTos": true
  },
  "paidTier": {
    "id": "g1-pro-tier",
    "name": "Gemini Code Assist in Google One AI Pro"
  },
  "gcpManaged": false
}
```

### Tier Types
| Tier ID | Name | Notes |
|---------|------|-------|
| `free-tier` | Free | Uses Google-managed project, limited quota |
| `standard-tier` | Gemini Code Assist | Unlimited, user-defined project |
| `g1-pro-tier` | Google One AI Pro | Premium tier with additional features |

### Key Fields
- `userDefinedCloudaicompanionProject: true` - User has their own GCP project
- `gcpManaged: false` - Not using Google's managed infrastructure
- `gcpManaged: true` - Free tier using Google-managed project

The tier affects **quotas and available models**, not the API mechanics. The same endpoints and authentication work for all tiers.

## OAuth Scopes

gemini-cli requests these OAuth scopes:
- `https://www.googleapis.com/auth/cloud-platform`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `openid`

## Known Issues (as of Jan 2026)

### Google One AI Pro Subscription Not Detected

**This is a known bug affecting many users.** Even with an active Google One AI Pro subscription, gemini-cli may show `standard-tier` instead of `g1-pro-tier`.

**Symptoms:**
- `currentTier.id` shows `standard-tier` instead of `g1-pro-tier`
- Quota limits match free tier (~100-1000 requests/day)
- Web Gemini works fine with the same account

**Related GitHub Issues:**
- [#12446](https://github.com/google-gemini/gemini-cli/issues/12446) - CLI fails to recognize Google AI Pro subscription
- [#16909](https://github.com/google-gemini/gemini-cli/issues/16909) - Code Assist + AI Pro still shows free tier
- [#15248](https://github.com/google-gemini/gemini-cli/issues/15248) - AI Pro getting low quota (possibly region-related, EU affected)
- [#3462](https://github.com/google-gemini/gemini-cli/issues/3462) - Log in using Google One AI Pro subscription

**Possible Workarounds:**
1. Enable "Preview Features" in `/settings`
2. Try re-authenticating (delete `~/.gemini/oauth_creds.json`)
3. Use `GEMINI_API_KEY` with pay-as-you-go instead (defeats purpose of subscription)
4. File/upvote GitHub issues to increase visibility

**Root Cause:** Server-side issue with how Google links Google One subscriptions to the Code Assist API. Not solvable client-side.

## References

- gemini-cli source: https://github.com/google-gemini/gemini-cli
- Code Assist API is internal/undocumented
- Public Gemini API docs: https://ai.google.dev/docs
- [Google AI Forum Discussion](https://discuss.ai.google.dev/t/misleading-quota-system-devalued-ai-pro-subscription-for-developers/109197)
