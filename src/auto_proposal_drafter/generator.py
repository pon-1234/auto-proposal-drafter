from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from pydantic import BaseModel

from .dictionaries import (
    DEFAULT_ASSUMPTIONS,
    DEFAULT_COEFFICIENT_RULES,
    DEFAULT_PAGE_PRESETS,
    DEFAULT_RATES,
    DEFAULT_SECTIONS,
    GenerationContext,
    default_generation_context,
)
from .models.estimate import EstimateDraft, EstimateLineItem
from .models.opportunity import Opportunity
from .models.structure import SectionSpec, SitePageSpec, StructureDraft
from .models.wire import WireDraft, WirePage, WireProject, WireSection


@dataclass
class DraftBundle:
    structure: StructureDraft
    wire: WireDraft
    estimate: EstimateDraft
    summary_markdown: str

    def model_dump(self) -> dict[str, object]:
        return {
            "structure": self.structure.model_dump(),
            "wire": self.wire.model_dump(),
            "estimate": {
                **self.estimate.model_dump(),
                "line_items": [
                    {**item.model_dump(), "cost": item.cost}
                    for item in self.estimate.line_items
                ],
            },
            "summary": self.summary_markdown,
        }


class ProposalGenerator:
    def __init__(
        self,
        *,
        page_presets=DEFAULT_PAGE_PRESETS,
        sections=DEFAULT_SECTIONS,
        rates: dict[str, float] | None = None,
        assumptions: Sequence[str] = DEFAULT_ASSUMPTIONS,
        coefficient_rules=DEFAULT_COEFFICIENT_RULES,
        context_factory=default_generation_context,
    ) -> None:
        self._page_presets = page_presets
        self._sections = sections
        self._rates = dict(rates or DEFAULT_RATES)
        self._assumptions = tuple(assumptions)
        self._coefficient_rules = tuple(coefficient_rules)
        self._context_factory = context_factory

    def generate(self, opportunity: Opportunity) -> DraftBundle:
        context = self._context_factory()
        site_type = self._infer_site_type(opportunity)
        structure = self._build_structure(opportunity, site_type)
        context.structure = structure
        wire = self._build_wire(opportunity, structure)
        estimate = self._build_estimate(opportunity, structure, context)
        summary = self._build_summary(opportunity, structure, estimate)
        return DraftBundle(structure=structure, wire=wire, estimate=estimate, summary_markdown=summary)

    def _infer_site_type(self, opportunity: Opportunity) -> str:
        title = opportunity.title.lower()
        goal = opportunity.goal.lower()
        if "lp" in title or "ランディング" in opportunity.title:
            return "LP"
        if "リード" in goal or "lead" in goal:
            return "LP"
        if "採用" in goal:
            return "Corporate"
        return "LP"

    def _build_structure(self, opportunity: Opportunity, site_type: str) -> StructureDraft:
        pages = list(self._page_presets.get(site_type, ()))
        if not pages:
            pages = list(self._page_presets["LP"])
        resolved_pages: list[SitePageSpec] = []
        for preset in pages:
            sections: list[SectionSpec] = []
            for section in preset.sections:
                definition = self._sections.get(f"{section.kind}/{section.variant}")
                if not definition:
                    sections.append(section)
                    continue
                copy = list(self._build_section_copy(opportunity, definition))
                sections.append(
                    SectionSpec(kind=section.kind, variant=section.variant, copy=copy)
                )
            resolved_pages.append(
                SitePageSpec(
                    page_id=preset.page_id,
                    type=preset.type,
                    goal=preset.goal,
                    sections=sections,
                    notes=preset.notes,
                )
            )

        uncertains = self._derive_uncertains(opportunity)
        risks = self._derive_risks(opportunity)
        flows = self._derive_flows(resolved_pages)
        return StructureDraft(site_map=resolved_pages, flows=flows, uncertains=uncertains, risks=risks)

    def _build_wire(self, opportunity: Opportunity, structure: StructureDraft) -> WireDraft:
        pages: list[WirePage] = []
        for page in structure.site_map:
            sections: list[WireSection] = []
            for section in page.sections:
                definition = self._sections.get(f"{section.kind}/{section.variant}")
                placeholders = None
                if definition:
                    placeholders = {
                        key: value.format(
                            company=opportunity.company,
                            persona_goal=(opportunity.goal or "成果"),
                            goal_phrase=self._goal_phrase(opportunity),
                        )
                        for key, value in definition.placeholders.items()
                    }
                sections.append(
                    WireSection(kind=section.kind, variant=section.variant, placeholders=placeholders)
                )
            pages.append(WirePage(page_id=page.page_id, sections=sections, notes=page.notes))
        project = WireProject(id=opportunity.id, title=f"{opportunity.company} {opportunity.title}")
        return WireDraft(project=project, pages=pages)

    def _build_estimate(
        self,
        opportunity: Opportunity,
        structure: StructureDraft,
        context: GenerationContext,
    ) -> EstimateDraft:
        line_items: list[EstimateLineItem] = []
        ia_hours = max(4.0, 1.5 * len(structure.site_map[0].sections) if structure.site_map else 4.0)
        line_items.append(
            EstimateLineItem(
                item="IA（サイトマップ/要件整理）",
                qty=1,
                hours=round(ia_hours, 1),
                rate=self._rates["IA"],
                role="IA",
            )
        )
        for page in structure.site_map:
            for section in page.sections:
                definition = self._sections.get(f"{section.kind}/{section.variant}")
                if not definition:
                    continue
                hours = definition.design_hours
                item_label = f"{page.page_id.title()}: {definition.label}"
                line_items.append(
                    EstimateLineItem(
                        item=item_label,
                        qty=1,
                        hours=round(hours, 1),
                        rate=self._rates["Design"],
                        role="Design",
                    )
                )
        pm_hours = max(4.0, len(line_items) * 0.6)
        line_items.append(
            EstimateLineItem(
                item="PM（進行管理・定例）",
                qty=1,
                hours=round(pm_hours, 1),
                rate=self._rates["PM"],
                role="PM",
            )
        )

        coefficients = [
            coeff
            for rule in self._coefficient_rules
            if (coeff := rule.evaluate(opportunity, context)) is not None
        ]

        assumptions = list(self._assumptions)
        if opportunity.assets.photo is False:
            assumptions.append("写真素材は別途撮影/選定が必要")
        if opportunity.assets.copy is False:
            assumptions.append("コピーライティングは共同で実施")

        return EstimateDraft(line_items=line_items, coefficients=coefficients, assumptions=assumptions)

    def _build_summary(
        self,
        opportunity: Opportunity,
        structure: StructureDraft,
        estimate: EstimateDraft,
    ) -> str:
        total_base = sum(item.cost for item in estimate.line_items)
        total = total_base
        coeff_summary: list[str] = []
        for coeff in estimate.coefficients:
            total *= coeff.multiplier
            coeff_summary.append(f"- {coeff.name} ×{coeff.multiplier:.2f} ({coeff.reason})")
        sections = sum(len(page.sections) for page in structure.site_map)
        uncertains = "\n".join(f"- {item}" for item in structure.uncertains) or "- なし"
        risks = "\n".join(f"- {item}" for item in structure.risks) or "- なし"

        summary_lines = [
            f"## 提案サマリ",
            f"- 案件ID: {opportunity.id}",
            f"- 目的: {opportunity.goal}",
            f"- セクション数: {sections}",
            f"- 基本見積: ¥{int(total_base):,}",
            f"- 係数適用後見積: ¥{int(total):,}",
            "",
            "## 係数",
            "\n".join(coeff_summary) if coeff_summary else "- なし",
            "",
            "## 不確定事項",
            uncertains,
            "",
            "## リスク",
            risks,
        ]
        return "\n".join(summary_lines)

    def _build_section_copy(self, opportunity: Opportunity, definition) -> Iterable[str]:
        goal_phrase = self._goal_phrase(opportunity)
        persona = opportunity.persona or "想定顧客"
        goal = opportunity.goal or "成果"
        if definition.kind == "Hero":
            return (
                f"{opportunity.company}が{goal_phrase}を支援",
                f"{persona}の課題を{goal}視点で解決",
                "まずは資料請求・お問い合わせで詳細をご確認ください",
            )
        if definition.kind == "SocialProof":
            refs = ", ".join(opportunity.references[:3]) if opportunity.references else "業界各社"
            return (
                f"{refs}などで導入実績",
                "安心してご相談いただけます",
            )
        if definition.kind == "Features":
            musts = list(opportunity.must_have[:3]) or ["高いCVR","直感的な導線","運用のしやすさ"]
            return tuple(f"特徴{i+1}: {must}" for i, must in enumerate(musts))
        if definition.kind == "CaseStudies":
            return (
                "対象業界での成功事例を掲載",
                "導入背景と成果を数値で提示",
            )
        if definition.kind == "Offer":
            budget = opportunity.budget_band or "要相談"
            return (
                "スピード重視の標準パッケージ",
                f"概算費用帯: {budget}",
            )
        if definition.kind == "FAQ":
            return (
                "導入スケジュールや体制のFAQを整備",
                "セキュリティ・保守に関する質問も想定",
            )
        if definition.kind == "CTA":
            return (
                "お気軽に資料請求/打ち合わせをご依頼ください",
            )
        if definition.kind == "Form":
            return (
                "氏名・会社名・連絡先・相談内容を想定",
                "6項目以内で離脱を抑制",
            )
        if definition.kind == "About":
            return (
                f"{opportunity.company}の事業概要とミッション",
                "沿革・主要メンバーの紹介",
            )
        if definition.kind == "Services":
            return (
                "提供サービスカテゴリを分かりやすく整理",
                "オプション対応範囲も記載",
            )
        return definition.copy_hints

    def _goal_phrase(self, opportunity: Opportunity) -> str:
        goal = opportunity.goal or "成果"
        if "リード" in goal:
            return "B2B向けのリード獲得"
        if "採用" in goal:
            return "採用強化"
        if "ブランド" in goal:
            return "ブランド想起向上"
        return goal

    def _derive_uncertains(self, opportunity: Opportunity) -> list[str]:
        items: list[str] = []
        if opportunity.deadline is None:
            items.append("納期未確定 → ヒアリング要")
        if opportunity.assets.copy is False:
            items.append("コピー提供タイミングの確認")
        if opportunity.assets.photo is False:
            items.append("写真素材の調達方法")
        if not opportunity.must_have:
            items.append("必須機能の確定")
        return items

    def _derive_risks(self, opportunity: Opportunity) -> list[str]:
        risks: list[str] = []
        if opportunity.assets.copy is False:
            risks.append("コピー未提供に伴う制作遅延")
        if opportunity.deadline and (opportunity.deadline - date.today()).days < 45:
            risks.append("短納期でのスケジュール逼迫")
        if "ブランドカラー" in "".join(opportunity.constraints):
            risks.append("ブランドガイドライン厳守によるリワーク")
        return risks

    def _derive_flows(self, pages: Sequence[SitePageSpec]) -> list[str]:
        flows: list[str] = []
        for page in pages:
            cta_kinds = [section.kind for section in page.sections if section.kind in {"CTA", "Form"}]
            if "Form" in cta_kinds:
                flows.append(f"{page.page_id.title()}→Form")
            if "CTA" in cta_kinds:
                flows.append(f"{page.page_id.title()}→CTA")
        return flows or ["Top→Form"]


__all__ = ["ProposalGenerator", "DraftBundle"]
