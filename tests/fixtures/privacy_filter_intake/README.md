# Privacy Filter Intake Fixtures

Status: active test fixture  
Owner: Repository maintainers  
Purpose: PaperPipe-specific privacy-policy fixture set for evaluating OpenAI Privacy Filter or compatible PII span detectors.

This fixture set is intentionally small but policy-dense. It covers:
- private beta user contact data
- request audit and config/log secrets
- local runtime paths
- public scientific metadata that should remain visible
- DOI URLs and clinical trial identifiers
- Korean contact examples
- clean runtime-readiness text that should not produce findings

Use this fixture to measure both:
- missed redactions for private data and secrets
- preserve conflicts where public provenance-critical scientific metadata would be over-redacted

It is not a production benchmark and does not imply anonymization or compliance readiness.

