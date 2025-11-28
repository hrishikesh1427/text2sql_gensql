import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class TemplateContext:
    question: str
    tenant_id: Optional[str]
    from_date: Optional[str]
    to_date: Optional[str]


@dataclass
class QueryTemplate:
    name: str
    matcher: Callable[[str], bool]
    renderer: Callable[[TemplateContext], str]


def _normalize(question: str) -> str:
    return question.lower()


def _contains_all(keywords: list[str]) -> Callable[[str], bool]:
    def _match(question: str) -> bool:
        q = _normalize(question)
        return all(keyword in q for keyword in keywords)

    return _match


def _extract_dates(question: str) -> tuple[Optional[str], Optional[str]]:
    date_pattern = re.compile(r"'(\d{4}-\d{2}-\d{2})'")
    matches = date_pattern.findall(question)
    if len(matches) >= 2:
        return matches[0], matches[1]

    bare_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    matches = bare_pattern.findall(question)
    if len(matches) >= 2:
        return matches[0], matches[1]
    return None, None


def _extract_tenant(question: str) -> Optional[str]:
    match = re.search(r"tenant\s*(?:id|=)?\s*(\d+)", question.lower())
    if match:
        return match.group(1)
    return None


def _resolve_tenant(ctx: TemplateContext) -> str:
    return ctx.tenant_id or ":tenant_id"


def _resolve_from_date(ctx: TemplateContext) -> str:
    return f"'{ctx.from_date}'" if ctx.from_date else ":from_date"


def _resolve_to_date(ctx: TemplateContext) -> str:
    return f"'{ctx.to_date}'" if ctx.to_date else ":to_date"


def _common_where(ctx: TemplateContext) -> str:
    tenant = _resolve_tenant(ctx)
    start = _resolve_from_date(ctx)
    end = _resolve_to_date(ctx)
    return f"tenant_id = {tenant} and date between {start} and {end}"


def _render_basic_boolean(ctx: TemplateContext, column: str, value: bool) -> str:
    where = _common_where(ctx)
    bool_val = "true" if value else "false"
    return (
        f"select count(*) from chatbot.call_data where {where} and {column}={bool_val};"
    )


def _render_basic_threshold(ctx: TemplateContext, column: str, operator: str, value) -> str:
    where = _common_where(ctx)
    literal = f"'{value}'" if isinstance(value, str) else str(value)
    return f"select count(*) from chatbot.call_data where {where} and {column} {operator} {literal};"


def _render_avg(ctx: TemplateContext, column: str) -> str:
    where = _common_where(ctx)
    return f"select avg({column}) from chatbot.call_data where {where};"


def _fatal_calls(ctx: TemplateContext) -> str:
    return _render_basic_boolean(ctx, "is_fatal_call", True)


def _disconnected_calls(ctx: TemplateContext) -> str:
    # Requirement explicitly expects is_disconnected=false
    return _render_basic_boolean(ctx, "is_disconnected", False)


def _ztp_calls(ctx: TemplateContext) -> str:
    return _render_basic_boolean(ctx, "is_ztp", True)


def _avg_call_score(ctx: TemplateContext) -> str:
    return _render_avg(ctx, "call_score")


def _audit_sheet_counts(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "select audit_sheet, count(*) as call_count "
        f"from chatbot.call_data where {where} and is_active = true "
        "group by audit_sheet order by call_count desc;"
    )


def _total_duration(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "select concat(floor(sum(duration) / 3600), ' hours ', "
        "floor((sum(duration) % 3600) / 60), ' minutes') as total_duration "
        f"from chatbot.call_data where {where};"
    )


def _customer_emotion_positive(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "select count(*) from chatbot.call_data "
        f"where {where} and customer_emotion='positive';"
    )


def _call_score_gt_85(ctx: TemplateContext) -> str:
    return _render_basic_threshold(ctx, "call_score", ">", 85)


def _call_intent_buy(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "select count(*) from chatbot.call_data "
        f"where {where} and call_intent='Intent to Buy';"
    )


def _mandatory_information_shared(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "select count(*) as call_count\n"
        "from chatbot.call_data\n"
        f"where {where}\n"
        "  and exists (\n"
        "        select 1\n"
        "        from jsonb_array_elements(scoring_parameters) as sp\n"
        "        where sp->>'name' = 'Mandatory Information shared'\n"
        "          and sp->>'status' = 'Yes'\n"
        "    );"
    )


def _agent_wise_count(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "SELECT \n"
        "    agent_name,\n"
        "    COUNT(*) AS call_count\n"
        "FROM chatbot.call_data\n"
        f"WHERE {where}\n"
        "GROUP BY agent_name\n"
        "ORDER BY call_count DESC;"
    )


def _disposition_wise_count(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "SELECT \n"
        "    disposition, \n"
        "    COUNT(*) \n"
        "FROM chatbot.call_data\n"
        f"WHERE {where}\n"
        "GROUP BY disposition\n"
        "ORDER BY COUNT(*) DESC;"
    )


def _avg_handling_time(ctx: TemplateContext) -> str:
    where = _common_where(ctx)
    return (
        "SELECT \n"
        "    AVG(handling_time) AS avg_handling_time\n"
        "FROM chatbot.call_data\n"
        f"WHERE {where};"
    )


def _avg_agent_skill_score(ctx: TemplateContext) -> str:
    tenant = _resolve_tenant(ctx)
    start = _resolve_from_date(ctx)
    end = _resolve_to_date(ctx)
    return (
        "SELECT \n"
        "    AVG(agent_skill_score)\n"
        "FROM chatbot.call_data\n"
        f"WHERE tenant_id = {tenant}\n"
        f"  AND date BETWEEN {start} AND {end};"
    )


def _propensity_score_gte_three(ctx: TemplateContext) -> str:
    tenant = _resolve_tenant(ctx)
    start = _resolve_from_date(ctx)
    end = _resolve_to_date(ctx)
    return (
        "SELECT \n"
        "    COUNT(*)\n"
        "FROM chatbot.call_data\n"
        f"WHERE tenant_id = {tenant}\n"
        f"  AND date BETWEEN {start} AND {end}\n"
        "  AND propensity_score >= 3;"
    )


TEMPLATES: list[QueryTemplate] = [
    QueryTemplate("fatal_calls", _contains_all(["fatal", "call", "count"]), _fatal_calls),
    QueryTemplate(
        "disconnected_calls", _contains_all(["disconnected", "count"]), _disconnected_calls
    ),
    QueryTemplate("ztp_calls", _contains_all(["ztp", "count"]), _ztp_calls),
    QueryTemplate("avg_call_score", _contains_all(["avg", "call", "score"]), _avg_call_score),
    QueryTemplate("audit_sheet", _contains_all(["audit", "sheet"]), _audit_sheet_counts),
    QueryTemplate("total_duration", _contains_all(["duration"]), _total_duration),
    QueryTemplate(
        "customer_emotion_positive",
        _contains_all(["customer", "emotion", "positive"]),
        _customer_emotion_positive,
    ),
    QueryTemplate("call_score_gt_85", _contains_all(["call", "score", "85"]), _call_score_gt_85),
    QueryTemplate("call_intent_buy", _contains_all(["intent", "buy"]), _call_intent_buy),
    QueryTemplate(
        "mandatory_information_shared",
        _contains_all(["mandatory", "information", "shared"]),
        _mandatory_information_shared,
    ),
    QueryTemplate("agent_wise", _contains_all(["agent", "call", "count"]), _agent_wise_count),
    QueryTemplate(
        "disposition_wise", _contains_all(["disposition", "call", "count"]), _disposition_wise_count
    ),
    QueryTemplate("avg_handling_time", _contains_all(["avg", "handling", "time"]), _avg_handling_time),
    QueryTemplate(
        "avg_agent_skill_score",
        _contains_all(["agent", "skill", "score"]),
        _avg_agent_skill_score,
    ),
    QueryTemplate(
        "propensity_score_gte_three",
        _contains_all(["propensity", "score"]),
        _propensity_score_gte_three,
    ),
]


def _build_context(question: str) -> TemplateContext:
    tenant_id = _extract_tenant(question)
    from_date, to_date = _extract_dates(question)
    return TemplateContext(question=question, tenant_id=tenant_id, from_date=from_date, to_date=to_date)


def match_template(question: str) -> Optional[str]:
    ctx = _build_context(question)
    for template in TEMPLATES:
        if template.matcher(question):
            return template.renderer(ctx)
    return None

