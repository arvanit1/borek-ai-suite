"""BT-34 integration seams. No unapproved web or audio provider is configured."""

from services.framework.stage1_research import CompanyResearchProvider


def get_company_research_provider() -> CompanyResearchProvider | None:
    """Override through app dependency wiring once an approved adapter exists.

    The adapter must verify company identity, return cited evidence, and enforce
    provider egress rules. Never treat an LLM's general knowledge as research.
    """
    return None
