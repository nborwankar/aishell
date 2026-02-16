# Assembly DSL — System Wiring Language

*Extracted from: Server-Side WASM Components conversation (ChatGPT)*

The engineer-facing DSL for wiring components into complete systems.
Declares instances, connections, tier requirements, and conditional branches.
Analogous to structural Verilog — instantiate components, connect ports.

---

## Early Component / Execution Graph Concepts (Turn 6, assistant)

```text
component Embedder {
  input:  tensor<string>
  output: tensor<float>[d]
  invariants:
    deterministic=true
    dimension=d
}
```

```text
Python glue → call model → call index → rerank → synthesize
```

```text
[embedder.wasm] ──┐
                  ├─ linked at runtime → execution graph
[index.wasm]  ────┤
[ranker.wasm] ────┘
```

```text
PLAN:
  LOAD encoder: e5_large
  ATTACH index: hnsw_cosine
  EXECUTE semantic_scan(k=20)
  PIPE rerank(cross_encoder)
  RETURN provenance
```

```text
SELECT * FROM docs WHERE embedding ~ query;
```

```text
ASSEMBLE retrieval_cell USING
  encoder = multilingual_e5
  index   = ivf_hnsw
  policy  = locality_sensitive
```

```text
semantic-encoder/
 ├─ component.wasm
 ├─ interface.wit
 ├─ manifest.toml
 ├─ calibration.json
 └─ provenance.sig
```

## VQL-to-Graph Transpilation (Turn 8, assistant)

```sql
SELECT doc_id, chunk_id, score
FROM corpus
WHERE SEMANTIC_MATCH(text, :query)
USING encoder="e5-large", index="hnsw_cos"
RERANK USING model="bge-reranker"
LIMIT 20;
```

```text
graph RetrievalCell {
  node q_encode: Encoder(e5-large)
  node ann: VectorSearch(hnsw_cos, metric=cos)
  node rerank: CrossEncoder(bge-reranker)
  edge query_text -> q_encode.in_text
  edge q_encode.out_vec -> ann.query_vec
  edge ann.topk -> rerank.candidates
  edge query_text -> rerank.query_text
  edge rerank.scored -> output.results
}
```

```sql
EXPLAIN PIPELINE
SELECT ...
```

## Multi-Layer Architecture (DataSheet → VQL → SCIR) (Turn 18, assistant)

```text
DataSheet DSL  ─┐
                ├─► SCIR synthesis ─► execution
VQL Intent  ────┘
```

```text
┌──────────────────────────────┐
│ Component Data Sheet DSL     │  ← industry standard (ISO-like)
└──────────────┬───────────────┘
               │
     Certified component catalog
               │
┌──────────────▼───────────────┐
│ VQL (assembly specification) │  ← engineer-facing
└──────────────┬───────────────┘
               │ compile / synthesize
┌──────────────▼───────────────┐
│ SCIR (assembly netlist)      │  ← EDA-like realization layer
└──────────────┬───────────────┘
               │ optimize / verify
┌──────────────▼───────────────┐
│ Execution substrate          │  ← WASM / cloud / native
└──────────────────────────────┘
```

## Multi-DSL Architecture and SupportBot System Example (Turn 20, assistant)

```text
VQL (retrieval DSL)  ─┐
ETL DSL              ├─► Assembly Script DSL ─► SCIR netlist ─► execution
Policy DSL           ┘
         ▲
         └── all rely on the same Component Data Sheet DSL
```

```text
system SupportBot {

  use tier = Hardened

  instance norm  = component("std/text/normalize@1.2", tier)
  instance embed = component("ml/embed/e5_large@3.1", tier) with {dim=1024}
  instance ann   = component("db/vector/hnsw@2.0", tier)    with {metric="cosine", k=200}
  instance rank  = component("ml/rerank/bge@1.4", tier)
  instance gen   = component("llm/generate/qwen@0.9", Consumer)

  connect input.query_text  -> norm.in
  connect norm.out          -> embed.text
  connect embed.vec         -> ann.query_vec
  connect ann.candidates    -> rank.candidates
  connect input.query_text  -> rank.query
  connect rank.topk         -> gen.context
  connect gen.answer        -> output.answer

  capabilities {
    embed: ["gpu"]
    ann:   ["kv:read"]
    gen:   ["net"]          // if remote model
  }

  constraints {
    latency_p95_ms <= 400
    memory_mb      <= 2048
    deterministic  = true   // forces gen into deterministic mode or disallows it
  }
}
```

## InvoiceFulfillment System Assembly (Turn 36, assistant)

```text
system InvoiceFulfillment {

  # Inputs
  input order: OrderV1
  input ship_to: AddressV1
  input bill_to: AddressV1

  # Required tiers by role (policy)
  require_tier {
    tax_engine      = Hardened
    pdf_renderer    = Consumer
    email_sender    = Hardened
    printer_router  = Hardened
    audit_logger    = Consumer
  }

  # Pick certified components from catalogs
  inst vat:     component("fin.tax.vat_calc")       tier=Hardened
  inst us_tax:  component("fin.tax.us_state_calc")  tier=Hardened
  inst totaler: component("fin.invoice.totaler")    tier=Hardened

  inst pdf:     component("doc.render.pdf")         tier=Consumer
  inst email:   component("net.email.send_smtp")    tier=Hardened
  inst print:   component("io.print.route")         tier=Hardened
  inst audit:   component("obs.audit.append")       tier=Consumer

  # Compute net
  connect order -> totaler.order

  # Branch: choose tax engine by location
  node is_eu = pred.country_in_set(ship_to.country, "EU27")
  node is_us = pred.equals(ship_to.country, "US")

  select tax_result {
    when is_eu: connect totaler.net -> vat.net;      connect ship_to.country -> vat.ship_country
    when is_us: connect totaler.net -> us_tax.net;   connect ship_to.state   -> us_tax.ship_state
    else:       raise UNSUPPORTED("No tax engine for destination")
  }

  # Combine totals
  connect tax_result.gross -> order_totals.gross   # could be explicit 'combine' op

  # Render PDF
  connect order_totals -> pdf.model
  connect pdf.pdf_bytes -> email.attachment_pdf
  connect pdf.pdf_bytes -> print.document_pdf

  # Actuation
  connect order.customer_email -> email.to
  connect order.invoice_id     -> email.subject_key

  connect ship_to.printer_zone -> print.zone
  connect print.job_id         -> audit.print_job_id

  connect email.message_id     -> audit.email_message_id
  connect audit.record         -> output.audit_record
}
```

## Shared Types + Three Domain System Assemblies (Finance, HR, Ops) (Turn 40, assistant)

```yaml
# std.types.v0.1.yaml
types_version: "0.1"

primitives:
  - bool
  - i64
  - f64
  - string
  - bytes

enums:
  ISO4217: ["USD","EUR","GBP","INR"]
  CountryCode: ["US","GB","DE","IN","FR","ES","IT","NL","IE","SE","NO","CH","CA","AU"]  # extendable by versioning
  USState: ["CA","NY","TX","WA","FL","IL","MA","NJ","PA","OH"]                          # extendable by versioning
  MimeType: ["text/plain","text/html","application/pdf"]
  HttpMethod: ["GET","POST","PUT","DELETE"]
  CertTier: ["Dev","Consumer","Hardened","Critical","Safety"]

structs:
  Timestamp:
    unix_ms: { primitive: "i64" }

  Text:
    utf8: { primitive: "bytes" }
    mime: { enum: "MimeType" }
    lang: { optional: { primitive: "string" } }

  Money:
    currency: { enum: "ISO4217" }
    minor_units: { primitive: "i64" }     # cents/paise etc.

  AddressV1:
    name:   { primitive: "string" }
    line1:  { primitive: "string" }
    line2:  { optional: { primitive: "string" } }
    city:   { primitive: "string" }
    region: { primitive: "string" }       # state/province/region name (string, but explicit)
    country:{ enum: "CountryCode" }
    us_state:{ optional: { enum: "USState" } }
    postal: { primitive: "string" }

  PdfBytes:
    bytes: { primitive: "bytes" }
    mime:  { literal: "application/pdf" }

  EmailAddress:
    addr: { primitive: "string" }

  EmailMessageV1:
    to:      { type: "EmailAddress" }
    subject: { primitive: "string" }
    body:    { type: "Text" }             # typically text/plain or text/html
    attachment_pdf: { optional: { type: "PdfBytes" } }

  EmailReceiptV1:
    message_id: { primitive: "string" }
    accepted:   { primitive: "bool" }
    provider:   { primitive: "string" }
    ts:         { type: "Timestamp" }

  PrinterZoneV1:
    zone: { primitive: "string" }         # e.g., "SF-3F", "NYC-5F"

  PrintReceiptV1:
    job_id:   { primitive: "string" }
    zone:     { type: "PrinterZoneV1" }
    accepted: { primitive: "bool" }
    ts:       { type: "Timestamp" }

  AuditEventV1:
    event_id:   { primitive: "string" }
    system_id:  { primitive: "string" }
    event_type: { primitive: "string" }
    ts:         { type: "Timestamp" }
    payload:    { primitive: "bytes" }    # NOTE: still explicit bytes; payload schema is event_type-specific in v0.2

# A universal, explicit error model (no INTERNAL).
errors:
  FailureClass:
    enum:
      - INVALID_INPUT
      - UNSUPPORTED
      - RESOURCE_LIMIT
      - TIME_BUDGET_EXCEEDED
      - DEPENDENCY_UNAVAILABLE
      - CAPABILITY_DENIED
      - STATE_VIOLATION
      - DATA_CORRUPTION_DETECTED
      - OUTPUT_CONTRACT_VIOLATION

  UnknownErrorV1:
    struct:
      sentinel: { literal: "UNKNOWN" }       # allowed ONLY in Dev tier
      fault_fingerprint: { primitive: "bytes" }
      observed_at: { enum: ["PRECONDITION","EXECUTION","POSTCONDITION"] }
      input_digest: { primitive: "bytes" }
      runtime_id: { primitive: "string" }
      placement: { primitive: "string" }

capabilities_v0:
  - net
  - fs_read
  - fs_write
  - clock
  - gpu
  - kv_read
  - kv_write
  - secrets_read
  - device_io
```

```yaml
datasheet_version: "0.1"

identity:
  id: "namespace.component"
  version: "1.0.0"
  manufacturer: "VendorName"
  cert_tier: "Consumer"          # Dev|Consumer|Hardened|Critical|Safety
  allow_unknown: false           # MUST be true only when cert_tier=Dev

runtime_targets:
  - "wasm32-wasi"                # or "remote:https", "remote:smtp", "linux-amd64", etc.

capabilities_declared:
  - "net"
  - "clock"

# Component-local types (MUST reference std.types by name for shared types)
types:
  # Optional: add/extend types local to this component
  # Example:
  # MyType: { struct: { ... } }

errors:
  # MUST enumerate subcodes explicitly; no INTERNAL.
  subcodes:
    # Example:
    # MySubcode: [ "X", "Y" ]

  KnownError:
    struct:
      class:   { type: "FailureClass" }         # from std.types
      subcode: { type: "MySubcode" }            # component-defined enum
      message: { optional: { primitive: "string" } }
      evidence:
        optional:
          struct:
            limit:         { optional: { primitive: "i64" } }
            observed:      { optional: { primitive: "string" } }
            required_cap:  { optional: { primitive: "string" } }
            dependency_id: { optional: { primitive: "string" } }
            postcond_id:   { optional: { primitive: "string" } }

contracts:
  predicate_language: "pred.v0.1"
  supported_predicates:
    - "len(bytes) <= N"
    - "equals(x, literal)"
    - "in_enum(x, EnumName)"
    - "range_i64(x, min, max)"
    - "all_finite(vec)"
    - "dim(vec) == N"

ops:
  - name: "op_name"
    inputs:
      in1: { type: "SomeType" }
    outputs:
      out1: { type: "SomeType" }
    returns:
      ok:  { outputs: ["out1"] }
      err:
        one_of: ["KnownError"]                 # add "UnknownErrorV1" ONLY if cert_tier=Dev and allow_unknown=true
    requires_caps: ["net"]
    pre:
      - "..."                                  # predicate strings over explicit types
    post:
      - "..."

performance:
  latency_ms: { p50: 0.0, p95: 0.0 }
  mem_mb: { peak: 0.0 }
  throughput_qps: 0.0

certification:
  environments:
    - runtime: "wasm32-wasi"
      tier: "Consumer"
  tests:
    property_based:
      - id: "op_name.pre"
        count: 200
      - id: "op_name.post"
        count: 200
```

```text
system Finance.InvoiceFulfillment_v1 {

  input order: FinOrderV1
  input ship_to: AddressV1
  input bill_to: AddressV1
  input vat_bps: i64
  input printer_zone: PrinterZoneV1
  input customer_email: EmailAddress

  require_tier {
    tax_engine     = Hardened
    numbering      = Hardened
    email_sender   = Hardened
    printer_router = Hardened
    pdf_render     = Consumer
    audit          = Hardened
  }

  # Components
  inst now:     std.time.now_v1                 tier=Hardened
  inst invno:   fin.invoice.numbering_v1        tier=Hardened
  inst total:   fin.invoice.totaler_v1          tier=Hardened
  inst vat:     fin.tax.vat_calc_v1             tier=Hardened
  inst us_tax:  fin.tax.us_state_calc_v1        tier=Hardened
  inst is_eu:   std.pred.in_set_country_eu27_v1 tier=Consumer
  inst html:    doc.render.template_html_v1     tier=Consumer
  inst pdf:     doc.render.pdf_v1               tier=Consumer
  inst secrets: sec.secrets.get_v1              tier=Hardened
  inst email:   net.email.send_smtp_v1          tier=Hardened
  inst print:   io.print.route_v1               tier=Hardened
  inst audit:   obs.audit.append_signed_v1      tier=Hardened

  # Layout
  connect ()              -> now.()
  connect order           -> total.order
  connect ship_to.country -> is_eu.country

  connect order.customer_id -> invno.customer_id
  connect now.now           -> invno.now

  # Branching tax selection (explicit)
  select gross_money: Money {
    when is_eu.is_eu == true:
      connect total.net      -> vat.net
      connect ship_to.country-> vat.ship_country
      connect vat_bps        -> vat.vat_bps
      yield vat.gross
    else:
      connect total.net      -> us_tax.net
      connect ship_to.us_state -> us_tax.ship_state
      yield us_tax.gross
  }

  # Build invoice model (bytes)
  inst model: fin.invoice.model_build_v1 tier=Consumer
  connect order      -> model.order
  connect bill_to    -> model.bill_to
  connect ship_to    -> model.ship_to
  connect gross_money-> model.totals.gross   # totals is a typed struct in v0.2; MVP uses explicit fields

  # Render + actuate
  connect model.model -> html.model
  connect html.html   -> pdf.html

  inst smtp_creds: sec.secrets.get_v1 tier=Hardened
  connect "smtp-prod" -> smtp_creds.id

  connect customer_email -> email.msg.to
  connect "Your invoice" -> email.msg.subject
  connect pdf.pdf        -> email.msg.attachment_pdf
  connect smtp_creds.secret -> email.creds

  connect pdf.pdf        -> print.pdf
  connect printer_zone   -> print.zone

  # Audit (signing shown in v0.2; MVP can treat sig as returned by sec.crypto.sign)
  inst sign: std.crypto.sign_v1 tier=Hardened
  connect (/*AuditEventV1*/ ) -> sign.data_bytes
  connect sign.sig_bytes      -> audit.sig
  connect (/*AuditEventV1*/ ) -> audit.evt
}
```

```text
system HR.OnboardingProvision_v1 {

  input emp: EmployeeV1
  input ship_to: AddressV1          # for device shipping
  input manager_email: EmailAddress

  require_tier {
    policy_eval    = Hardened
    provisioning   = Hardened
    email_sender   = Hardened
    pdf_render     = Consumer
    audit          = Hardened
  }

  inst policy:  hr.policy.role_to_entitlements_v1 tier=Hardened
  inst pack:    hr.doc.employee_pack_model_v1     tier=Consumer
  inst html:    doc.render.template_html_v1       tier=Consumer
  inst pdf:     doc.render.pdf_v1                 tier=Consumer
  inst secrets: sec.secrets.get_v1                tier=Hardened
  inst email:   net.email.send_smtp_v1            tier=Hardened

  inst acct:    it.provision.account_create_v1    tier=Hardened
  inst groups:  it.provision.group_assign_v1      tier=Hardened
  inst device:  it.provision.device_request_v1    tier=Hardened

  inst now:     std.time.now_v1                   tier=Hardened
  inst audit:   obs.audit.append_signed_v1        tier=Hardened
  inst sign:    std.crypto.sign_v1                tier=Hardened

  # Compute entitlements with country/role inputs
  connect emp.role    -> policy.role
  connect emp.country -> policy.country

  # Provisioning (actuation)
  connect "idp-admin" -> secrets.id
  connect secrets.secret -> acct.creds
  connect emp -> acct.emp

  connect acct.acct -> groups.acct
  connect policy.ents -> groups.ents
  connect secrets.secret -> groups.creds

  # Branch: device spec differs by role (example mux)
  inst is_eng: std.pred.equals_v1 tier=Consumer
  connect emp.role_string -> is_eng.a
  connect "Engineer"      -> is_eng.b

  inst dev_laptop: HrDeviceSpecEng_v1    tier=Consumer   # could be a constant component in v0.2
  inst std_laptop: HrDeviceSpecStd_v1    tier=Consumer

  select spec: DeviceSpecV1 {
    when is_eng.is_equal == true:  yield dev_laptop.spec
    else:                          yield std_laptop.spec
  }

  connect emp  -> device.emp
  connect spec -> device.device

  # Employee pack PDF + email
  connect emp         -> pack.emp
  connect policy.ents -> pack.ents
  connect pack.model  -> html.model
  connect html.html   -> pdf.html

  inst smtp_creds: sec.secrets.get_v1 tier=Hardened
  connect "smtp-prod" -> smtp_creds.id

  connect manager_email -> email.msg.to
  connect "Onboarding pack" -> email.msg.subject
  connect pdf.pdf       -> email.msg.attachment_pdf
  connect smtp_creds.secret -> email.creds

  # Audit (placeholder event wiring)
  connect (/*AuditEventV1: account created, groups assigned, device requested*/ ) -> sign.data_bytes
  connect sign.sig_bytes -> audit.sig
  connect (/*AuditEventV1*/ ) -> audit.evt
}
```

```text
system Ops.IncidentResponse_v1 {

  input raw: TicketRawV1
  input customer_email: EmailAddress
  input printer_zone: PrinterZoneV1

  require_tier {
    classification = Consumer
    remediation    = Hardened
    notification   = Hardened
    pdf_render     = Consumer
    print_router   = Hardened
    audit          = Hardened
  }

  inst ingest: ops.ingest.ticket_v1          tier=Consumer
  inst cls:    ops.classify.severity_v1      tier=Consumer
  inst play:   ops.remediate.playbook_v1     tier=Hardened

  inst html:   doc.render.template_html_v1   tier=Consumer
  inst pdf:    doc.render.pdf_v1             tier=Consumer
  inst secrets:sec.secrets.get_v1            tier=Hardened
  inst email:  net.email.send_smtp_v1        tier=Hardened
  inst print:  io.print.route_v1             tier=Hardened

  inst is_sev1: ops.pred.is_sev1_v1          tier=Consumer   # small predicate component from std.pred family
  inst audit:  obs.audit.append_signed_v1    tier=Hardened
  inst sign:   std.crypto.sign_v1            tier=Hardened
  inst now:    std.time.now_v1               tier=Hardened

  connect raw -> ingest.raw
  connect ingest.t -> cls.t
  connect cls.sev -> play.sev
  connect cls.cat -> play.cat

  # Build a customer-facing report model (bytes)
  inst report_model: ops.report.model_build_v1 tier=Consumer
  connect ingest.t -> report_model.ticket
  connect cls.sev  -> report_model.severity
  connect cls.cat  -> report_model.category
  connect play.plan-> report_model.plan
  connect ()       -> now.()
  connect now.now  -> report_model.now

  connect report_model.model -> html.model
  connect html.html          -> pdf.html

  # Notification (email)
  inst smtp_creds: sec.secrets.get_v1 tier=Hardened
  connect "smtp-prod" -> smtp_creds.id

  connect customer_email -> email.msg.to
  connect "Incident update" -> email.msg.subject
  connect pdf.pdf       -> email.msg.attachment_pdf
  connect smtp_creds.secret -> email.creds

  # Optional print if sev1 (branch)
  connect cls.sev -> is_sev1.sev
  select do_print: bool { when is_sev1.yes==true: yield true else: yield false }

  # In v0.1, model printing as conditional execution node
  node maybe_print {
    when do_print==true:
      connect pdf.pdf      -> print.pdf
      connect printer_zone -> print.zone
  }

  # Audit
  connect (/*AuditEventV1: severity, plan, email receipt, optional print*/ ) -> sign.data_bytes
  connect sign.sig_bytes -> audit.sig
  connect (/*AuditEventV1*/ ) -> audit.evt
}
```

