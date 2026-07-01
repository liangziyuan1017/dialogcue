from unittest.mock import MagicMock, patch

from f008_state_extraction.state_extraction import (
    extract_state,
    extract_state_keyword,
    extract_state_llm,
    flat_to_path_state,
    merge_state,
    path_state_to_flat,
)

TAXONOMY = {
    "facts": [{"group_name": "financial_hardship", "keywords": ["没钱", "没有钱", "经济困难"]}],
    "emotions": [{"group_name": "pleading", "keywords": ["求求你", "拜托"]}],
    "collector_actions": [{"group_name": "empathy", "keywords": ["理解", "体谅"]}],
    "willingness_levels": [
        {"level": 0, "definition": "拒绝还款"},
        {"level": 5, "definition": "同意还款"},
    ],
}


class TestExtractStateLLM:
    def test_returns_correct_structure(self):
        mock_response = {
            "facts": [{"keyword": "没钱", "group": "financial_hardship"}],
            "emotions": [],
            "actions": [],
            "confidence": 0.9,
        }
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state_llm("我现在没钱还", TAXONOMY)
        assert "facts" in result
        assert "emotions" in result
        assert "actions" in result
        assert "confidence" in result
        assert result["method"] == "llm"

    def test_returns_lists(self):
        mock_response = {
            "facts": [{"keyword": "没钱", "group": "financial_hardship"}],
            "emotions": [{"keyword": "求求你", "group": "pleading"}],
            "actions": [],
        }
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state_llm("我现在没钱还", TAXONOMY)
        assert isinstance(result["facts"], list)
        assert isinstance(result["emotions"], list)
        assert isinstance(result["actions"], list)

    def test_open_set_extraction(self):
        mock_response = {
            "facts": [{"keyword": "x", "group": "novel_fact_xyz"}],
            "emotions": [{"keyword": "y", "group": "novel_emo_abc"}],
            "actions": [],
            "confidence": 0.8,
        }
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state_llm("some novel utterance", TAXONOMY)
        assert "novel_fact_xyz" in result["facts"]
        assert "novel_emo_abc" in result["emotions"]

    def test_willingness_five_levels(self):
        for level in ["resistant", "weak", "conditional", "negotiating", "strong"]:
            mock_response = {"facts": [], "emotions": [], "actions": [], "willingness": level}
            with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response):
                result = extract_state_llm("utterance", TAXONOMY)
            assert result["willingness"] == level


class TestExtractStateKeyword:
    def test_returns_correct_structure(self):
        mock_db = MagicMock()
        mock_db.keyword_search.return_value = [
            {"group_name": "financial_hardship", "category": "facts"},
        ]
        result = extract_state_keyword("我现在没钱还", TAXONOMY, db=mock_db)
        assert "facts" in result
        assert "emotions" in result
        assert "actions" in result
        assert result["method"] == "keyword"

    def test_no_db_returns_empty(self):
        result = extract_state_keyword("我现在没钱还", TAXONOMY, db=None)
        assert result["facts"] == []
        assert result["emotions"] == []
        assert result["actions"] == []
        assert result["confidence"] == 0.0


class TestExtractState:
    def test_llm_first(self):
        mock_response = {"facts": ["financial_hardship"], "emotions": [], "actions": []}
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response), \
             patch("f008_state_extraction.state_extraction._apply_relabel"):
            result = extract_state("我现在没钱还", TAXONOMY)
        assert result["method"] == "llm"

    def test_keyword_fallback_on_llm_failure(self):
        mock_db = MagicMock()
        mock_db.keyword_search.return_value = [
            {"group_name": "financial_hardship", "category": "facts"},
        ]
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", side_effect=Exception("API error")), \
             patch("f008_state_extraction.state_extraction._apply_relabel"):
            result = extract_state("我现在没钱还", TAXONOMY, db=mock_db)
        assert result["method"] == "keyword"


class TestRelabelCascade:
    def test_canonical_skip_keeps_tag(self):
        import f008_state_extraction.state_extraction as se
        with patch.object(se, "_FACT_DESCRIPTIONS", {"financial_hardship": {}}), \
             patch.object(se, "_EMOTION_DESCRIPTIONS", {}), \
             patch.object(se, "_FACT_CSV_MAP", {}), \
             patch.object(se, "_EMOTION_CSV_MAP", {}), \
             patch.object(se, "_load_csv_relabel_maps"), \
             patch.object(se, "_load_descriptions"):
            result = {"facts": ["financial_hardship"], "emotions": []}
            se._apply_relabel(result)
        assert result["facts"] == ["financial_hardship"]

    def test_csv_map_replaces_tag(self):
        import f008_state_extraction.state_extraction as se
        with patch.object(se, "_FACT_DESCRIPTIONS", {}), \
             patch.object(se, "_EMOTION_DESCRIPTIONS", {}), \
             patch.object(se, "_FACT_CSV_MAP", {"unknown_tag": "financial_hardship"}), \
             patch.object(se, "_EMOTION_CSV_MAP", {}), \
             patch.object(se, "_load_csv_relabel_maps"), \
             patch.object(se, "_load_descriptions"):
            result = {"facts": ["unknown_tag"], "emotions": []}
            se._apply_relabel(result)
        assert result["facts"] == ["financial_hardship"]

    def test_llm_fallback_only_when_both_miss(self):
        import f008_state_extraction.state_extraction as se
        mock_mod = MagicMock()
        mock_mod.TAG_LABELS = {"financial_hardship": {}}
        mock_mod.build_categories_block.return_value = "cats"
        mock_mod.SYSTEM_PROMPT = "sys {categories}"
        mock_mod.USER_PROMPT_TEMPLATE = "user {count} {tags}"
        with patch.object(se, "_FACT_DESCRIPTIONS", {}), \
             patch.object(se, "_EMOTION_DESCRIPTIONS", {}), \
             patch.object(se, "_FACT_CSV_MAP", {}), \
             patch.object(se, "_EMOTION_CSV_MAP", {}), \
             patch.object(se, "_load_csv_relabel_maps"), \
             patch.object(se, "_load_descriptions"), \
             patch.object(se, "_get_fact_relabel_module", return_value=mock_mod), \
             patch.object(se, "_get_emotion_relabel_module", return_value=mock_mod), \
             patch.object(se, "_append_relabel_to_csv"), \
             patch("f008_state_extraction.state_extraction.call_deepseek_json",
                   return_value={"novel_tag": "financial_hardship"}):
            result = {"facts": ["novel_tag"], "emotions": []}
            se._apply_relabel(result)
        assert result["facts"] == ["financial_hardship"]


class TestMergeStatePath:
    def test_initial_fact_sets_branch_key(self):
        existing = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": ["financial_hardship"], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"facts": ["financial_hardship"]}
        assert result["inherited_facts"] == []

    def test_second_fact_promotes_first_to_inherited(self):
        existing = {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": ["request_installment"], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"facts": ["request_installment"]}
        assert "financial_hardship" in result["inherited_facts"]

    def test_emotion_sets_branch_key(self):
        existing = {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": [], "emotions": ["disappointment"], "actions": []}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"emotions": ["disappointment"]}
        assert "financial_hardship" in result["inherited_facts"]

    def test_action_sets_branch_key(self):
        existing = {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": [], "emotions": [], "actions": ["plan_proposal"]}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"action": "plan_proposal"}
        assert "financial_hardship" in result["inherited_facts"]

    def test_deduplicates_facts(self):
        existing = {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": ["financial_hardship"], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"facts": ["financial_hardship"]}
        assert result["inherited_facts"] == []

    def test_willingness_overwrites(self):
        existing = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": "weak"}
        new = {"facts": [], "emotions": [], "actions": [], "willingness": "conditional"}
        result = merge_state(existing, new)
        assert result["willingness"] == "conditional"

    def test_willingness_preserved_when_null(self):
        existing = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": "conditional"}
        new = {"facts": [], "emotions": [], "actions": [], "willingness": None}
        result = merge_state(existing, new)
        assert result["willingness"] == "conditional"

    def test_no_new_state_preserves_branch_key(self):
        existing = {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        new = {"facts": [], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["branch_key"] == {"facts": ["financial_hardship"]}


class TestPathStateConversion:
    def test_roundtrip(self):
        facts = ["a", "b", "c"]
        emotions = ["x", "y"]
        actions = []
        ps = flat_to_path_state(facts, emotions, actions, "conditional")
        rf, re, ra = path_state_to_flat(ps)
        assert set(rf) == set(facts)
        assert set(re) == set(emotions)
        assert ra == actions

    def test_empty_state(self):
        ps = flat_to_path_state([], [], [])
        assert ps["branch_key"] == {}
        assert ps["inherited_facts"] == []
        assert ps["inherited_emotions"] == []
