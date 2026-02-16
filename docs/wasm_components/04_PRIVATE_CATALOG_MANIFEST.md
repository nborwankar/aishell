# Private Catalog Manifest

*Extracted from: Server-Side WASM Components conversation (ChatGPT)*

A single YAML manifest listing ~30 components across finance, IoT, security,
and infrastructure domains. Each entry is a full datasheet. Normative rules
enforce no INTERNAL errors and restrict UnknownError to Dev tier.

---

## Full Catalog Manifest (~30 Components) + Validation Report (Turn 42, assistant)

```yaml
catalog_version: "0.1"
catalog_id: "private.demo.catalog"
std_types_ref: "std.types.v0.1.yaml"

normative_rules:
  - "No INTERNAL errors permitted."
  - "UnknownErrorV1 is allowed ONLY when identity.cert_tier == Dev AND identity.allow_unknown == true."
  - "Any observed UnknownErrorV1 during validation marks component non-compliant and blocks promotion."
  - "All errors must be explicitly enumerated as (FailureClass, SubcodeEnum)."

# -------------------------------------------------------------------
# Component entries
# Each component declares:
# - identity (tier, allow_unknown)
# - runtime_targets
# - capabilities_declared (superset; per-op requires_caps is authoritative)
# - local_types (optional)
# - errors.subcodes: explicit enum list
# - ops: typed signatures + explicit KnownError (+ UnknownError only in Dev)
# -------------------------------------------------------------------

components:

  # =========================
  # A) Cross-domain StdLib (15)
  # =========================

  - identity: { id: "std.pred.equals_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        EqSubcode: ["TYPE_MISMATCH"]   # for MVP, treat mismatch as INVALID_INPUT at call site
      KnownError: { class: "FailureClass", subcode: "EqSubcode" }
    ops:
      - name: "equals_string"
        inputs: { a: { primitive: "string" }, b: { primitive: "string" } }
        outputs: { is_equal: { primitive: "bool" } }
        returns: { ok: { outputs: ["is_equal"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.pred.in_set_country_eu27_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        EUSetSubcode: ["COUNTRY_ENUM_INVALID"]
      KnownError: { class: "FailureClass", subcode: "EUSetSubcode" }
    ops:
      - name: "is_eu27"
        inputs: { country: { enum: "CountryCode" } }
        outputs: { is_eu: { primitive: "bool" } }
        returns: { ok: { outputs: ["is_eu"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.route.select2_money_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        Select2Subcode: ["MISSING_BRANCH_INPUT"]
      KnownError: { class: "FailureClass", subcode: "Select2Subcode" }
    ops:
      - name: "select_money"
        inputs:
          sel: { primitive: "bool" }
          a:   { type: "Money" }
          b:   { type: "Money" }
        outputs: { out: { type: "Money" } }
        returns: { ok: { outputs: ["out"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.data.project_address_country_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        ProjectSubcode: ["FIELD_NOT_PRESENT"]
      KnownError: { class: "FailureClass", subcode: "ProjectSubcode" }
    ops:
      - name: "get_country"
        inputs: { addr: { type: "AddressV1" } }
        outputs: { country: { enum: "CountryCode" } }
        returns: { ok: { outputs: ["country"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.data.project_address_us_state_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        ProjectStateSubcode: ["US_STATE_MISSING"]
      KnownError: { class: "FailureClass", subcode: "ProjectStateSubcode" }
    ops:
      - name: "get_us_state"
        inputs: { addr: { type: "AddressV1" } }
        outputs: { state: { enum: "USState" } }
        returns: { ok: { outputs: ["state"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.time.now_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: ["clock"]
    errors:
      subcodes:
        NowSubcode: ["CLOCK_UNAVAILABLE"]
      KnownError: { class: "FailureClass", subcode: "NowSubcode" }
    ops:
      - name: "now"
        inputs: {}
        outputs: { now: { type: "Timestamp" } }
        returns: { ok: { outputs: ["now"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["clock"]
        pre: []
        post: []

  - identity: { id: "sec.secrets.get_v1", version: "1.0.0", manufacturer: "SecureLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: ["secrets_read"]
    errors:
      subcodes:
        SecretsSubcode: ["SECRET_NOT_FOUND","ACCESS_DENIED","STORE_UNAVAILABLE"]
      KnownError: { class: "FailureClass", subcode: "SecretsSubcode" }
    ops:
      - name: "get"
        inputs: { id: { primitive: "string" } }
        outputs: { secret: { primitive: "bytes" } }
        returns: { ok: { outputs: ["secret"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["secrets_read"]
        pre: []
        post: []

  - identity: { id: "std.crypto.sign_v1", version: "1.0.0", manufacturer: "SecureLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        SignSubcode: ["KEY_UNAVAILABLE","INVALID_INPUT_BYTES","SIGNATURE_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "SignSubcode" }
    ops:
      - name: "sign"
        inputs:
          data_bytes: { primitive: "bytes" }
          key_id: { primitive: "string" }
        outputs:
          sig_bytes: { primitive: "bytes" }
        returns: { ok: { outputs: ["sig_bytes"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: ["len(data_bytes) <= 5000000"]
        post: []

  - identity: { id: "doc.render.template_html_v1", version: "1.0.0", manufacturer: "DocLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        TplSubcode: ["TEMPLATE_NOT_FOUND","MODEL_INVALID","RENDER_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "TplSubcode" }
    ops:
      - name: "render_html"
        inputs:
          template_id: { primitive: "string" }
          model_bytes: { primitive: "bytes" }
        outputs:
          html: { type: "Text" }   # must have mime=text/html; enforced via postconditions in v0.2
        returns: { ok: { outputs: ["html"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: ["len(model_bytes) <= 5000000"]
        post: []

  - identity: { id: "doc.render.pdf_v1", version: "1.0.0", manufacturer: "DocLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        PdfSubcode: ["HTML_INVALID","RENDER_FAILURE","RESOURCE_LIMIT_EXCEEDED"]
      KnownError: { class: "FailureClass", subcode: "PdfSubcode" }
    ops:
      - name: "html_to_pdf"
        inputs: { html: { type: "Text" } }
        outputs: { pdf: { type: "PdfBytes" } }
        returns: { ok: { outputs: ["pdf"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "net.email.send_smtp_v1", version: "1.0.0", manufacturer: "NetLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["remote:smtp"]
    capabilities_declared: ["net","secrets_read","clock"]
    errors:
      subcodes:
        SmtpSubcode: ["DNS_FAIL","CONNECT_FAIL","AUTH_FAIL","RCPT_REJECTED","DATA_REJECTED","UPSTREAM_TIMEOUT"]
      KnownError: { class: "FailureClass", subcode: "SmtpSubcode" }
    ops:
      - name: "send"
        inputs:
          msg:   { type: "EmailMessageV1" }
          creds: { primitive: "bytes" }
        outputs:
          rcpt:  { type: "EmailReceiptV1" }
        returns: { ok: { outputs: ["rcpt"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["net","secrets_read","clock"]
        pre: []
        post: []

  - identity: { id: "io.print.route_v1", version: "1.0.0", manufacturer: "IOLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: ["device_io","clock"]
    errors:
      subcodes:
        PrintSubcode: ["ZONE_UNKNOWN","PRINTER_UNAVAILABLE","JOB_REJECTED","UPSTREAM_TIMEOUT","DOC_INVALID_PDF"]
      KnownError: { class: "FailureClass", subcode: "PrintSubcode" }
    ops:
      - name: "print_pdf"
        inputs:
          pdf:  { type: "PdfBytes" }
          zone: { type: "PrinterZoneV1" }
        outputs:
          rcpt: { type: "PrintReceiptV1" }
        returns: { ok: { outputs: ["rcpt"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["device_io","clock"]
        pre: []
        post: []

  - identity: { id: "obs.audit.append_signed_v1", version: "1.0.0", manufacturer: "ObsLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: ["kv_write","clock"]
    errors:
      subcodes:
        AuditSubcode: ["STORE_UNAVAILABLE","WRITE_DENIED","SIGNATURE_INVALID","SCHEMA_REJECTED"]
      KnownError: { class: "FailureClass", subcode: "AuditSubcode" }
    ops:
      - name: "append"
        inputs:
          evt: { type: "AuditEventV1" }
          sig: { primitive: "bytes" }
        outputs: { ok: { primitive: "bool" } }
        returns: { ok: { outputs: ["ok"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["kv_write","clock"]
        pre: []
        post: []

  - identity: { id: "std.error.map_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    # For MVP: maps from one subcode enum to another using a declared mapping table ID.
    errors:
      subcodes:
        ErrMapSubcode: ["MAPPING_NOT_FOUND","INPUT_ERROR_CLASS_UNKNOWN"]
      KnownError: { class: "FailureClass", subcode: "ErrMapSubcode" }
    ops:
      - name: "map_error"
        inputs:
          mapping_id: { primitive: "string" }
          err_in: { struct: { class: { type: "FailureClass" }, subcode: { primitive: "string" } } }
        outputs:
          err_out: { struct: { class: { type: "FailureClass" }, subcode: { primitive: "string" } } }
        returns: { ok: { outputs: ["err_out"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  # =========================
  # B) Finance domain (6)
  # =========================

  - identity: { id: "fin.invoice.totaler_v1", version: "1.0.0", manufacturer: "FinCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      LineItemV1:
        struct:
          sku: { primitive: "string" }
          qty: { primitive: "i64" }
          unit_price: { type: "Money" }
      FinOrderV1:
        struct:
          customer_id: { primitive: "string" }
          currency: { enum: "ISO4217" }
          items: { list: { type: "LineItemV1" } }
    errors:
      subcodes:
        TotalSubcode: ["EMPTY_ITEMS","NEGATIVE_QTY","CURRENCY_MISMATCH","SUM_OVERFLOW"]
      KnownError: { class: "FailureClass", subcode: "TotalSubcode" }
    ops:
      - name: "sum_net"
        inputs: { order: { type: "FinOrderV1" } }
        outputs: { net: { type: "Money" } }
        returns: { ok: { outputs: ["net"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: ["len(order.items) > 0"]
        post: ["net.currency == order.currency"]

  - identity: { id: "fin.tax.vat_calc_v1", version: "1.0.0", manufacturer: "FinCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        VatSubcode: ["NEGATIVE_AMOUNT","COUNTRY_UNSUPPORTED","VAT_BPS_INVALID","ROUNDING_OVERFLOW"]
      KnownError: { class: "FailureClass", subcode: "VatSubcode" }
    ops:
      - name: "compute_vat"
        inputs:
          net: { type: "Money" }
          ship_country: { enum: "CountryCode" }
          vat_bps: { primitive: "i64" }
        outputs:
          vat: { type: "Money" }
          gross: { type: "Money" }
        returns: { ok: { outputs: ["vat","gross"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: ["net.minor_units >= 0", "vat_bps >= 0", "vat_bps <= 50000"]
        post: ["vat.currency == net.currency", "gross.currency == net.currency"]

  - identity: { id: "fin.tax.us_state_calc_v1", version: "1.0.0", manufacturer: "FinCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        UsTaxSubcode: ["NEGATIVE_AMOUNT","STATE_UNSUPPORTED","RATE_TABLE_MISSING","ROUNDING_OVERFLOW"]
      KnownError: { class: "FailureClass", subcode: "UsTaxSubcode" }
    ops:
      - name: "compute_state_tax"
        inputs:
          net: { type: "Money" }
          ship_state: { enum: "USState" }
        outputs:
          tax: { type: "Money" }
          gross: { type: "Money" }
        returns: { ok: { outputs: ["tax","gross"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: ["net.minor_units >= 0"]
        post: ["tax.currency == net.currency", "gross.currency == net.currency"]

  - identity: { id: "fin.invoice.numbering_v1", version: "1.0.0", manufacturer: "FinCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: ["clock"]
    errors:
      subcodes:
        NumSubcode: ["CLOCK_UNAVAILABLE","SEQUENCE_UNAVAILABLE","FORMAT_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "NumSubcode" }
    ops:
      - name: "allocate_invoice_id"
        inputs:
          customer_id: { primitive: "string" }
          now: { type: "Timestamp" }
        outputs:
          invoice_id: { primitive: "string" }
        returns: { ok: { outputs: ["invoice_id"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["clock"]
        pre: []
        post: []

  - identity: { id: "fin.invoice.model_build_v1", version: "1.0.0", manufacturer: "FinCo", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      FinTotalsV1:
        struct:
          gross: { type: "Money" }
          tax:   { optional: { type: "Money" } }
      InvoiceModelV1:
        struct:
          invoice_id: { primitive: "string" }
          bill_to: { type: "AddressV1" }
          ship_to: { type: "AddressV1" }
          gross: { type: "Money" }
          currency: { enum: "ISO4217" }
    errors:
      subcodes:
        ModelSubcode: ["MISSING_FIELD","CURRENCY_MISMATCH","SERIALIZE_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "ModelSubcode" }
    ops:
      - name: "build_model"
        inputs:
          invoice_id: { primitive: "string" }
          bill_to: { type: "AddressV1" }
          ship_to: { type: "AddressV1" }
          gross: { type: "Money" }
        outputs:
          model_bytes: { primitive: "bytes" }
        returns: { ok: { outputs: ["model_bytes"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: ["len(model_bytes) > 0"]

  - identity: { id: "fin.pay.capture_stub_v1", version: "0.1.0", manufacturer: "FinCo", cert_tier: "Dev", allow_unknown: true }
    runtime_targets: ["remote:https"]
    capabilities_declared: ["net","clock"]
    errors:
      subcodes:
        PaySubcode: ["AUTH_FAIL","UPSTREAM_TIMEOUT","DECLINED","AMOUNT_INVALID"]
      KnownError: { class: "FailureClass", subcode: "PaySubcode" }
    ops:
      - name: "capture"
        inputs:
          invoice_id: { primitive: "string" }
          amount: { type: "Money" }
        outputs:
          captured: { primitive: "bool" }
        returns:
          ok:  { outputs: ["captured"] }
          err: { one_of: ["KnownError","UnknownErrorV1"] }   # allowed because Dev + allow_unknown
        requires_caps: ["net","clock"]
        pre: ["amount.minor_units > 0"]
        post: []

  # =========================
  # C) HR/IT domain (5)
  # =========================

  - identity: { id: "hr.policy.role_to_entitlements_v1", version: "1.0.0", manufacturer: "HRCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      HrRoleV1: { enum: ["Engineer","Sales","HR","IT","Support"] }
      EntitlementsV1:
        struct:
          groups: { list: { primitive: "string" } }
          needs_vpn: { primitive: "bool" }
          needs_github: { primitive: "bool" }
      EmployeeV1:
        struct:
          employee_id: { primitive: "string" }
          name: { primitive: "string" }
          email: { type: "EmailAddress" }
          role: { type: "HrRoleV1" }
          country: { enum: "CountryCode" }
    errors:
      subcodes:
        EntSubcode: ["ROLE_UNKNOWN","COUNTRY_UNSUPPORTED","POLICY_TABLE_MISSING"]
      KnownError: { class: "FailureClass", subcode: "EntSubcode" }
    ops:
      - name: "compute"
        inputs: { emp: { type: "EmployeeV1" } }
        outputs: { ents: { type: "EntitlementsV1" } }
        returns: { ok: { outputs: ["ents"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "hr.doc.employee_pack_model_v1", version: "1.0.0", manufacturer: "HRCo", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        PackSubcode: ["SERIALIZE_FAILURE","MISSING_FIELD"]
      KnownError: { class: "FailureClass", subcode: "PackSubcode" }
    ops:
      - name: "build_model"
        inputs:
          emp: { type: "EmployeeV1" }
          ents: { type: "EntitlementsV1" }
        outputs:
          model_bytes: { primitive: "bytes" }
        returns: { ok: { outputs: ["model_bytes"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: ["len(model_bytes) > 0"]

  - identity: { id: "it.provision.account_create_v1", version: "1.0.0", manufacturer: "ITCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["remote:https"]
    capabilities_declared: ["net","secrets_read","clock"]
    local_types:
      AccountRefV1: { struct: { account_id: { primitive: "string" } } }
    errors:
      subcodes:
        AcctSubcode: ["AUTH_FAIL","UPSTREAM_TIMEOUT","EMPLOYEE_INVALID","ACCOUNT_EXISTS"]
      KnownError: { class: "FailureClass", subcode: "AcctSubcode" }
    ops:
      - name: "create"
        inputs:
          emp: { type: "EmployeeV1" }
          creds: { primitive: "bytes" }
        outputs:
          acct: { type: "AccountRefV1" }
        returns: { ok: { outputs: ["acct"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["net","secrets_read","clock"]
        pre: []
        post: []

  - identity: { id: "it.provision.group_assign_v1", version: "1.0.0", manufacturer: "ITCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["remote:https"]
    capabilities_declared: ["net","secrets_read","clock"]
    errors:
      subcodes:
        GroupSubcode: ["AUTH_FAIL","UPSTREAM_TIMEOUT","GROUP_NOT_FOUND","ASSIGNMENT_REJECTED"]
      KnownError: { class: "FailureClass", subcode: "GroupSubcode" }
    ops:
      - name: "assign"
        inputs:
          acct: { type: "AccountRefV1" }
          ents: { type: "EntitlementsV1" }
          creds: { primitive: "bytes" }
        outputs:
          ok: { primitive: "bool" }
        returns: { ok: { outputs: ["ok"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["net","secrets_read","clock"]
        pre: []
        post: []

  - identity: { id: "it.provision.device_request_v1", version: "1.0.0", manufacturer: "ITCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["remote:https"]
    capabilities_declared: ["net","clock"]
    local_types:
      DeviceSpecV1: { struct: { sku: { primitive: "string" }, notes: { optional: { primitive: "string" } } } }
      DeviceReqV1:  { struct: { request_id: { primitive: "string" } } }
    errors:
      subcodes:
        DevReqSubcode: ["UPSTREAM_TIMEOUT","INVALID_ADDRESS","SKU_UNAVAILABLE","REQUEST_REJECTED"]
      KnownError: { class: "FailureClass", subcode: "DevReqSubcode" }
    ops:
      - name: "request"
        inputs:
          emp: { type: "EmployeeV1" }
          ship_to: { type: "AddressV1" }
          device: { type: "DeviceSpecV1" }
        outputs:
          req: { type: "DeviceReqV1" }
        returns: { ok: { outputs: ["req"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["net","clock"]
        pre: []
        post: []

  # =========================
  # D) Ops/Incident domain (4)
  # =========================

  - identity: { id: "ops.ingest.ticket_v1", version: "1.0.0", manufacturer: "OpsCo", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      TicketRawV1: { struct: { source: { primitive: "string" }, payload: { primitive: "bytes" } } }
      TicketV1:
        struct:
          ticket_id: { primitive: "string" }
          subject: { primitive: "string" }
          body: { type: "Text" }
          customer_id: { primitive: "string" }
    errors:
      subcodes:
        IngestSubcode: ["PAYLOAD_INVALID","MISSING_FIELD","DECODE_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "IngestSubcode" }
    ops:
      - name: "ingest"
        inputs: { raw: { type: "TicketRawV1" } }
        outputs: { t: { type: "TicketV1" } }
        returns: { ok: { outputs: ["t"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "ops.classify.severity_v1", version: "1.0.0", manufacturer: "OpsCo", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      SeverityV1: { enum: ["SEV1","SEV2","SEV3","SEV4"] }
      CategoryV1: { enum: ["OUTAGE","BILLING","SECURITY","PERFORMANCE","OTHER"] }
    errors:
      subcodes:
        ClsSubcode: ["MODEL_MISSING","INPUT_TOO_LARGE","CLASSIFY_FAILURE"]
      KnownError: { class: "FailureClass", subcode: "ClsSubcode" }
    ops:
      - name: "classify"
        inputs: { t: { type: "TicketV1" } }
        outputs: { sev: { type: "SeverityV1" }, cat: { type: "CategoryV1" } }
        returns: { ok: { outputs: ["sev","cat"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "ops.remediate.playbook_v1", version: "1.0.0", manufacturer: "OpsCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    local_types:
      RemediationPlanV1:
        struct:
          steps: { list: { primitive: "string" } }
          notify_status_page: { primitive: "bool" }
    errors:
      subcodes:
        PlaySubcode: ["NO_PLAYBOOK","PLAYBOOK_INVALID","UNSUPPORTED_CATEGORY"]
      KnownError: { class: "FailureClass", subcode: "PlaySubcode" }
    ops:
      - name: "plan"
        inputs: { sev: { type: "SeverityV1" }, cat: { type: "CategoryV1" } }
        outputs: { plan: { type: "RemediationPlanV1" } }
        returns: { ok: { outputs: ["plan"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "ops.notify.customer_v1", version: "1.0.0", manufacturer: "OpsCo", cert_tier: "Hardened", allow_unknown: false }
    runtime_targets: ["remote:https"]
    capabilities_declared: ["net","secrets_read","clock"]
    errors:
      subcodes:
        NotifySubcode: ["AUTH_FAIL","UPSTREAM_TIMEOUT","RCPT_REJECTED","TEMPLATE_MISSING"]
      KnownError: { class: "FailureClass", subcode: "NotifySubcode" }
    ops:
      - name: "notify"
        inputs:
          t: { type: "TicketV1" }
          sev: { type: "SeverityV1" }
          msg: { type: "EmailMessageV1" }
          creds: { primitive: "bytes" }
        outputs:
          rcpt: { type: "EmailReceiptV1" }
        returns: { ok: { outputs: ["rcpt"] }, err: { one_of: ["KnownError"] } }
        requires_caps: ["net","secrets_read","clock"]
        pre: []
        post: []
```

```yaml
validation_report_version: "0.1"
system_id: "Finance.InvoiceFulfillment_v1"
timestamp_utc: "2026-02-16T00:00:00Z"  # example

inputs_declared:
  - order: fin.invoice.totaler_v1.FinOrderV1
  - ship_to: AddressV1
  - bill_to: AddressV1
  - vat_bps: i64
  - printer_zone: PrinterZoneV1
  - customer_email: EmailAddress

role_policy:
  required_tiers:
    tax_engine: Hardened
    numbering: Hardened
    email_sender: Hardened
    printer_router: Hardened
    pdf_render: Consumer
    audit: Hardened

selected_bom:
  - instance: now
    component_id: std.time.now_v1
    tier: Hardened
    role: numbering
    reason: ["requires clock for invoice id + receipts timestamps"]
  - instance: invno
    component_id: fin.invoice.numbering_v1
    tier: Hardened
    role: numbering
    reason: ["financial/legal identifier allocation"]
  - instance: total
    component_id: fin.invoice.totaler_v1
    tier: Hardened
    role: tax_engine
    reason: ["financial correctness"]
  - instance: is_eu
    component_id: std.pred.in_set_country_eu27_v1
    tier: Consumer
    role: pdf_render
    reason: ["pure predicate; no actuation"]
  - instance: vat
    component_id: fin.tax.vat_calc_v1
    tier: Hardened
    role: tax_engine
    reason: ["legal/financial correctness"]
  - instance: us_tax
    component_id: fin.tax.us_state_calc_v1
    tier: Hardened
    role: tax_engine
    reason: ["legal/financial correctness"]
  - instance: model
    component_id: fin.invoice.model_build_v1
    tier: Consumer
    role: pdf_render
    reason: ["pure serialization"]
  - instance: html
    component_id: doc.render.template_html_v1
    tier: Consumer
    role: pdf_render
  - instance: pdf
    component_id: doc.render.pdf_v1
    tier: Consumer
    role: pdf_render
  - instance: smtp_creds
    component_id: sec.secrets.get_v1
    tier: Hardened
    role: email_sender
    reason: ["secrets access gate"]
  - instance: email
    component_id: net.email.send_smtp_v1
    tier: Hardened
    role: email_sender
    reason: ["external network actuation"]
  - instance: print
    component_id: io.print.route_v1
    tier: Hardened
    role: printer_router
    reason: ["physical actuation"]
  - instance: sign
    component_id: std.crypto.sign_v1
    tier: Hardened
    role: audit
  - instance: audit
    component_id: obs.audit.append_signed_v1
    tier: Hardened
    role: audit

tier_compliance:
  status: PASS
  checks:
    - rule: "instance tier >= required tier for role"
      result: PASS

capability_plan:
  granted_capabilities:
    - clock
    - secrets_read
    - net
    - device_io
    - kv_write
  per_instance_requires:
    now: ["clock"]
    invno: ["clock"]
    smtp_creds: ["secrets_read"]
    email: ["net","secrets_read","clock"]
    print: ["device_io","clock"]
    audit: ["kv_write","clock"]
  capability_compliance:
    status: PASS
    notes:
      - "No instance requests fs_read/fs_write; none granted."
      - "email and print are the only actuators; both Hardened."

schematic:
  nodes:
    - total.sum_net
    - is_eu.is_eu27
    - vat.compute_vat
    - us_tax.compute_state_tax
    - std.route.select2_money_v1.select_money
    - model.build_model
    - doc.render.template_html_v1.render_html
    - doc.render.pdf_v1.html_to_pdf
    - net.email.send_smtp_v1.send
    - io.print.route_v1.print_pdf
    - obs.audit.append_signed_v1.append
  branches:
    - id: tax_branch
      predicate: is_eu.is_eu
      when_true: "VAT path"
      when_false: "US state path"

type_closure:
  status: FAIL
  issues:
    - id: TYPE-001
      severity: ERROR
      description: "US-state tax branch requires ship_to.us_state, but ship_to.us_state is optional in AddressV1."
      where: "connect ship_to.us_state -> us_tax.ship_state"
      required_fix:
        - "Insert std.data.project_address_us_state_v1.get_us_state adapter"
        - "OR add explicit branch guard: ship_to.us_state present else raise INVALID_INPUT"
      why_this_is_good:
        - "Prevents silent null/None coercion; strict typing forces explicit handling."

branch_completeness:
  status: WARN
  notes:
    - "Branch predicate covers EU vs non-EU. Non-EU assumed US-state path; but if country is not US, this should be UNSUPPORTED."
  required_fix:
    - "Add predicate ship_to.country == US (std.pred.equals_v1 or a dedicated country==US pred) and use select3 with else->UNSUPPORTED."

failure_closure:
  status: WARN
  findings:
    - "Tax calculators enumerate STATE_UNSUPPORTED/COUNTRY_UNSUPPORTED; current design routes non-US/non-EU into US path → likely STATE_UNSUPPORTED."
    - "Recommendation: make UNSUPPORTED explicit at system level rather than letting it emerge as downstream error."

unknown_error_policy:
  status: PASS
  notes:
    - "No Dev-tier components used in this system build."
    - "UnknownErrorV1 is forbidden for selected components; catalog indicates allow_unknown=false."

datasheet_contract_checks:
  status: PASS_WITH_CONDITIONS
  executed:
    - "fin.invoice.totaler_v1.sum_net: pre/post sample=200"
    - "fin.tax.vat_calc_v1.compute_vat: pre/post sample=200"
    - "fin.tax.us_state_calc_v1.compute_state_tax: pre/post sample=200"
    - "doc.render.pdf_v1.html_to_pdf: post sample=100"
  blocked_by:
    - "TYPE-001 must be resolved before end-to-end run."

overall:
  status: FAIL
  summary:
    - "Fail due to strict type closure in US-state branch (AddressV1.us_state optional)."
    - "Once fixed, system is expected to PASS tier + capability + contract checks."
```

## Additional Catalog Components (Predicate, Router, Adapter) (Turn 44, assistant)

```yaml
- identity: { id: "std.pred.equals_country_us_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
  runtime_targets: ["wasm32-wasi"]
  capabilities_declared: []
  errors:
    subcodes:
      CUSubcode: ["COUNTRY_ENUM_INVALID"]
    KnownError: { class: "FailureClass", subcode: "CUSubcode" }
  ops:
    - name: "is_us"
      inputs: { country: { enum: "CountryCode" } }
      outputs: { is_us: { primitive: "bool" } }
      returns: { ok: { outputs: ["is_us"] }, err: { one_of: ["KnownError"] } }
      requires_caps: []
      pre: []
      post: []
```

```yaml
- identity: { id: "std.route.select3_money_or_unsupported_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
  runtime_targets: ["wasm32-wasi"]
  capabilities_declared: []
  errors:
    subcodes:
      Sel3Subcode: ["NO_BRANCH_TRUE","MISSING_BRANCH_INPUT"]
    KnownError: { class: "FailureClass", subcode: "Sel3Subcode" }
  ops:
    - name: "select_money_or_unsupported"
      inputs:
        sel1: { primitive: "bool" }   # EU?
        sel2: { primitive: "bool" }   # US?
        a:    { type: "Money" }       # EU path result
        b:    { type: "Money" }       # US path result
      outputs:
        out:  { type: "Money" }
      returns:
        ok:  { outputs: ["out"] }
        err: { one_of: ["KnownError"] }  # caller treats NO_BRANCH_TRUE as UNSUPPORTED at system boundary
      requires_caps: []
      pre: []
      post: []
```

```text
# existing
is_eu = std.pred.in_set_country_eu27_v1.is_eu27(ship_to.country)

# new
is_us = std.pred.equals_country_us_v1.is_us(ship_to.country)

# existing EU path
net = fin.invoice.totaler_v1.sum_net(order).net
eu_gross = fin.tax.vat_calc_v1.compute_vat(net, ship_to.country, vat_bps).gross

# updated US path with explicit adapter
ship_state = std.data.project_address_us_state_v1.get_us_state(ship_to).state
us_gross   = fin.tax.us_state_calc_v1.compute_state_tax(net, ship_state).gross

# new select3
gross_money =
  std.route.select3_money_or_unsupported_v1.select_money_or_unsupported(
    sel1=is_eu.is_eu,
    sel2=is_us.is_us,
    a=eu_gross,
    b=us_gross
  )
```

```yaml
type_closure:
  status: PASS
  fixes_applied:
    - id: TYPE-001
      action: "Inserted std.data.project_address_us_state_v1.get_us_state adapter"
      new_wiring: "ship_to -> get_us_state.addr; get_us_state.state -> us_tax.ship_state"

branch_completeness:
  status: PASS
  fixes_applied:
    - action: "Added std.pred.equals_country_us_v1 and replaced 2-way branch with select3_money_or_unsupported"
    - behavior: "If not EU and not US, select emits NO_BRANCH_TRUE which is escalated as UNSUPPORTED at system boundary"

failure_closure:
  status: PASS_WITH_NOTE
  notes:
    - "System-level mapping recommended: select3 NO_BRANCH_TRUE -> FailureClass.UNSUPPORTED (explicit)."
    - "All component error enums remain fully explicit; no INTERNAL; no UNKNOWN permitted in this build."

overall:
  status: PASS
  summary:
    - "Tier compliance PASS"
    - "Capability compliance PASS"
    - "Type closure PASS"
    - "Branch completeness PASS (EU/US else UNSUPPORTED)"
    - "No Dev-tier/UnknownError components used"
```

## Updated Catalog Entries and Wiring (Turn 46, assistant)

```yaml
- identity: { id: "std.pred.equals_country_us_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        CUSubcode: ["COUNTRY_ENUM_INVALID"]
      KnownError: { class: "FailureClass", subcode: "CUSubcode" }
    ops:
      - name: "is_us"
        inputs: { country: { enum: "CountryCode" } }
        outputs: { is_us: { primitive: "bool" } }
        returns: { ok: { outputs: ["is_us"] }, err: { one_of: ["KnownError"] } }
        requires_caps: []
        pre: []
        post: []

  - identity: { id: "std.route.select3_money_or_unsupported_v1", version: "1.0.0", manufacturer: "StdLib", cert_tier: "Consumer", allow_unknown: false }
    runtime_targets: ["wasm32-wasi"]
    capabilities_declared: []
    errors:
      subcodes:
        Sel3Subcode: ["NO_BRANCH_TRUE","MISSING_BRANCH_INPUT"]
      KnownError: { class: "FailureClass", subcode: "Sel3Subcode" }
    ops:
      - name: "select_money_or_unsupported"
        inputs:
          sel1: { primitive: "bool" }
          sel2: { primitive: "bool" }
          a:    { type: "Money" }
          b:    { type: "Money" }
        outputs:
          out:  { type: "Money" }
        returns:
          ok:  { outputs: ["out"] }
          err: { one_of: ["KnownError"] }
        requires_caps: []
        pre: []
        post: []
```

```text
is_eu = std.pred.in_set_country_eu27_v1.is_eu27(ship_to.country)
is_us = std.pred.equals_country_us_v1.is_us(ship_to.country)

net     = fin.invoice.totaler_v1.sum_net(order).net
eu_gross= fin.tax.vat_calc_v1.compute_vat(net, ship_to.country, vat_bps).gross

state   = std.data.project_address_us_state_v1.get_us_state(ship_to).state
us_gross= fin.tax.us_state_calc_v1.compute_state_tax(net, state).gross

gross_money =
  std.route.select3_money_or_unsupported_v1.select_money_or_unsupported(
    sel1=is_eu.is_eu,
    sel2=is_us.is_us,
    a=eu_gross,
    b=us_gross
  )
```

