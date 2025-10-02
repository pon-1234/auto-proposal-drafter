from __future__ import annotations

import json
import logging
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

logger = logging.getLogger(__name__)


class VertexAIAdapter:
    """Adapter for Vertex AI Gemini models."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str = "asia-northeast1",
        model_name: str = "gemini-1.5-pro",
    ) -> None:
        """Initialize Vertex AI adapter.

        Args:
            project_id: GCP project ID
            location: Vertex AI location
            model_name: Model name (e.g., "gemini-1.5-pro")
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name

        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)

        # Initialize model
        self.model = GenerativeModel(model_name)

    def generate_content(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
        response_format: str | None = None,
    ) -> str:
        """Generate content using Vertex AI.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0.0 - 1.0)
            max_output_tokens: Maximum output tokens
            response_format: Optional response format ("json" for JSON mode)

        Returns:
            Generated text
        """
        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Add JSON mode instruction if requested
        if response_format == "json":
            prompt = f"{prompt}\n\nPlease respond with valid JSON only."

        response = self.model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        generated_text = response.text

        logger.info(
            "Generated content with Vertex AI",
            extra={
                "model": self.model_name,
                "temperature": temperature,
                "input_length": len(prompt),
                "output_length": len(generated_text),
            },
        )

        return generated_text

    def generate_json(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_output_tokens: Maximum output tokens

        Returns:
            Parsed JSON response
        """
        response = self.generate_content(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format="json",
        )

        # Parse JSON response
        try:
            # Strip markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse JSON response",
                exc_info=True,
                extra={"response": response},
            )
            raise ValueError(f"Invalid JSON response: {exc}") from exc

    def enhance_section_copy(
        self,
        *,
        section_kind: str,
        section_variant: str,
        opportunity_context: str,
        current_copy: list[str],
    ) -> list[str]:
        """Enhance section copy using Vertex AI.

        Args:
            section_kind: Section kind (e.g., "Hero", "Features")
            section_variant: Section variant (e.g., "standard", "split")
            opportunity_context: Context about the opportunity
            current_copy: Current copy lines

        Returns:
            Enhanced copy lines
        """
        prompt = f"""あなたはウェブサイトのコピーライターです。
以下のセクションのコピーを改善してください。

セクション種類: {section_kind}
バリエーション: {section_variant}

案件コンテキスト:
{opportunity_context}

現在のコピー:
{json.dumps(current_copy, ensure_ascii=False, indent=2)}

要件:
- ターゲットペルソナに響く言葉選びにする
- 具体的で行動を促す表現にする
- 簡潔で分かりやすい日本語にする
- 各行は1文〜2文程度に収める

改善後のコピーをJSON配列形式で返してください。
例: ["コピー1", "コピー2", "コピー3"]
"""

        try:
            result = self.generate_json(prompt, temperature=0.8)

            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "copy" in result:
                return result["copy"]
            else:
                logger.warning(
                    "Unexpected JSON structure from Vertex AI",
                    extra={"result": result},
                )
                return current_copy

        except Exception as exc:
            logger.error(
                "Failed to enhance section copy with Vertex AI",
                exc_info=True,
                extra={"section_kind": section_kind},
            )
            # Return original copy on failure
            return current_copy

    def suggest_additional_sections(
        self,
        *,
        opportunity_context: str,
        current_sections: list[str],
        available_sections: list[str],
    ) -> list[dict[str, str]]:
        """Suggest additional sections for the site structure.

        Args:
            opportunity_context: Context about the opportunity
            current_sections: Current section kinds in the structure
            available_sections: Available section kinds to choose from

        Returns:
            List of suggested sections with rationale
        """
        prompt = f"""あなたはウェブサイトのIA設計者です。
以下の案件に対して、追加すべきセクションを提案してください。

案件コンテキスト:
{opportunity_context}

現在のセクション構成:
{json.dumps(current_sections, ensure_ascii=False)}

利用可能なセクション:
{json.dumps(available_sections, ensure_ascii=False)}

要件:
- 案件の目的達成に必要なセクションを提案する
- 重複を避ける
- 最大3つまで提案する
- 各提案に理由を付ける

以下のJSON形式で返してください:
[
  {{"kind": "セクション種類", "variant": "standard", "reason": "追加理由"}}
]
"""

        try:
            result = self.generate_json(prompt, temperature=0.7)

            if isinstance(result, list):
                return result
            else:
                logger.warning(
                    "Unexpected JSON structure from Vertex AI",
                    extra={"result": result},
                )
                return []

        except Exception as exc:
            logger.error(
                "Failed to suggest additional sections with Vertex AI",
                exc_info=True,
            )
            return []


__all__ = ["VertexAIAdapter"]
