# Production Adapters

v0.6 introduces the production boundary. The goal is not to generate a video as fast as possible. The goal is to make it difficult for a stale approval, unsupported claim, modified artifact, or unreviewed package to reach a future live publisher.

## Invariants

Production code must preserve all of these:

1. A raw `APPROVED` state is insufficient. Production consumes `evaluate_approval_guard()`.
2. A `ProductionAuthorization` is bound to one approval event and one research SHA-256 digest.
3. Authorization is re-checked at the point of use; it is not a permanent capability.
4. Every structured factual script segment references one or more supported claim IDs.
5. Script claim IDs must belong to the same product and current approved research revision.
6. Production packages retain approval event ID and research digest.
7. Package signoff is bound to the exact package digest.
8. Any package mutation invalidates the previous signoff.
9. Artifact records are content-addressed with SHA-256 and byte length.
10. A strict publish dry-run verifies research lineage, script grounding, signoff, disclosure, required artifact kinds, and artifact bytes.
11. v0.6 contains no live publisher. The bundled YouTube publisher is planning-only and `side_effecting=False`.
12. External LLM/TTS/render implementations remain adapters. They do not become the trust root.

## Trust chain

```text
Research Workspace
      |
      v
ApprovalGuardReport
  raw APPROVED
  completeness PASS
  approval snapshot present
  approval snapshot current
      |
      v
ProductionAuthorization
  product_id
  approval_event_id
  research_digest
      |
      +------------------------------+
      |                              |
      v                              v
ScriptRequest                   metadata / thumbnail
approved claims only            explicit disclosure
claim IDs + source locators     no hidden publish
      |
      v
ScriptGenerator protocol
      |
      v
ScriptDocument
FACT segment -> claim IDs
      |
      v
validate_script_grounding()
      |
      v
ProductionPackage
research lineage
adapter plans
artifact manifest
      |
      v
human ProductionSignoff
bound to package SHA-256
      |
      v
publish-dry-run
      |
      +--> current research?        PASS/FAIL
      +--> package lineage?         PASS/FAIL
      +--> script grounding?        PASS/FAIL
      +--> signoff current?         PASS/FAIL
      +--> disclosure present?      PASS/FAIL
      +--> artifact set complete?   PASS/FAIL
      +--> artifact bytes match?    PASS/FAIL
      |
      v
ready_for_live_adapter
```

`ready_for_live_adapter=true` is still not a publish action. It means the package passed the local preconditions that a future live adapter must re-check.

## Versioned contracts

v0.6 defines:

```text
affiliate-mate.production-authorization.v1
affiliate-mate.script.v1
affiliate-mate.production-package.v1
affiliate-mate.production-signoff.v1
affiliate-mate.publish-plan.v1
```

Deserializers reject unknown schema versions rather than silently coercing them.

## Script generation

`ScriptGenerator` is provider-neutral. The request contains approved claims and precise source locators, not arbitrary raw pages. The default constraints explicitly prohibit invented specifications, guarantees, rankings, first-hand experience, and uncited factual statements.

The credential-free `StrictTemplateScriptGenerator` is intentionally conservative. It reuses approved claim text rather than pretending to write a polished review. It exists for deterministic tests and safe pipeline development.

A future LLM adapter must still return structured `FACT` segments with claim IDs and pass `validate_script_grounding()`.

Structural grounding cannot prove that generated prose is semantically faithful to a claim. This is why production package signoff remains a separate human checkpoint.

## Affiliate disclosures

`disclosure_template()` provides explicit German and English convenience text. It is not a jurisdiction-specific legal oracle. Callers can replace the spoken and description strings.

The production package requires the configured description disclosure to appear in the final metadata description. Users remain responsible for program-specific and jurisdiction-specific requirements.

## Metadata and thumbnail planning

`build_video_metadata()` creates deterministic metadata around an explicit affiliate URL and disclosure. Affiliate URLs must be absolute HTTP(S) URLs.

`build_thumbnail_brief()` deliberately tells render adapters not to add ratings, awards, prices, performance claims, or comparison badges unless those claims are explicitly approved.

## Adapter contracts

The production interfaces are:

- `ScriptGenerator`
- `TTSAdapter`
- `VideoRenderAdapter`
- `ThumbnailAdapter`
- `PublisherAdapter`

v0.6 ships deterministic planning adapters only:

```text
dry-run-tts-v1
dry-run-video-v1
dry-run-thumbnail-v1
dry-run-youtube-v1
```

They calculate content-derived input digests and expose planned parameters without contacting an external service.

A future live adapter should separate `plan` and `execute`. `execute` must accept a current production authorization and re-run the same guard immediately before side effects.

## Artifact manifest

Each external artifact record contains:

```text
logical_name
kind
relative path
media type
SHA-256
byte length
```

Paths reject absolute paths, parent traversal, and backslash ambiguity. When `artifact_root` is provided, the publish dry-run reads every artifact and compares the bytes with the manifest.

Required live-publish kinds currently are:

```text
script
narration
video
thumbnail
metadata
```

Captions can be present but are not yet a hard requirement.

## Package signoff

A research approval authorizes a research revision. It does not authorize arbitrary generated assets. Therefore v0.6 adds a second human checkpoint:

```text
ProductionSignoff {
  product_id
  package_digest
  actor
  reason
  created_at
}
```

The package digest covers script, metadata, thumbnail brief, adapter plans, artifact records, research digest, approval event, and creation time. Editing any of these fields invalidates the old signoff.

The signoff is an integrity binding and audit record, not a cryptographic identity signature. A future milestone can add asymmetric signatures without changing the package digest model.

## CLI

The fifth CLI is:

```text
affiliate-mate-production
```

Authorize the current research revision:

```bash
affiliate-mate-production authorize affiliate-mate.sqlite3 demo-headphones-1
```

Export an LLM-neutral grounded request:

```bash
affiliate-mate-production script-request \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  --title "Example Headphones" \
  --language de \
  --locale de-DE \
  --output script-request.json
```

Generate the deterministic baseline script:

```bash
affiliate-mate-production script-template \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  --title "Example Headphones" \
  --language de \
  --locale de-DE \
  --output script.json
```

Build a production package:

```bash
affiliate-mate-production package \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  script.json \
  --title "Example Headphones" \
  --affiliate-url "https://example.invalid/affiliate" \
  --locale de-DE \
  --output production-package.json
```

Sign the exact package:

```bash
affiliate-mate-production signoff \
  production-package.json \
  --actor editor@example \
  --reason "Final script, metadata, disclosure, thumbnail brief, and assets reviewed." \
  --output production-signoff.json
```

Run the non-side-effecting publish gate:

```bash
affiliate-mate-production publish-dry-run \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  production-package.json \
  --signoff production-signoff.json \
  --artifact-root ./render-output \
  --output publish-plan.json
```

For development before rendered artifacts exist, `--allow-missing-artifacts` bypasses only the artifact presence/integrity requirement. It should not be used as a future live-publish precondition.

## External LLM integration

A safe integration should:

1. export a versioned grounded script request;
2. send only that request to the model;
3. require structured script JSON;
4. validate the schema version;
5. run `validate_script_grounding()`;
6. re-check research approval before rendering;
7. inspect generated copy;
8. sign the exact production package;
9. run the publish dry-run;
10. only then allow a separately implemented live publisher.

Do not give a generation model publisher credentials merely because it can produce a script.

## Threat model notes

v0.6 directly addresses stale research approvals, approval TOCTOU, cross-product claim references, factual segments without claim lineage, package edits after signoff, artifact replacement after packaging, path traversal, missing disclosures, accidental bundled live side effects, and silent production-schema coercion.

It does not claim to solve semantic hallucination inside a claim-referenced sentence, malicious human approval, a compromised machine, stolen external credentials, media rights, jurisdiction-specific law, provider account enforcement, or platform moderation decisions.