# groot-cal Canonical Architecture Research Harness

## 0. 이 문서의 목적

이 작업의 목적은 groot-cal에 기능을 더 많이 구현하는 것이 아니다.

현재 존재하는 구조와 아이디어를 반복적으로 검토하고, 대안을 만들고, 반례를 찾고, 불필요한 abstraction을 제거함으로써 다음 질문에 답하는 것이다.

> **BI 사용자가 자연어로 질문하면, 필요한 데이터를 RDBMS에서 추출하고, 질문 의도에 맞는 수리·통계적 연산을 수행하여 근거 있는 답을 생성하는 시스템을 가장 단순하고 canonical하게 어떻게 구성할 것인가?**

이번 작업은 일반적인 feature development가 아니라 **architecture discovery experiment**이다.

한 번 설계안을 만든 뒤 구현하는 방식이 아니라 다음 과정을 반복한다.

```text
Hypothesis
→ Architecture
→ Counterexample
→ Critique
→ Alternative
→ Simplification
→ Implementation
→ Regression Test
→ Revised Hypothesis
```

가능하다면 충분히 긴 reasoning cycle을 수행한다.

단, 오래 실행하는 것 자체가 목적은 아니다.

목적은 반복 탐색을 통해 **더 적은 개념으로 더 많은 분석 질의를 안정적으로 표현하는 구조에 수렴하는 것**이다.

---

# 1. groot-cal의 목표

groot-cal이 궁극적으로 수행해야 하는 기본 흐름은 다음과 같다.

```text
User Question
    ↓
Intent Interpretation
    ↓
Semantic Binding
    ↓
Analytical Planning
    ↓
Data Requirement
    ↓
RDBMS Query
    ↓
Mathematical / Statistical Operation
    ↓
Validation
    ↓
Evidence
    ↓
Answer
```

예를 들어 사용자가 다음과 같이 질문한다.

> 지난달 매출 감소의 가장 큰 원인은 무엇인가?

groot-cal은 단순히 SQL을 생성해서 데이터를 보여주는 것이 아니다.

다음과 같은 분석 계획을 만들어야 한다.

```text
metric
    revenue

comparison
    previous month vs current month

analysis
    contribution decomposition

dimensions
    product
    customer
    region

objective
    identify positive/negative drivers
```

그 후 필요한 데이터만 RDBMS에서 가져오고 deterministic computation을 수행한다.

---

# 2. 핵심 설계 가설

현재 가장 우선적으로 검증할 architecture hypothesis는 다음이다.

> **Semantic Layer = nouns**
>
> **Canonical Operators = verbs**
>
> **Domain Packs = analytical idioms**
>
> **Analytical IR / DAG = sentence**
>
> **Agent Harness = compiler**

이를 절대적인 정답으로 간주하지 않는다.

이번 실험에서 적극적으로 반증해야 할 **working hypothesis**이다.

---

# 3. Hypothesis A — Semantic Layer는 Noun을 정의한다

Semantic Layer의 책임은 다음 질문에 답하는 것이다.

> 데이터가 업무적으로 무엇을 의미하는가?

예:

```text
Metric
    revenue
    quantity
    unit_price

Dimension
    product
    customer
    region

Entity
    customer
    supplier
    product

Relationship
    order → customer
    order → product
    product → category

Grain
    order_line

Time
    order_date
    ship_date
```

추가적으로 metric 간의 수학적 관계도 semantic contract의 일부가 될 수 있다.

예:

```text
revenue = quantity × unit_price

average_unit_price = revenue / quantity
```

중요한 것은 semantic layer가 특정 분석 알고리즘을 무제한으로 포함하지 않도록 하는 것이다.

다음 구분을 검증한다.

```text
Semantic Layer
    what something means

Analytical Operator
    what mathematical operation can be performed
```

---

# 4. Hypothesis B — Analytical Operator는 Verb를 정의한다

가능한 한 domain-independent한 canonical analytical primitives를 정의한다.

초기 후보는 다음과 같다.

```text
aggregation

comparison
delta
ratio
growth_rate

ranking

decomposition
weighted_decomposition

distribution
quantile

trend
slope
acceleration
change_point

outlier
robust_zscore

concentration
entropy
hhi

correlation
regression

forecast

counterfactual
```

이 목록 역시 정답이 아니다.

다음 질문을 반복한다.

> 이 operator가 정말 primitive여야 하는가?

그리고:

> 더 작은 operator들의 composition으로 표현할 수 있는가?

가능하면 새로운 operator를 추가하기보다 기존 primitive의 composition을 선호한다.

---

# 5. Hypothesis C — Domain Pack은 Analytical Idiom을 정의한다

Domain Pack은 새로운 계산 엔진을 만드는 곳이 아니다.

다음을 연결하는 역할을 한다.

```text
domain language
        ↓
semantic object
        +
canonical analytical pattern
```

예를 들어 SCM에서는:

```text
"납기 악화 원인을 찾아라"
```

를 다음과 같이 해석할 수 있다.

```yaml
metric: on_time_delivery_rate

dimensions:
  - supplier
  - plant
  - material
  - lane

preferred_analysis:
  - contribution_decomposition
  - trend
  - concentration
```

Sales에서는:

```text
"평균 판매단가 상승의 원인을 찾아라"
```

가 다음으로 연결될 수 있다.

```yaml
metric: average_selling_price

metric_relationship:
  revenue: quantity * price

preferred_analysis:
  - mix_rate_decomposition
```

Domain Pack이 canonical operator를 복제하지 않는 구조를 우선 검토한다.

---

# 6. 가장 중요한 후보 abstraction — Analytical IR

이번 architecture research에서 특히 집중해서 검토한다.

LLM이 직접 SQL과 계산 절차를 자유롭게 생성하는 구조 대신:

```text
Question
    ↓
LLM / Planner
    ↓
Typed Analytical IR
    ↓
Deterministic Runtime
```

구조를 우선 검증한다.

예:

사용자 질문:

```text
올해 2분기 매출 증가에서
어떤 제품군이 가장 많이 기여했는가?
```

내부 representation 후보:

```yaml
analysis:
  metric: revenue

comparison:
  baseline: 2026-Q1
  target: 2026-Q2

operation:
  type: contribution_decomposition

breakdown:
  - product_category

ranking:
  measure: contribution
  order: descending

output:
  top_drivers: 5
  offsets: true
```

이 representation은 다음 사이의 contract 역할을 한다.

```text
LLM
↕
Analytical IR
↕
Semantic Resolver
SQL Planner
Operator Runtime
Validator
```

우리가 찾아야 하는 핵심 중 하나는:

> **Analytical IR의 최소 grammar는 무엇인가?**

이다.

---

# 7. 중요한 설계 원칙

가능하면 다음 원칙을 유지한다.

## 7.1 LLM은 계산기가 아니라 Planner이다

우선 검증할 원칙:

> LLM은 최종 숫자를 생성하는 주체가 아니라  
> 실행 가능한 분석 계획을 생성하는 주체이다.

예:

LLM이 직접:

```text
매출은 13.7% 감소했습니다.
```

라고 만들어내지 않는다.

대신:

```yaml
metric: revenue
comparison: month_over_month
operation: growth_rate
```

를 생성한다.

13.7%는 deterministic runtime에서 계산한다.

---

## 7.2 SQL 생성과 Analysis Planning을 분리한다

다음 구조를 우선한다.

```text
Question
    ↓
Analytical Intent
    ↓
Semantic Binding
    ↓
Analytical IR
    ↓
Data Requirements
    ↓
SQL
```

다음을 피한다.

```text
Question
    ↓
LLM
    ↓
SQL
```

SQL은 최종 목적이 아니라 분석을 수행하기 위한 data acquisition mechanism이다.

---

## 7.3 Diagnosis를 반드시 독립 Layer로 만들 필요는 없다

기존의 다음 개념도 적극적으로 반증한다.

```text
Calculation Layer
Diagnosis Layer
Semantic Layer
```

가 실제 physical/logical architecture에서 각각 독립된 layer여야 하는가?

대안 가설은 다음이다.

> 상당수 Diagnosis는 canonical operator들의 conditional DAG일 수 있다.

예:

```text
Revenue Decline
        ↓
Contribution Decomposition
        ↓
 ┌───────────────┐
 │               │
dominant       diffuse
 │               │
 ↓               ↓
concentration   trend
 │
 ↓
mix/rate
```

따라서 Diagnosis가 저장된 독립 계층인지,

아니면 runtime에서 생성되는 Analytical DAG인지 검증한다.

---

# 8. 연구 방법

이번 작업에서는 처음 발견한 architecture에 빠르게 수렴하지 않는다.

반드시 복수 대안을 만든다.

최소한 다음 역할을 반복적으로 수행한다.

```text
Architect
    architecture candidate 제시

Minimalist
    abstraction 삭제 시도

Red Team
    architecture를 깨는 query 생성

Domain Analyst
    실제 BI/SCM 질의로 검증

Compiler Designer
    IR과 execution model 검토

Verifier
    regression 및 invariant 검증
```

실제 multi-agent framework를 만들 필요는 없다.

하나의 Codex session에서도 역할을 순차적으로 바꾸며 실행할 수 있다.

추천 cycle:

```text
Generate
→ Criticize
→ Generate Counterexamples
→ Compare Alternatives
→ Simplify
→ Implement Minimal Change
→ Test
→ Record Findings
→ Repeat
```

---

# 9. Architecture Counterexample 방식

수학에서 conjecture를 반례로 검증하듯이 architecture도 query로 공격한다.

대표 query corpus를 만든다.

초기 예:

### Q1 — Contribution

```text
전월 대비 매출 감소에서
어떤 제품군이 가장 크게 기여했는가?
```

### Q2 — Mix vs Rate

```text
평균 판매단가 상승이
개별 제품 가격 인상 때문인가,
고가 제품 판매 비중 증가 때문인가?
```

### Q3 — Trend

```text
매출은 증가하고 있지만
증가 속도가 둔화되고 있는가?
```

### Q4 — Outlier / Concentration

```text
평균 lead time 상승이
전체 supplier에서 나타나는 현상인가,
일부 supplier의 extreme value 때문인가?
```

### Q5 — Multi-dimensional Driver

```text
매출 감소에서 제품, 지역, 고객 가운데
가장 큰 driver는 무엇인가?
```

### Q6 — Counterfactual

```text
supplier delay가 없었다면
service level 하락이 여전히 발생했는가?
```

### Q7 — Price / Volume / Mix

```text
매출 변화가
volume, price, mix 중 무엇 때문인가?
```

### Q8 — Offset

```text
전체 매출은 거의 변하지 않았지만
내부적으로 크게 증가한 segment와
이를 상쇄한 segment가 있는가?
```

각 query마다 반드시 묻는다.

```text
현재 architecture로 표현 가능한가?
```

표현 불가능하다면 즉시 abstraction을 추가하지 않는다.

먼저 묻는다.

```text
기존 primitive의 composition으로 표현 가능한가?
```

그 다음에만 새로운 primitive를 검토한다.

---

# 10. Query Corpus를 Architecture Test Suite로 사용한다

가능하면 다음 구조를 만든다.

```text
tests/
  query_corpus/
    contribution/
    mix_rate/
    trend/
    anomaly/
    concentration/
    counterfactual/
    multi_dimension/
```

각 test에는 최소한 다음을 저장한다.

```yaml
id: sales_contribution_001

question:
  "지난달 매출 감소의 가장 큰 제품군 원인은?"

expected_semantics:
  metric: revenue

expected_analysis:
  operation: contribution_decomposition

expected_breakdown:
  - product_category

expected_comparison:
  type: period_over_period
```

모든 architecture change 후 corpus를 다시 실행한다.

목표는 특정 prompt의 성공이 아니라:

> architecture change에도 전체 query population이 계속 표현 가능한가?

를 확인하는 것이다.

---

# 11. 수렴에 절대적인 정답 기준은 없다

이 연구는 수학 문제처럼 다음 상태를 갖지 않는다.

```text
proof complete = true
```

우리는 여러 design trade-off 사이에서 architecture를 선택한다.

따라서 하나의 objective function으로 정답을 정의하지 않는다.

하지만 완전히 정성적인 평가만 하는 것도 피한다.

**정량적 proxy + 정성적 architectural judgment**를 함께 사용한다.

---

# 12. Quantitative Proxy Metrics

각 architecture iteration마다 가능하면 다음 값을 기록한다.

## 12.1 Query Coverage

```text
현재 architecture로 표현 가능한 query 비율
```

예:

```text
94 / 100 = 94%
```

---

## 12.2 Concept Count

core architecture에서 사용하는 개념 수.

예:

```text
semantic concepts
operator types
IR node types
special planner rules
domain-specific exceptions
```

가능하면 증가하지 않도록 한다.

---

## 12.3 Exception Count

다음과 같은 특수 처리의 개수:

```text
if domain == SCM
if query == mix_rate
special_case
custom_handler
fallback_prompt
```

exception이 증가한다면 architecture가 canonical하지 않을 가능성을 의심한다.

---

## 12.4 Operator Reuse Ratio

domain-specific analysis 중 canonical operator composition으로 표현되는 비율.

예:

```text
canonical composition: 42
custom implementation: 8

reuse ratio = 84%
```

---

## 12.5 Deterministic Execution Ratio

전체 execution DAG 중 deterministic runtime이 담당하는 비율을 관찰한다.

정확한 공식일 필요는 없지만 다음 경향을 본다.

```text
LLM judgment ↓

typed plan
SQL execution
math operation
validation
invariant check
↑
```

---

## 12.6 Planning Stability

같거나 유사한 질문을 여러 표현으로 바꿨을 때 비슷한 Analytical IR이 나오는지 확인한다.

예:

```text
"매출 감소의 주요 원인은?"

"매출이 왜 줄었나?"

"어느 부문이 매출 하락을 만들었나?"
```

이들이 가능한 한 동일한 analytical pattern으로 normalize되는 것이 바람직하다.

---

## 12.7 Regression Failure Count

architecture 변경 후 기존 query corpus에서 실패한 수.

```text
new capability gained
vs
previous capability broken
```

을 항상 함께 본다.

---

# 13. Qualitative Evaluation Criteria

정량 proxy만 최적화하면 안 된다.

각 architecture candidate를 다음 기준으로 평가한다.

## Minimality

같은 문제를 더 적은 concept로 설명할 수 있는가?

## Coverage

실제 BI 질의를 충분히 표현할 수 있는가?

## Composability

복잡한 분석을 primitive들의 조합으로 만들 수 있는가?

## Determinism

LLM의 자유 판단을 deterministic runtime으로 이동시킬 수 있는가?

## Explainability

왜 이 operator와 데이터를 선택했는지 설명할 수 있는가?

## Testability

planning, SQL, calculation을 각각 독립적으로 검증할 수 있는가?

## Domain Portability

SCM에서 만든 core가 Sales, Finance, Manufacturing에서도 유지되는가?

## Storage Neutrality

Oracle, PostgreSQL, Snowflake, DuckDB 등의 차이가 logical architecture를 오염시키지 않는가?

## Extensibility

새로운 분석 방법을 추가할 때 core contract를 깨지 않는가?

## Cognitive Simplicity

새로운 developer가 architecture를 짧은 시간 안에 설명할 수 있는가?

---

# 14. 가장 중요한 Anti-Goal

다음을 피한다.

## 14.1 모든 것을 Semantic Layer에 넣기

```text
metric
dimension
ontology
business rule
analysis
diagnosis
workflow
operator
prompt
```

를 하나의 semantic model 안에 모두 넣지 않는다.

---

## 14.2 모든 업무 분석을 Domain Pack에 custom code로 구현하기

이렇게 되면:

```text
SCM engine
Sales engine
Finance engine
Manufacturing engine
```

이 병렬로 생긴다.

대신 가능한 한:

```text
shared canonical operators
+
domain-specific analytical patterns
```

을 추구한다.

---

## 14.3 모든 질문을 별도 Agent로 만들기

```text
Contribution Agent
Trend Agent
Mix Agent
Outlier Agent
```

를 처음부터 생성하지 않는다.

먼저 다음 구조를 검토한다.

```text
one planner
+
operator registry
+
conditional DAG
```

---

## 14.4 LLM이 계산식을 즉석에서 작성하도록 하기

가능한 계산은 registered operator로 수행한다.

LLM은 operator를 선택하고 parameter를 binding한다.

---

## 14.5 Architecture보다 Framework가 앞서게 만들기

LangGraph, TypeDB, Neo4j, PydanticAI 등의 선택이 logical model을 결정하게 하지 않는다.

먼저 contract와 IR을 정의한다.

그 후 구현 기술을 선택한다.

---

# 15. TypeDB / Graph / YAML / RDBMS의 위치도 재검토한다

logical architecture와 physical realization을 분리한다.

예:

```text
Logical

Semantic Contract
Analytical Contract
Planning Contract
```

와

```text
Physical

YAML
PostgreSQL
TypeDB
Neo4j
Python
DuckDB
```

를 구분한다.

TypeDB가 필요하다면 다음과 같은 physical realization일 수 있다.

```text
Semantic Contract
       ↓
Semantic Authority
       ↓
TypeDB
```

TypeDB 자체를 groot-cal architecture의 정의로 사용하지 않는다.

---

# 16. 현재 가장 단순한 Core Architecture Candidate

우선 다음 구조를 강한 후보로 검증한다.

```text
                  User Question
                        │
                        ▼
                Agent Harness
                        │
                 Intent / Plan
                        │
                        ▼
                 Analytical IR
                   Typed DAG
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
   Semantic Registry  Data Runtime  Operator Runtime
          │             │             │
          │           RDBMS           │
          └─────────────┼─────────────┘
                        │
                        ▼
                 Evidence Result
                        │
                        ▼
                     Answer
```

Domain Pack:

```text
        SCM       Sales      Finance
         │          │           │
         └──────────┼───────────┘
                    ▼
              Core Runtime
```

---

# 17. 더 압축된 Architecture Candidate

더 radical한 simplification도 검토한다.

groot-cal의 본질을 세 contract로 설명할 수 있는가?

## Semantic Contract

```text
What is it?
What is its grain?
What is its unit?
How does it aggregate?
What is it related to?
How is it mathematically related to other metrics?
```

## Analytical Contract

```text
What operation is this?
What input types are required?
What output type is returned?
What invariants must hold?
```

예:

```text
contribution_decomposition

inputs:
    metric
    baseline
    target
    dimension

invariant:
    sum(segment_delta) == total_delta
```

## Planning Contract

```text
User Intent
    ↓
Semantic Binding
    ↓
Operator Selection
    ↓
Data Requirements
    ↓
Execution DAG
```

가능하면 나머지 abstraction을 이 세 contract 아래로 환원해본다.

---

# 18. Long-Running Architecture Research Mode

이 작업에서는 한 번의 답을 낸 후 종료하지 않는다.

가능한 범위에서 반복 cycle을 수행한다.

한 cycle은 다음을 포함한다.

```text
1. inspect current architecture

2. formulate one architectural hypothesis

3. derive consequences

4. construct alternative hypothesis

5. create counterexample queries

6. test both hypotheses

7. identify duplication / exceptions

8. remove unnecessary concepts

9. implement the smallest useful experiment

10. run regression

11. record evidence

12. decide next hypothesis
```

한 iteration에서 지나치게 많은 코드를 변경하지 않는다.

Architecture understanding이 먼저다.

---

# 19. Architecture Journal을 유지한다

다음 파일을 생성하거나 이에 준하는 기록을 유지한다.

```text
research/
  architecture/
    hypotheses.md
    experiments.md
    counterexamples.md
    decisions.md
    metrics.md
```

각 hypothesis는 다음 형식으로 기록한다.

```markdown
## H-012

### Hypothesis

Diagnosis Layer는 필요하지 않고
diagnostic behavior는 analytical DAG로 표현할 수 있다.

### Supporting Evidence

...

### Counterexamples

...

### Implementation Experiment

...

### Result

supported / weakened / rejected / unresolved

### New Questions

...
```

중요:

실패한 가설을 삭제하지 않는다.

어떤 reasoning path가 실패했는지 역시 중요한 architecture knowledge다.

---

# 20. Architecture Decision Rule

새로운 abstraction을 추가하기 전에 반드시 다음 질문에 답한다.

```text
1. 어떤 실제 query가 현재 architecture에서 표현되지 않는가?

2. 기존 primitive composition으로 정말 표현할 수 없는가?

3. 이 문제가 domain-specific인가, domain-independent인가?

4. 이 abstraction을 추가하면 다른 query들도 단순해지는가?

5. 새로운 concept 하나가 몇 개의 exception을 제거하는가?

6. 이것을 제거하면 무엇이 깨지는가?
```

명확한 답이 없다면 abstraction 추가를 보류한다.

---

# 21. Simplification Rule

반대로 다음 조건을 만족하면 concept 제거를 적극 검토한다.

```text
A와 B가 항상 함께 사용된다.

B가 A에서 완전히 derivable하다.

B를 제거해도 query coverage가 떨어지지 않는다.

B가 새로운 exception을 만든다.

B가 특정 framework 때문에 존재한다.

B가 runtime behavior가 아니라 description에 불과하다.
```

---

# 22. Canonicality Test

어떤 구조가 canonical한지 평가할 때 다음 질문을 사용한다.

> SCM이라는 domain 이름을 지워도 이 abstraction이 필요한가?

YES라면 core candidate다.

NO라면 Domain Pack candidate다.

그리고:

> PostgreSQL이라는 제품 이름을 지워도 필요한가?

YES라면 logical architecture candidate다.

NO라면 implementation detail일 가능성이 높다.

그리고:

> LLM이 없어도 이 computation의 의미가 존재하는가?

YES라면 analytical/semantic contract에 둘 가능성이 높다.

---

# 23. 목표 상태

최종적으로 완벽한 architecture를 증명하는 것이 목표가 아니다.

다음 상태에 가까워지는 것을 목표로 한다.

```text
query coverage       ↑
operator reuse       ↑
planning stability   ↑
determinism          ↑

concept count        ↓
special cases        ↓
domain duplication   ↓
LLM free-form logic  ↓
```

그러나 이 지표를 기계적으로 최적화하지 않는다.

가장 중요한 최종 판단은:

> **이 architecture가 groot-cal이 무엇인지 더 명확하게 설명하게 만드는가?**

이다.

---

# 24. 최종적으로 발견하고 싶은 최소 문법

연구 과정에서 다음 형태의 최소 analytical grammar를 찾아라.

초기 가설:

```text
Question

→ Intent

→ Metric
→ Entity / Dimension
→ Time Scope
→ Comparison

→ Operator
→ Breakdown
→ Filter
→ Parameters

→ Conditional Operators

→ Data Requirement

→ Execution DAG

→ Evidence
```

그러나 이 grammar 또한 적극적으로 축소하거나 수정한다.

---

# 25. 작업 우선순위

다음 순서로 진행한다.

## Phase 1 — Observe

현재 groot-cal repository를 읽고 기존 abstraction을 목록화한다.

코드를 바로 변경하지 않는다.

다음을 찾아낸다.

```text
semantic concepts
operator concepts
planner concepts
domain concepts
execution concepts
special cases
```

---

## Phase 2 — Build Query Corpus

최소 30개의 대표 분석 질의를 만든다.

가능하면 이후 50~100개로 확장한다.

범주는 최소 다음을 포함한다.

```text
aggregation
comparison
ranking
contribution
mix/rate
trend
acceleration
change point
outlier
concentration
multi-dimensional driver
counterfactual
```

---

## Phase 3 — Reverse Engineer Minimal IR

각 query를 실행하기 위해 필요한 semantic information과 operator를 역으로 추출한다.

그 교집합으로 Analytical IR grammar 후보를 만든다.

---

## Phase 4 — Generate Alternatives

최소 세 가지 architecture를 비교한다.

예:

```text
A. Semantic-heavy

B. Operator-centric

C. IR-centric + thin semantic layer
```

가능하면 현재 구조도 Candidate 0으로 포함한다.

---

## Phase 5 — Red Team

각 architecture를 깨뜨릴 query를 생성한다.

특히 다음을 찾는다.

```text
unexpected composition
multi-metric query
multi-level decomposition
non-additive metric
weighted metric
derived metric
time comparison
nested diagnosis
```

---

## Phase 6 — Simplify

coverage를 유지하면서 concept를 제거한다.

---

## Phase 7 — Minimal Implementation

가장 유망한 candidate의 최소 vertical slice를 구현한다.

```text
Question
→ Analytical IR
→ SQL
→ Operator
→ Validation
→ Answer
```

---

## Phase 8 — Regression

전체 corpus를 다시 실행한다.

---

## Phase 9 — Repeat

새로운 counterexample을 생성하고 cycle을 반복한다.

---

# 26. 매 Iteration이 남겨야 하는 결과

각 iteration 종료 시 최소 다음을 기록한다.

```markdown
## Iteration N

### Hypothesis

...

### Architecture Change

...

### Why

...

### Query Coverage

...

### New Counterexamples

...

### Concepts Added

...

### Concepts Removed

...

### Special Cases Added/Removed

...

### Regression

...

### Qualitative Assessment

...

### Next Hypothesis

...
```

---

# 27. 중요한 작업 태도

이 작업에서는 "코드를 많이 만든 것"을 progress로 간주하지 않는다.

진전은 다음과 같은 경우다.

```text
두 abstraction을 하나로 통합했다.

domain-specific logic을 canonical operator로 환원했다.

LLM 판단을 deterministic contract로 변경했다.

새로운 반례를 발견했다.

잘못된 architecture hypothesis를 폐기했다.

IR grammar를 더 작게 만들었다.

동일 grammar가 더 많은 query를 표현하게 되었다.
```

특히 다음 결과는 성공으로 간주한다.

> 많은 시간을 검토한 결과 현재 abstraction 하나가 필요 없다는 것을 증명했다.

코드가 줄어드는 것이 architecture research의 중요한 성과가 될 수 있다.

---

# 28. Codex에 대한 핵심 지시

이 연구에서는 빠르게 결론을 내리지 마라.

첫 architecture candidate를 정답으로 취급하지 마라.

현재 repository의 구조를 정당화하는 방향으로 reasoning하지 마라.

반드시 alternative를 만든다.

반드시 counterexample을 찾는다.

반드시 simplification을 시도한다.

새로운 abstraction을 추가하는 것보다 기존 abstraction을 제거하는 것을 먼저 검토한다.

LLM prompt engineering으로 해결하기 전에 typed contract와 deterministic computation으로 해결할 수 있는지 검토한다.

특정 framework에 architecture를 맞추지 않는다.

실제 query corpus를 architecture의 test suite로 사용한다.

---

# 29. North Star

groot-cal의 architecture는 궁극적으로 다음 문장이 자연스럽게 성립해야 한다.

> **groot-cal은 사용자의 분석 질문을 typed analytical plan으로 compile하고, semantic contract를 이용해 필요한 데이터를 찾으며, canonical mathematical operators를 deterministic하게 실행하여 evidence-based answer를 만드는 시스템이다.**

그리고 Domain Pack은:

> **특정 업무 영역의 언어와 분석 관행을 core semantic objects와 canonical operators의 조합으로 번역한다.**

이 두 문장을 설명하기 위해 계속 새로운 subsystem이 필요해진다면 architecture를 다시 의심한다.

---

# 30. Research Question

계속해서 이 질문으로 돌아온다.

> **우리가 가진 다양한 BI·SCM 분석 질문을 표현하기 위해 정말 필요한 최소한의 semantic concepts, analytical primitives, planning grammar는 무엇인가?**

그리고 매 iteration에서 다시 묻는다.

> **더 적은 개념으로 같은 것을 할 수 있는가?**