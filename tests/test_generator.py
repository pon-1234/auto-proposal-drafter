from pathlib import Path

from auto_proposal_drafter.generator import ProposalGenerator
from auto_proposal_drafter.models.opportunity import Opportunity


def load_fixture(name: str) -> Opportunity:
    fixture_path = Path("data/opportunities") / f"{name}.json"
    return Opportunity.model_validate_json(fixture_path.read_text(encoding="utf-8"))


def test_generator_produces_expected_shapes():
    opportunity = load_fixture("OPP-2025-001")
    generator = ProposalGenerator()
    bundle = generator.generate(opportunity)

    assert bundle.structure.site_map, "site_map should not be empty"
    assert bundle.wire.pages, "wire pages should not be empty"
    assert bundle.estimate.line_items, "estimate must include line items"
    assert "提案サマリ" in bundle.summary_markdown

    # Ensure coefficients reflect opportunity conditions
    coeff_names = {coeff.name for coeff in bundle.estimate.coefficients}
    assert "短納期" in coeff_names
    assert "素材未提供（コピー）" in coeff_names
