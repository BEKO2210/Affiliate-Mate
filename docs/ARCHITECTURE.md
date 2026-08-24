# Architecture

Affiliate-Mate separates **data acquisition**, **evidence**, **decision logic**,
and **content production** so that no single vendor or LLM becomes the system.

## Layers

### 1. Sources

Source adapters acquire candidate products and external signals. A source should
return normalized data and provenance, not decide whether a product is "good."

Planned source types:

- manual / CSV
- affiliate catalog API
- keyword and trend data
- video-search competition data
- user-supplied review exports

### 2. Normalization

All providers map into a stable internal product model. This prevents Amazon,
YouTube, an LLM provider, or any other service from leaking vendor-specific
assumptions into the opportunity engine.

### 3. Evidence store

A later milestone will persist observations with:

- source
- observed timestamp
- market / locale
- raw value
- normalized value
- confidence / quality
- expiry policy

This matters because prices, commissions, competition, and search demand change.

### 4. Opportunity engine

The engine is deterministic by default. It produces both a score and a
breakdown. A product can also be rejected before scoring if required evidence is
missing or economics are below a configured floor.

### 5. Human approval checkpoint

No future publishing adapter should bypass an explicit approval state. This is
where a creator verifies product claims, rights, affiliate disclosures, and
whether the planned content adds genuine value.

### 6. Production adapters

Script, voice, video, thumbnail, and publishing tools belong at the edge of the
system. The core must remain useful even when none of them are configured.

## Design constraints

- no dependency on scraping private or brittle page markup
- no secret keys committed to the repository
- no revenue claim without visible assumptions
- deterministic tests for ranking and rejection logic
- adapters must fail closed when provider data is incomplete
- timestamps and provenance must survive normalization
