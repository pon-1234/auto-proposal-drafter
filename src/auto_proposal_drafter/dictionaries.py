from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable, Mapping, Sequence

from .models.estimate import EstimateCoefficient, EstimateDraft, EstimateLineItem
from .models.opportunity import Opportunity
from .models.structure import SectionSpec, SitePageSpec, StructureDraft
from .models.wire import WireDraft, WirePage, WireProject, WireSection


@dataclass(frozen=True)
class SectionDefinition:
    key: str
    label: str
    kind: str
    variant: str
    design_hours: float
    copy_hints: Sequence[str]
    placeholders: Mapping[str, str]


DEFAULT_SECTIONS: Mapping[str, SectionDefinition] = {
    "Hero/Center": SectionDefinition(
        key="Hero/Center",
        label="Hero",
        kind="Hero",
        variant="Center",
        design_hours=1.5,
        copy_hints=(
            "顧客課題と解決価値を1行で",
            "主要ベネフィットを箇条書き",
            "CTAリンクの誘導文",
        ),
        placeholders={
            "headline": "{company}が{persona_goal}を加速",
            "sub": "{goal_phrase}"
        },
    ),
    "SocialProof/LogosStrip": SectionDefinition(
        key="SocialProof/LogosStrip",
        label="Social Proof",
        kind="SocialProof",
        variant="LogosStrip",
        design_hours=1.0,
        copy_hints=("代表的な導入企業を3〜5社紹介",),
        placeholders={"headline": "導入企業", "logos": "A社 / B社 / C社"},
    ),
    "Features/3ColsIcons": SectionDefinition(
        key="Features/3ColsIcons",
        label="Features",
        kind="Features",
        variant="3ColsIcons",
        design_hours=1.4,
        copy_hints=("ベネフィット3つを簡潔に",),
        placeholders={
            "col1": "特徴1",
            "col2": "特徴2",
            "col3": "特徴3",
        },
    ),
    "CaseStudies/Cards3": SectionDefinition(
        key="CaseStudies/Cards3",
        label="Case Studies",
        kind="CaseStudies",
        variant="Cards3",
        design_hours=1.3,
        copy_hints=("代表的な成功事例を要約",),
        placeholders={"title": "導入事例"},
    ),
    "Offer/PricingSimple": SectionDefinition(
        key="Offer/PricingSimple",
        label="Offer",
        kind="Offer",
        variant="PricingSimple",
        design_hours=1.2,
        copy_hints=("基本プランと差別化ポイント",),
        placeholders={"plan": "スタンダードプラン"},
    ),
    "FAQ/Accordion": SectionDefinition(
        key="FAQ/Accordion",
        label="FAQ",
        kind="FAQ",
        variant="Accordion",
        design_hours=1.0,
        copy_hints=("よくある質問と回答を3〜5件",),
        placeholders={"q1": "質問1", "a1": "回答1"},
    ),
    "CTA/PrimaryBottom": SectionDefinition(
        key="CTA/PrimaryBottom",
        label="CTA",
        kind="CTA",
        variant="PrimaryBottom",
        design_hours=0.6,
        copy_hints=("フォーム送信を促す一文",),
        placeholders={"cta": "資料請求はこちら"},
    ),
    "Form/ContactBasic": SectionDefinition(
        key="Form/ContactBasic",
        label="Form",
        kind="Form",
        variant="ContactBasic",
        design_hours=1.2,
        copy_hints=("入力項目6つ程度に抑える",),
        placeholders={"submit": "送信"},
    ),
    "About/Split": SectionDefinition(
        key="About/Split",
        label="About",
        kind="About",
        variant="Split",
        design_hours=1.1,
        copy_hints=("企業概要と差別化を簡潔に",),
        placeholders={"headline": "会社概要"},
    ),
    "Services/Grid": SectionDefinition(
        key="Services/Grid",
        label="Services",
        kind="Services",
        variant="Grid",
        design_hours=1.3,
        copy_hints=("提供サービスカテゴリを整理",),
        placeholders={"headline": "提供サービス"},
    ),
}


DEFAULT_PAGE_PRESETS: Mapping[str, Sequence[SitePageSpec]] = {
    "LP": (
        SitePageSpec(
            page_id="top",
            type="LP",
            goal="リード獲得",
            sections=[
                SectionSpec(kind="Hero", variant="Center"),
                SectionSpec(kind="SocialProof", variant="LogosStrip"),
                SectionSpec(kind="Features", variant="3ColsIcons"),
                SectionSpec(kind="CaseStudies", variant="Cards3"),
                SectionSpec(kind="Offer", variant="PricingSimple"),
                SectionSpec(kind="FAQ", variant="Accordion"),
                SectionSpec(kind="CTA", variant="PrimaryBottom"),
                SectionSpec(kind="Form", variant="ContactBasic"),
            ],
        ),
    ),
    "Corporate": (
        SitePageSpec(
            page_id="home",
            type="Corporate",
            goal="企業理解",
            sections=[
                SectionSpec(kind="Hero", variant="Center"),
                SectionSpec(kind="About", variant="Split"),
                SectionSpec(kind="Services", variant="Grid"),
                SectionSpec(kind="CaseStudies", variant="Cards3"),
                SectionSpec(kind="FAQ", variant="Accordion"),
                SectionSpec(kind="CTA", variant="PrimaryBottom"),
                SectionSpec(kind="Form", variant="ContactBasic"),
            ],
        ),
    ),
}


DEFAULT_RATES: Mapping[str, float] = {
    "IA": 12000.0,
    "Design": 12000.0,
    "PM": 12000.0,
}


DEFAULT_ASSUMPTIONS: Sequence[str] = (
    "写真素材は支給を想定",
    "CMS構築は別途見積対象",
    "ファーストビュー文言はクライアント確定を前提",
)


@dataclass
class CoefficientRule:
    name: str
    multiplier: float
    reason: str
    predicate: Callable[[Opportunity, "GenerationContext"], bool]

    def evaluate(self, opportunity: Opportunity, context: "GenerationContext") -> EstimateCoefficient | None:
        if self.predicate(opportunity, context):
            return EstimateCoefficient(name=self.name, multiplier=self.multiplier, reason=self.reason)
        return None


@dataclass
class GenerationContext:
    today: date
    structure: StructureDraft | None = None


DEFAULT_COEFFICIENT_RULES: Sequence[CoefficientRule] = (
    CoefficientRule(
        name="短納期",
        multiplier=1.15,
        reason="納期が45日未満",
        predicate=lambda opp, ctx: bool(opp.deadline and (opp.deadline - ctx.today).days < 45),
    ),
    CoefficientRule(
        name="素材未提供（コピー）",
        multiplier=1.2,
        reason="コピー素材が未支給",
        predicate=lambda opp, ctx: opp.assets.copy is False,
    ),
    CoefficientRule(
        name="CMS要件含む",
        multiplier=1.1,
        reason="メモにCMS化要望",
        predicate=lambda opp, ctx: bool(opp.notes and "CMS" in opp.notes.upper()),
    ),
)


def default_generation_context() -> GenerationContext:
    return GenerationContext(today=date.today())


__all__ = [
    "DEFAULT_SECTIONS",
    "DEFAULT_PAGE_PRESETS",
    "DEFAULT_RATES",
    "DEFAULT_COEFFICIENT_RULES",
    "DEFAULT_ASSUMPTIONS",
    "CoefficientRule",
    "GenerationContext",
    "default_generation_context",
]
