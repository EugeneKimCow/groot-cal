# Unresolved questions

1. Is `operation_family` a durable intent constraint or derivable plan metadata?
2. What is the smallest typed metric-expression language that covers sum,
   weighted rate, distinct, period-end balance, and derived metrics?
3. Is decomposition one operator parameterized by an algebra, or several
   estimand-specific primitives?
4. How should conditional branches reference typed result predicates without
   turning the IR into a general workflow language?
5. Which checks belong to semantic registration, data planning, operator
   preconditions, and postconditions respectively?
6. What logical data requirement is sufficient to generate correct SQL while
   preserving grain, ratio aggregation, filters, and time semantics?
7. Are plan comparison and event overlap canonical operators or domain idioms?
8. Can commerce VRM be expressed by generic metric expressions plus a
   decomposition convention, and how must interaction allocation be declared?
9. E-017 provisionally added `set_transition@v1` because additive contribution
   loses entrants, exits, and migrations. Can it lower to smaller canonical set
   operations without weakening the typed estimand or execution checks?
10. How should report/staleness workflows share the harness without bloating
    analytical IR?
11. E-017 established representative shadow parity across both pipelines. E-018
    must now test the public bundle, report, materialization, provenance, and
    failure boundary before even metric-level default routing can change.
12. How should real RDBMS pushdown be tested without letting a specific SQL
    dialect define the logical architecture?
13. E-011 found no error-quality advantage for explicit node classes on five
    representative plans. Whether generated typed builders remain ergonomic as
    the registry grows is an implementation-scale uncertainty, not an open
    logical-architecture fork.
14. E-016 accounted for every material clause in the governed corpus and
    improved the existing change paraphrases from 4/5 to 5/5 without free-form
    fallback. How well does the same contract perform on broader Korean wording
    and an LLM proposal adapter?
15. How should privacy, access control and multi-source freshness compose across
    stored results and reports?
16. E-016 produced a complete inventory for its governed Korean corpus and
    rejects unrecognized analytical language rather than hiding it as discourse.
    How should proposal recall expand without growing a brittle phrase list, and
    what held-out corpus is sufficient before any production planner trial?
17. E-013 period-end evaluation is proven only for already-monthly end snapshots.
    How should executable source grain and observation-time selection prevent a
    daily inventory table from being summed while still using the same strategy?
18. E-014 now rejects duplicate bindings at live typed-operator invocation.
    Should semantic catalog loading also reject them before any query reaches
    execution, and should that registration gate apply to every binding role?
19. E-019 kept the executor's stop-at-first-failure semantics because current
    fixtures cannot discriminate break versus per-branch isolation (typed
    metrics are single-axis; commerce gates are global). Which failure
    isolation contract should independent DAG branches have, and what fixture
    proves it, before drilldown or multi-source routing?
20. Commerce share_of_change suppression (§4.1) lives in the legacy kernel and
    has no consumer through the normalized view. When a renderer needs shares
    from the C4 payload, should suppression become a registered check on
    contribution@v1 or a reporting-contract rule?
21. E-019's route adapter declares the change label capability set
    (confirmed + suggestive). Should label capabilities move into operator
    registry contracts so adapters stop owning label policy?
22. E-021 showed both local models split "변동을 제품군별 기여로" into two
    analysis clauses (fail-closed), and read "어떻게 달라졌어" as delta while
    the paraphrase gold says contribution. Which readings are gold-label
    ambiguity versus proposal error, and should composite analysis phrases be
    prompt examples or registered composition vocabulary?
23. E-023 accepts ISO-week periods under the clause value kind still named
    "month". Renaming to "period" is a record-v2 wire change — when, and with
    what migration for stored binding records?
24. E-023 registered iso_week for the daily flow source and proved SQL value
    identity as pushdown increment 0. The open second half of #12/#17: when
    does execution authority move into SQL (with gates translated), and how is
    period-end observation-time selection declared for a daily balance source?
