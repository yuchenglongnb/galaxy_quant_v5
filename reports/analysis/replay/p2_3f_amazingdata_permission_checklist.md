# P2.3F AmazingData Permission Checklist

## Scope

This checklist records the permission and control-flow questions that must be resolved before AmazingData online 09:35 backfill can be considered safe to retry.

## Manual Basis

AmazingData usage requires:

```text
login before data API calls
SDK account/password/IP/port obtained after official permission is enabled
```

The current repo must therefore distinguish:

```text
config ready = credential fields exist locally
permission ready = vendor-side SDK and data entitlements are enabled
```

## Current Local Facts

```text
config ready = true
P2.3E login styles tested = 5
P2.3E successful login styles = 0
P2.3F safe_to_query = false
SystemExit(0) remains ambiguous control flow
```

## Items Requiring Human / Vendor Confirmation

```text
SDK API permission enabled
historical snapshot query_snapshot permission enabled
historical kline query_kline permission enabled
A-share stock universe permission enabled
IP allowlist or machine binding requirement
host/port are SDK data-service endpoint, not another service endpoint
account supports Python SDK login
whether login requires trading-session timing or license/session initialization step
whether SystemExit(0) is documented SDK behavior
```

## Engineering Judgment

Permission issue is plausible but not proven. Because no control-flow strategy produced `safe_to_query=true`, AmazingData online 09:35 backfill should remain blocked until the login/session behavior is clarified.

## Boundary

This checklist contains no credentials, host values, port values, supplier logs, or market data.
