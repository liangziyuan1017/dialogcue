import inspect
from unittest.mock import AsyncMock, MagicMock, patch

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
    def test_is_async(self):
        assert inspect.iscoroutinefunction(extract_state_keyword)

    async def test_returns_correct_structure(self):
        mock_db = MagicMock()
        mock_db.taxonomy_keyword_search = AsyncMock(return_value=[
            {"group_name": "financial_hardship", "category": "facts"},
        ])
        result = await extract_state_keyword("我现在没钱还", TAXONOMY, db=mock_db)
        assert "facts" in result
        assert "emotions" in result
        assert "actions" in result
        assert result["method"] == "keyword"

    async def test_no_db_returns_empty(self):
        result = await extract_state_keyword("我现在没钱还", TAXONOMY, db=None)
        assert result["facts"] == []
        assert result["emotions"] == []
        assert result["actions"] == []
        assert result["confidence"] == 0.0


class TestExtractState:
    def test_is_async(self):
        assert inspect.iscoroutinefunction(extract_state)

    async def test_llm_first(self):
        mock_response = {"facts": ["financial_hardship"], "emotions": [], "actions": []}
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", return_value=mock_response), \
             patch("f008_state_extraction.state_extraction._apply_relabel"), \
             patch("f008_state_extraction.state_extraction.get_extraction_provider", return_value="llm"):
            result = await extract_state("我现在没钱还", TAXONOMY)
        assert result["method"] == "llm"

    async def test_keyword_fallback_on_llm_failure(self):
        mock_db = MagicMock()
        mock_db.taxonomy_keyword_search = AsyncMock(return_value=[
            {"group_name": "financial_hardship", "category": "facts"},
        ])
        with patch("f008_state_extraction.state_extraction.call_deepseek_json", side_effect=Exception("API error")), \
             patch("f008_state_extraction.state_extraction._apply_relabel"), \
             patch("f008_state_extraction.state_extraction.get_extraction_provider", return_value="llm"):
            result = await extract_state("我现在没钱还", TAXONOMY, db=mock_db)
        assert result["method"] == "keyword"

    async def test_bert_provider_uses_bert_extractor(self):
        bert_out = {
            "facts": ["financial_hardship"],
            "emotions": [],
            "actions": [],
            "willingness": "weak",
            "confidence": 0.8,
            "method": "bert",
        }
        with patch("f008_state_extraction.state_extraction.get_extraction_provider", return_value="bert"), \
             patch("f008_state_extraction.state_extraction.extract_state_bert", return_value=bert_out), \
             patch("f008_state_extraction.state_extraction.call_deepseek_json") as mock_llm, \
             patch("f008_state_extraction.state_extraction._apply_relabel"):
            result = await extract_state("我现在没钱还", TAXONOMY)
        assert result["method"] == "bert"
        assert "financial_hardship" in result["facts"]
        mock_llm.assert_not_called()

    async def test_bert_placeholder_falls_back_to_keyword(self):
        mock_db = MagicMock()
        mock_db.taxonomy_keyword_search = AsyncMock(return_value=[
            {"group_name": "financial_hardship", "category": "facts"},
        ])
        with patch("f008_state_extraction.state_extraction.get_extraction_provider", return_value="bert"), \
             patch(
                 "f008_state_extraction.state_extraction.extract_state_bert",
                 side_effect=NotImplementedError("placeholder"),
             ), \
             patch("f008_state_extraction.state_extraction._apply_relabel"):
            result = await extract_state("我现在没钱还", TAXONOMY, db=mock_db)
        assert result["method"] == "keyword"

    async def test_llm_call_does_not_block_event_loop(self):
        import asyncio
        import time

        other_ran = False

        async def other_task():
            nonlocal other_ran
            other_ran = True

        def slow_llm(*args, **kwargs):
            time.sleep(0.1)
            return {"facts": [], "emotions": [], "actions": []}

        with patch("f008_state_extraction.state_extraction.call_deepseek_json", side_effect=slow_llm), \
             patch("f008_state_extraction.state_extraction._apply_relabel"), \
             patch("f008_state_extraction.state_extraction.get_extraction_provider", return_value="llm"):
            task = asyncio.create_task(other_task())
            await extract_state("test", TAXONOMY)
            assert other_ran, "event loop was blocked during LLM call — other_task never ran"
            await task


class TestBertExtractorPlaceholder:
    def test_placeholder_raises(self):
        from f008_state_extraction.bert_extractor import extract_state_bert

        try:
            extract_state_bert("test")
            raise AssertionError("expected NotImplementedError")
        except NotImplementedError:
            pass

    def test_default_provider_is_llm(self):
        from f008_state_extraction.bert_extractor import get_extraction_provider

        with patch.dict("os.environ", {}, clear=False):
            # Ensure env override is not set for this check
            import os

            os.environ.pop("EXTRACTION_PROVIDER", None)
            assert get_extraction_provider() == "llm"
    def test_canonical_skip_keeps_tag(self):
        import f007_infrastructure.label_relabel as lr
        with patch.object(lr, "_FACT_DESCRIPTIONS", {"financial_hardship": {}}), \
             patch.object(lr, "_EMOTION_DESCRIPTIONS", {}), \
             patch.object(lr, "_FACT_CSV_MAP", {}), \
             patch.object(lr, "_EMOTION_CSV_MAP", {}), \
             patch.object(lr, "load_csv_relabel_maps", return_value=({}, {})), \
             patch.object(lr, "load_descriptions", return_value=({"financial_hardship": {}}, {})):
            # Force maps used inside relabel_label_list via globals set above + load stubs
            lr._FACT_CSV_MAP = {}
            lr._EMOTION_CSV_MAP = {}
            lr._FACT_DESCRIPTIONS = {"financial_hardship": {}}
            lr._EMOTION_DESCRIPTIONS = {}
            result = {"facts": ["financial_hardship"], "emotions": []}
            lr.apply_relabel(result)
        assert result["facts"] == ["financial_hardship"]

    def test_csv_map_replaces_tag(self):
        import f007_infrastructure.label_relabel as lr
        with patch.object(lr, "load_csv_relabel_maps",
                          return_value=({"unknown_tag": "financial_hardship"}, {})), \
             patch.object(lr, "load_descriptions", return_value=({}, {})), \
             patch.object(lr, "relabel_via_llm", side_effect=AssertionError("LLM should not run")):
            result = {"facts": ["unknown_tag"], "emotions": []}
            lr.apply_relabel(result)
        assert result["facts"] == ["financial_hardship"]

    def test_llm_fallback_only_when_both_miss(self):
        import f007_infrastructure.label_relabel as lr
        mock_mod = MagicMock()
        mock_mod.TAG_LABELS = {"financial_hardship": {}}
        mock_mod.build_categories_block.return_value = "cats"
        mock_mod.classify_batch.return_value = {"novel_tag": "financial_hardship"}
        mock_mod.validate_mapping.return_value = []
        with patch.object(lr, "load_csv_relabel_maps", return_value=({}, {})), \
             patch.object(lr, "load_descriptions", return_value=({"financial_hardship": {}}, {})), \
             patch.object(lr, "load_relabel_module", return_value=mock_mod), \
             patch.object(lr, "append_relabel_to_csv"), \
             patch.object(lr, "_get_client", return_value=MagicMock()):
            result = {"facts": ["novel_tag"], "emotions": []}
            lr.apply_relabel(result)
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
