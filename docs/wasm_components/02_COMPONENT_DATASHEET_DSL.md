# Component Data Sheet DSL

*Extracted from: Server-Side WASM Components conversation (ChatGPT)*

Strictly-typed YAML datasheets that define component interfaces, error enums,
capabilities, pre/post conditions, and certification tiers. No opaque types.
No INTERNAL errors. UnknownError only permitted at Dev tier.

---

## First Interface Signature and Error Enum (Turn 26, assistant)

```text
op Embed(input: Text) -> Result<VectorF32[1024], EmbedError>
```

```text
EmbedError = enum {
  INVALID_UTF8,
  TOO_LONG,
  MODEL_UNAVAILABLE,
  RESOURCE_LIMIT,
  INTERNAL
}
```

```yaml
id: std.embed.e5_large
version: 1.0.0
cert_tier: Hardened
runtime_targets: [wasm32-wasi]

types:
  Text: { struct: { utf8: bytes, mime: string, lang: { optional: string } } }
  VectorF32_1024: { vector_f32: { dim: 1024 } }

errors:
  EmbedError: { enum: [INVALID_UTF8, TOO_LONG, RESOURCE_LIMIT, INTERNAL] }

ops:
  - name: embed
    input:
      text: Text
    output:
      vec: VectorF32_1024
    error: EmbedError
    requires_caps: [gpu]
    pre:
      - "text.mime == 'text/plain'"
      - "len(text.utf8) <= 20000"
    post:
      - "all_finite(vec)"
      - "len(vec) == 1024"

performance:
  latency_ms: { p50: 6.0, p95: 15.0 }
  mem_mb: { peak: 1200.0 }
```

## Full Datasheet Template (v0.1) with Tier Rules (Turn 32, assistant)

```yaml
datasheet_version: "0.1"

identity:
  id: "namespace.component_name"      # stable identifier
  version: "1.0.0"                    # semver
  manufacturer: "Acme Components"
  cert_tier: "Dev"                    # Dev | Consumer | Hardened | Critical | Safety
  allow_unknown: true                 # ONLY legal when cert_tier == Dev

runtime_targets:
  - "wasm32-wasi"                     # for MVP: treat as tags

capabilities:                         # closed set in v0
  # Declare what this component *may* request; per-op declares what it actually requires.
  defined:
    - "gpu"
    - "net"
    - "fs_read"
    - "fs_write"
    - "clock"
    - "kv_read"
    - "kv_write"
    - "secrets_read"

types:
  # Closed-world, explicit IDL.
  # Allowed forms: primitive, enum, struct, list, vector_f32(dim)
  Text:
    struct:
      utf8: { primitive: "bytes" }
      mime: { primitive: "string" }      # e.g., "text/plain"
      lang: { optional: { primitive: "string" } }

  Span:
    struct:
      start: { primitive: "i64" }
      end:   { primitive: "i64" }

  Vector1024:
    vector_f32:
      dim: 1024

  # Result type is structural; every op returns either ok or err.
  # Error is a tagged union: either KnownError or UnknownError.

errors:
  # Normative closed set of actionable failure classes.
  FailureClass:
    enum:
      - "INVALID_INPUT"
      - "UNSUPPORTED"
      - "RESOURCE_LIMIT"
      - "TIME_BUDGET_EXCEEDED"
      - "DEPENDENCY_UNAVAILABLE"
      - "CAPABILITY_DENIED"
      - "STATE_VIOLATION"
      - "DATA_CORRUPTION_DETECTED"
      - "OUTPUT_CONTRACT_VIOLATION"

  # Per-component explicit subcodes (still enumerations; no catch-alls).
  EmbedSubcode:
    enum:
      - "NON_UTF8"
      - "MIME_NOT_SUPPORTED"
      - "TOO_LONG_BYTES"
      - "GPU_OOM"
      - "MODEL_WEIGHTS_MISSING"
      - "NAN_IN_VECTOR"
      - "WRONG_DIMENSION"

  KnownError:
    struct:
      class:   { type: "FailureClass" }
      subcode: { type: "EmbedSubcode" }
      message: { optional: { primitive: "string" } }
      evidence:
        optional:
          struct:
            limit:         { optional: { primitive: "i64" } }
            observed:      { optional: { primitive: "string" } }
            required_cap:  { optional: { primitive: "string" } }
            dependency_id: { optional: { primitive: "string" } }
            postcond_id:   { optional: { primitive: "string" } }

  # UNKNOWN is allowed only in Dev tier with allow_unknown=true.
  UnknownError:
    struct:
      sentinel: { literal: "UNKNOWN" }
      message:  { optional: { primitive: "string" } }
      diagnostics:
        struct:
          fault_fingerprint: { primitive: "bytes" }
          observed_at:
            enum: ["PRECONDITION", "EXECUTION", "POSTCONDITION"]
          input_digest: { primitive: "bytes" }
          runtime_id:   { primitive: "string" }
          placement:    { primitive: "string" }

contracts:
  # Minimal predicate vocabulary for MVP (you implement a tiny evaluator).
  # Expressions are strings but over explicit types; later you can make this an AST.
  predicate_language: "scir-pred-0.1"
  predicates_supported:
    - "len(bytes) <= N"
    - "equals(string, literal)"
    - "all_finite(vector)"
    - "dim(vector) == N"

ops:
  - name: "embed"
    inputs:
      text: { type: "Text" }
    outputs:
      vec:  { type: "Vector1024" }
    returns:
      ok:  { outputs: ["vec"] }
      err:
        one_of: ["KnownError", "UnknownError"]  # UnknownError MUST be disallowed outside Dev
    requires_caps: ["gpu"]
    pre:
      - "equals(text.mime, 'text/plain')"
      - "len(text.utf8) <= 20000"
    post:
      - "all_finite(vec)"
      - "dim(vec) == 1024"

performance:
  latency_ms: { p50: 6.0, p95: 15.0 }
  mem_mb: { peak: 1200.0 }

validation:
  # Links the datasheet to a certification suite (even if your MVP runner is basic).
  property_tests:
    - id: "embed_preconditions"
      kind: "generated_inputs"
      count: 200
    - id: "embed_postconditions"
      kind: "generated_inputs"
      count: 200
```

```yaml
identity:
  id: "std.embed.e5_large"
  version: "0.1.0"
  manufacturer: "LocalLab"
  cert_tier: "Dev"
  allow_unknown: true
```

```yaml
identity:
  id: "std.embed.e5_large"
  version: "1.0.0"
  manufacturer: "Acme Components"
  cert_tier: "Hardened"
  allow_unknown: false   # or omit field entirely
```

```yaml
ops:
  - name: "embed"
    returns:
      ok:  { outputs: ["vec"] }
      err:
        one_of: ["KnownError"]   # UnknownError forbidden at schema level
```

## Three Domain Examples: Finance, IoT, Security (Turn 34, assistant)

```yaml
datasheet_version: "0.1"
identity: { id: "fin.tax.vat_calc", version: "1.0.0", manufacturer: "AcmeFin", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  ISO4217: { enum: ["USD","EUR","GBP","INR"] }
  Money:
    struct: { currency: { type: "ISO4217" }, minor_units: { primitive: "i64" } }
  CountryCode: { enum: ["US","GB","DE","IN"] }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  VatSubcode: { enum: ["NEGATIVE_AMOUNT","COUNTRY_UNSUPPORTED","CURRENCY_MISMATCH","ROUNDING_OVERFLOW"] }
  KnownError:
    struct: { class: { type: "FailureClass" }, subcode: { type: "VatSubcode" }, message: { optional: { primitive: "string" } } }

ops:
  - name: "compute_vat"
    inputs:
      net: { type: "Money" }
      ship_to: { type: "CountryCode" }
      vat_rate_bps: { primitive: "i64" }     # e.g. 2000 = 20.00%
    outputs:
      vat: { type: "Money" }
      gross: { type: "Money" }
    returns: { ok: { outputs: ["vat","gross"] }, err: { one_of: ["KnownError"] } }
    pre:
      - "net.minor_units >= 0"
      - "vat_rate_bps >= 0"
    post:
      - "vat.currency == net.currency"
      - "gross.currency == net.currency"
```

```yaml
datasheet_version: "0.1"
identity: { id: "fin.fx.quote", version: "2.1.0", manufacturer: "RateCo", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["remote:https"]

types:
  ISO4217: { enum: ["USD","EUR","GBP","INR"] }
  FxPair:  { struct: { base: { type: "ISO4217" }, quote: { type: "ISO4217" } } }
  Timestamp: { struct: { unix_ms: { primitive: "i64" } } }
  FxQuote:
    struct:
      pair: { type: "FxPair" }
      rate: { primitive: "f64" }
      asof: { type: "Timestamp" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  FxSubcode: { enum: ["PAIR_UNSUPPORTED","STALE_MARKET_DATA","UPSTREAM_TIMEOUT","HTTP_4XX","HTTP_5XX"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "FxSubcode" }, message: { optional: { primitive: "string" } } } }

ops:
  - name: "get_quote"
    inputs: { pair: { type: "FxPair" }, max_age_ms: { primitive: "i64" } }
    outputs: { quote: { type: "FxQuote" } }
    returns: { ok: { outputs: ["quote"] }, err: { one_of: ["KnownError"] } }
    requires_caps: ["net","clock"]
    pre:
      - "max_age_ms >= 0"
    post:
      - "quote.rate > 0"
```

```yaml
datasheet_version: "0.1"
identity: { id: "fin.invoice.totaler", version: "1.0.0", manufacturer: "AcmeFin", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  ISO4217: { enum: ["USD","EUR","GBP","INR"] }
  Money: { struct: { currency: { type: "ISO4217" }, minor_units: { primitive: "i64" } } }
  LineItem: { struct: { sku: { primitive: "string" }, qty: { primitive: "i64" }, unit_price: { type: "Money" } } }
  Invoice: { struct: { items: { list: { type: "LineItem" } }, currency: { type: "ISO4217" } } }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  InvSubcode: { enum: ["EMPTY_ITEMS","NEGATIVE_QTY","CURRENCY_MISMATCH","SUM_OVERFLOW"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "InvSubcode" } } }

ops:
  - name: "sum_net"
    inputs: { invoice: { type: "Invoice" } }
    outputs: { net: { type: "Money" } }
    returns: { ok: { outputs: ["net"] }, err: { one_of: ["KnownError"] } }
    pre:
      - "len(invoice.items) > 0"
    post:
      - "net.currency == invoice.currency"
```

```yaml
datasheet_version: "0.1"
identity: { id: "iot.ingest.mqtt", version: "1.3.0", manufacturer: "EdgeWorks", cert_tier: "Dev", allow_unknown: true }
runtime_targets: ["remote:mqtt"]

types:
  Timestamp: { struct: { unix_ms: { primitive: "i64" } } }
  Topic: { struct: { name: { primitive: "string" } } }
  BytesMsg:
    struct:
      topic: { type: "Topic" }
      ts: { type: "Timestamp" }
      payload: { primitive: "bytes" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  MqttSubcode: { enum: ["BROKER_UNREACHABLE","AUTH_FAILED","SUBSCRIBE_DENIED","PAYLOAD_TOO_LARGE"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "MqttSubcode" } } }
  UnknownError:
    struct:
      sentinel: { literal: "UNKNOWN" }
      diagnostics: { struct: { fault_fingerprint: { primitive: "bytes" }, input_digest: { primitive: "bytes" }, runtime_id: { primitive: "string" }, placement: { primitive: "string" } } }

ops:
  - name: "subscribe"
    inputs: { topic: { type: "Topic" }, max_payload_bytes: { primitive: "i64" } }
    outputs: { msg: { type: "BytesMsg" } }
    returns: { ok: { outputs: ["msg"] }, err: { one_of: ["KnownError","UnknownError"] } }
    requires_caps: ["net","clock"]
    pre: ["max_payload_bytes > 0"]
```

```yaml
datasheet_version: "0.1"
identity: { id: "iot.decode.protobuf_v1", version: "1.0.0", manufacturer: "EdgeWorks", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  Timestamp: { struct: { unix_ms: { primitive: "i64" } } }
  Telemetry:
    struct:
      device_id: { primitive: "string" }
      ts: { type: "Timestamp" }
      temperature_c: { primitive: "f64" }
      humidity_pct: { primitive: "f64" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  PbSubcode: { enum: ["WIRE_FORMAT_INVALID","MISSING_REQUIRED_FIELD","VALUE_OUT_OF_RANGE"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "PbSubcode" } } }

ops:
  - name: "decode"
    inputs: { payload: { primitive: "bytes" } }
    outputs: { t: { type: "Telemetry" } }
    returns: { ok: { outputs: ["t"] }, err: { one_of: ["KnownError"] } }
    post:
      - "t.humidity_pct >= 0"
      - "t.humidity_pct <= 100"
```

```yaml
datasheet_version: "0.1"
identity: { id: "iot.detect.zscore", version: "1.0.0", manufacturer: "EdgeWorks", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  Timestamp: { struct: { unix_ms: { primitive: "i64" } } }
  Telemetry:
    struct:
      device_id: { primitive: "string" }
      ts: { type: "Timestamp" }
      temperature_c: { primitive: "f64" }
      humidity_pct: { primitive: "f64" }
  Anomaly:
    struct:
      device_id: { primitive: "string" }
      ts: { type: "Timestamp" }
      metric: { enum: ["temperature_c","humidity_pct"] }
      z: { primitive: "f64" }
      threshold: { primitive: "f64" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  DetSubcode: { enum: ["WINDOW_TOO_SMALL","NAN_INPUT"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "DetSubcode" } } }

ops:
  - name: "score"
    inputs: { t: { type: "Telemetry" }, window: { primitive: "i64" }, threshold: { primitive: "f64" } }
    outputs: { a: { type: "Anomaly" } }
    returns: { ok: { outputs: ["a"] }, err: { one_of: ["KnownError"] } }
    pre:
      - "window >= 5"
```

```yaml
datasheet_version: "0.1"
identity: { id: "sec.jwt.verify_rs256", version: "1.0.0", manufacturer: "SecureCo", cert_tier: "Hardened", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  Timestamp: { struct: { unix_ms: { primitive: "i64" } } }
  Jwt:
    struct:
      header_b64: { primitive: "string" }
      payload_b64: { primitive: "string" }
      signature_b64: { primitive: "string" }
  Claims:
    struct:
      sub: { primitive: "string" }
      aud: { primitive: "string" }
      iss: { primitive: "string" }
      exp: { type: "Timestamp" }
      scopes: { list: { primitive: "string" } }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  JwtSubcode: { enum: ["MALFORMED_TOKEN","BAD_SIGNATURE","EXPIRED","AUD_MISMATCH","ISS_MISMATCH","KEY_NOT_FOUND"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "JwtSubcode" } } }

ops:
  - name: "verify"
    inputs: { token: { primitive: "string" }, aud: { primitive: "string" }, iss: { primitive: "string" }, now: { type: "Timestamp" } }
    outputs: { claims: { type: "Claims" } }
    returns: { ok: { outputs: ["claims"] }, err: { one_of: ["KnownError"] } }
    requires_caps: ["clock"]
```

```yaml
datasheet_version: "0.1"
identity: { id: "sec.policy.rbac", version: "1.0.0", manufacturer: "SecureCo", cert_tier: "Hardened", allow_unknown: false }
runtime_targets: ["wasm32-wasi"]

types:
  Claims:
    struct:
      sub: { primitive: "string" }
      aud: { primitive: "string" }
      iss: { primitive: "string" }
      exp: { struct: { unix_ms: { primitive: "i64" } } }
      scopes: { list: { primitive: "string" } }
  Request:
    struct:
      method: { enum: ["GET","POST","PUT","DELETE"] }
      path: { primitive: "string" }

  Decision:
    struct:
      allow: { primitive: "bool" }
      reason: { primitive: "string" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  PolSubcode: { enum: ["RULESET_MISSING","INVALID_RULESET","SCOPE_FORMAT_INVALID"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "PolSubcode" } } }

ops:
  - name: "decide"
    inputs: { claims: { type: "Claims" }, req: { type: "Request" } }
    outputs: { decision: { type: "Decision" } }
    returns: { ok: { outputs: ["decision"] }, err: { one_of: ["KnownError"] } }
```

```yaml
datasheet_version: "0.1"
identity: { id: "net.http.gateway_v1", version: "1.0.0", manufacturer: "NetCo", cert_tier: "Consumer", allow_unknown: false }
runtime_targets: ["remote:http"]

types:
  Request:
    struct:
      method: { enum: ["GET","POST","PUT","DELETE"] }
      path: { primitive: "string" }
      headers: { list: { struct: { k: { primitive: "string" }, v: { primitive: "string" } } } }
  Response:
    struct:
      status: { primitive: "i64" }
      body: { primitive: "bytes" }

errors:
  FailureClass: { enum: ["INVALID_INPUT","UNSUPPORTED","RESOURCE_LIMIT","TIME_BUDGET_EXCEEDED","DEPENDENCY_UNAVAILABLE","CAPABILITY_DENIED","STATE_VIOLATION","DATA_CORRUPTION_DETECTED","OUTPUT_CONTRACT_VIOLATION"] }
  GwSubcode: { enum: ["UPSTREAM_TIMEOUT","BAD_UPSTREAM_RESPONSE","CONNECTION_FAILED"] }
  KnownError: { struct: { class: { type: "FailureClass" }, subcode: { type: "GwSubcode" } } }

ops:
  - name: "handle"
    inputs: { req: { type: "Request" } }
    outputs: { resp: { type: "Response" } }
    returns: { ok: { outputs: ["resp"] }, err: { one_of: ["KnownError"] } }
    requires_caps: ["net"]
```

