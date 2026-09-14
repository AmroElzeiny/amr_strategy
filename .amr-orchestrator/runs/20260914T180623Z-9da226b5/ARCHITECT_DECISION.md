# Architect decision — Prompt 4

## Classification

This mission is Deep because it spans independent contract schemas, financial execution authority, persistent lineage/idempotency, bounded asynchronous queues, concurrency locks, failure isolation, crash recovery, feedback integrity, secrets boundaries, and exchange safety.

## Decision

Implement only a fourth package. Packages 1–3 and their ZIPs are immutable inputs. Package 4 may bridge only through deterministic transport translation, validation, public invocation, and external routing metadata. It may not infer or recreate market features, strategy decisions, financial risk, order/protection behavior, or AI routing.

Schema-hash inequality is not itself failure. The supervisor must compare semantics and prove each mapping. An adapter is valid only when the source value and target value have identical meaning and precision, the original payload remains unchanged, the transformation is deterministic and explicit, and downstream integrity/lineage is preserved. Defaulting missing semantic evidence, manufacturing execution lifecycle state, or deriving risk/strategy values is not adaptation.

If actual Package 3 public interfaces cannot supply or reconcile a mandatory lifecycle capability and satisfying it would require Package 4 to own execution/position logic, the correct verdict is the user's required `BUILD FAILED — PACKAGE CONTRACT INCOMPATIBILITY`, not a mocked-only claim of complete production integration. Mocks may prove orchestration mechanics but cannot prove an absent real public interface.

## Safety posture

The run is Offline. No Demo authorization was given. All exchange/private/AI effects must be fake or mocked. Default product configuration must remain execution-off, dry-run-on, real-trading-off, and Testnet-free. The development snapshot status of Package 3 must be carried into final documentation and verdict.
