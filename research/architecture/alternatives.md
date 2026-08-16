# Competing architecture families

All candidates must be measured on `query_corpus.json`. No candidate is the
default winner.

## C0 — Current architecture

Semantic descriptor + three-family Query Spec + profile-specific imperative
pipeline + Python operators + runtime enforcement.

Expected strength: working tested vertical slice and strong evidence/reporting
contracts. Expected weakness: strategy hardcoding, two runtimes, no data/SQL
planning contract, and limited composition.

## C1 — Semantic-heavy

Store metric relationships, allowed analyses, decomposition identities,
diagnostic recipes, and data mappings in the semantic layer. A thin executor
interprets the enriched model.

Falsification pressure: concept count, semantic/runtime coupling, and domain
recipe duplication. It may perform well for stable governed domains.

## C2 — Operator-centric

Expose a registry of strongly typed operators. The planner selects operators
and parameters; the runtime composes them. Semantic metadata exists chiefly to
satisfy operator input contracts.

Falsification pressure: can operator calls alone preserve question intent,
logical data requirements, conditional control, and evidence selection without
smuggling in an implicit IR?

## C3 — IR-centric with thin semantic layer

Bind nouns in a small semantic contract, compile intent into a typed analytical
DAG, derive logical data requirements, lower them through a backend adapter,
then execute registered canonical operators.

Falsification pressure: IR grammar growth, premature compiler machinery, and
whether simple questions become needlessly verbose.

## C4 — Three-contract compressed candidate

Only three logical contracts are primary:

1. Semantic: typed metric expressions, grain, dimensions, relationships.
2. Analytical: typed node signatures, invariants, result/evidence shapes.
3. Planning: a DAG of analytical nodes plus bound inputs and output selection.

Catalogs, domain packs, SQL adapters, reporting, and storage are authorities or
consumers around those contracts, not additional logical layers.

This is the initial leading simplification hypothesis, not a decision. The
first experiments will determine whether C4 is just C3 with clearer names or
whether it genuinely removes concepts.

