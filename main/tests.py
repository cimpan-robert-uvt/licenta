from django.test import TestCase

from .utils_api import _clamp_score, _compute_weighted_score, _extract_json_text


class UtilsApiTests(TestCase):
    def test_extract_json_text_handles_markdown_fenced_json_with_extra_text(self):
        raw_text = (
            "Răspuns Gemini:\n"
            "```json\n"
            '{"scor": 90, "justificare": "Potrivire bună"}\n'
            "```\n"
            "Text adițional după JSON."
        )

        extracted = _extract_json_text(raw_text)

        self.assertEqual(
            extracted,
            '{"scor": 90, "justificare": "Potrivire bună"}',
        )

    def test_compute_weighted_score_with_all_subscores_maxed_returns_100(self):
        item = {
            "skills_match": 100,
            "experience_match": 100,
            "education_match": 100,
        }

        score = _compute_weighted_score(item)

        self.assertEqual(score, 100)

    def test_compute_weighted_score_with_missing_subscore_uses_available_components(
        self,
    ):
        item = {
            "skills_match": 100,
            "experience_match": 80,
            # education_match is intentionally missing
        }

        score = _compute_weighted_score(item)

        self.assertEqual(score, 74)

    def test_clamp_score_limits_values_above_100(self):
        self.assertEqual(_clamp_score(150), 100)
