# Validation Reports and Error Handling

*Extracted from: Server-Side WASM Components conversation (ChatGPT)*

The assembler validates systems against the catalog: type closure (all ports
match), branch completeness (all paths handled), failure closure (all errors
propagated). Reports are machine-readable YAML.

---

## Validation Fixes: Type Closure, Branch Completeness (Turn 44, assistant)

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

## Error Propagation and Unsupported-Input Handling (Turn 48, assistant)

```text
Sel3Subcode.NO_BRANCH_TRUE
```

```text
FailureClass = UNSUPPORTED
subcode = NO_TAX_ENGINE_FOR_COUNTRY
```

```text
SupportedCountries = EU27 ∪ US
Else → UNSUPPORTED
```

```text
Unsupported input handling: PASS
Unsupported countries → FailureClass.UNSUPPORTED
```

```text
System requires: tax engine supporting Country=CA
Current system: UNSUPPORTED for CA
```

```text
Finance.InvoiceFulfillment_v2
```

```text
fin.tax.canada_calc_v1
```

```text
fin.tax.generic_zero_rate_v1
```

```text
Supported:
  EU27 VAT
  US State Tax
Unsupported:
  All other countries
```

