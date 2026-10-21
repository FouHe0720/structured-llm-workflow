# Evaluation results

Mode: **mock**; model: `mock-fixture-v1`.

Mock/fault-fixture metrics are workflow checks, not real LLM accuracy. Gold labels have not received independent human review.

| Metric | Value |
|---|---|
| generated_at | 2026-10-21T12:50:46.981509+08:00 |
| python_version | 3.12.15 |
| prompt_version | v1-0204fd73519d |
| dataset_sha256 | a46d5ee92185c1bd04228a1b098417eb2a94920fbc26ae1cc1679582cf5d2b8d |
| mode | mock |
| model | mock-fixture-v1 |
| cases | 40 |
| schema_validation_rate | 0.925 |
| call_validation_success_rate | 0.9756838905775076 |
| required_field_accuracy | 0.9375 |
| correct_fields | 180 |
| total_fields | 192 |
| type_accuracy | 0.9 |
| unsupported_claim_rate | 0.0 |
| unsupported_claims | 0 |
| claim_count | 141 |
| rejected_unsupported_attempts | 2 |
| model_calls | 329 |
| p50_latency_ms | 3.0751670001336606 |
| p95_latency_ms | 3.834578999885707 |
| expectations_met | 39 |

See eval/README.md for denominators and the deliberate valid-schema misclassification.
