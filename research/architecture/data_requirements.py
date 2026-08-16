"""E-006 prototype: backend-neutral data requirements and SQLite lowering."""
from dataclasses import dataclass


class RequirementError(ValueError):
    pass


@dataclass(frozen=True)
class AggregateExpr:
    kind: str
    value_field: str | None = None
    numerator_field: str | None = None
    denominator_field: str | None = None


@dataclass(frozen=True)
class Relationship:
    bridge: str
    source_key: str
    bridge_key: str
    dimension_field: str
    cardinality: str
    allocation_rule: str | None = None


@dataclass(frozen=True)
class DataRequirement:
    source: str
    source_grain: tuple
    aggregate: AggregateExpr
    group_by: tuple
    relationship: Relationship | None = None
    filters: tuple = ()


def validate_requirement(requirement):
    if not requirement.source_grain:
        raise RequirementError("source grain is required")
    if requirement.aggregate.kind not in {"sum", "ratio_of_sums"}:
        raise RequirementError("unsupported aggregate expression")
    rel = requirement.relationship
    if rel and rel.cardinality == "many_to_many" \
            and rel.allocation_rule not in {"equal_split", "duplicate_explicit"}:
        raise RequirementError("many_to_many grouping requires explicit allocation rule")
    if rel and rel.allocation_rule == "duplicate_explicit":
        raise RequirementError("duplicate_explicit cannot produce a reconciled additive result")
    return requirement


def lower_sqlite(requirement):
    """Lower one validated logical requirement; SQL is a backend artifact."""
    validate_requirement(requirement)
    aggregate = requirement.aggregate
    rel = requirement.relationship

    where = ""
    params = []
    if requirement.filters:
        clauses = []
        for field, value in requirement.filters:
            clauses.append(f"s.{field} = ?")
            params.append(value)
        where = " WHERE " + " AND ".join(clauses)

    if rel is None:
        from_sql = f"{requirement.source} s"
        weight = "1.0"
        dimension = None
    elif rel.cardinality == "many_to_many":
        counts = (f"(SELECT {rel.bridge_key}, COUNT(*) AS allocation_n "
                  f"FROM {rel.bridge} GROUP BY {rel.bridge_key}) alloc")
        from_sql = (f"{requirement.source} s "
                    f"JOIN {rel.bridge} b ON s.{rel.source_key} = b.{rel.bridge_key} "
                    f"JOIN {counts} ON s.{rel.source_key} = alloc.{rel.bridge_key}")
        weight = "(1.0 / alloc.allocation_n)"
        dimension = f"b.{rel.dimension_field}"
    else:
        from_sql = (f"{requirement.source} s JOIN {rel.bridge} b "
                    f"ON s.{rel.source_key} = b.{rel.bridge_key}")
        weight = "1.0"
        dimension = f"b.{rel.dimension_field}"

    if aggregate.kind == "sum":
        expression = f"SUM(s.{aggregate.value_field} * {weight})"
        component_sql = expression + " AS value"
    else:
        numerator = f"SUM(s.{aggregate.numerator_field} * {weight})"
        denominator = f"SUM(s.{aggregate.denominator_field} * {weight})"
        component_sql = (f"{numerator} AS numerator, {denominator} AS denominator, "
                         f"{numerator} / NULLIF({denominator}, 0) AS value")

    select_parts = []
    group_sql = ""
    if requirement.group_by:
        if rel is None or requirement.group_by != (rel.dimension_field,):
            raise RequirementError("prototype supports the declared relationship dimension only")
        select_parts.append(f"{dimension} AS {rel.dimension_field}")
        group_sql = f" GROUP BY {dimension}"
    select_parts.append(component_sql)
    sql = f"SELECT {', '.join(select_parts)} FROM {from_sql}{where}{group_sql}"
    return {"sql": sql, "params": params,
            "logical_requirement": requirement,
            "backend": "sqlite"}

