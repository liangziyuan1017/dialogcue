# Fix: /recommend always returns same sentence — descend into children on empty pool

## Bug

`/recommend` always returned the same sentence regardless of input, with only `state_tags` varying.

**Root cause**: `_find_matching_nodes_subset()` used `aggregate_pools(nodes)` as the sole validity check. When a node's own `sentence_pool` was empty (sentences lived in child/leaf nodes), the function skipped the node and fell back to root (`initial_contact`, 308 sentences). 23 of 32 single-label nodes have empty pools.

## Diff

### `src/f006_retrieval_engine/retrieval_engine.py`

```diff
@@ -79,6 +79,11 @@ def aggregate_pools(nodes):
     return pool
 
 
+def _has_reachable_sentences(nodes):
+    pool, _, _ = descend_for_sentences(nodes)
+    return bool(pool)
+
+
 def _find_matching_nodes_subset(all_facts, all_emotions, all_actions, index, label_set_index, pool_cap=None):
     if pool_cap is None:
         pool_cap = _pool_cap()
@@ -90,7 +95,7 @@ def _find_matching_nodes_subset(all_facts, all_emotions, all_actions, index, lab
 
     if query_items and query_items in label_set_index:
         nodes = label_set_index[query_items]
-        if aggregate_pools(nodes):
+        if _has_reachable_sentences(nodes):
             return nodes, 1.0, []
 
     drop_order = []
@@ -133,8 +138,9 @@ def _find_matching_nodes_subset(all_facts, all_emotions, all_actions, index, lab
                     unique.append(n)
 
             pool = aggregate_pools(unique)
-            if pool:
-                if len(pool) <= pool_cap:
+            if not pool:
+                pool, _, _ = descend_for_sentences(unique)
+            if pool and len(pool) <= pool_cap:
                     n_dropped = n_drop_e + n_drop_f
                     conf = max(0.0, 1.0 - n_dropped * _cfg("confidence.subset_drop_penalty", 0.1))
                     fb = ["subset_drop_emotion"] * n_drop_e + ["subset_drop_fact"] * n_drop_f
@@ -145,7 +151,7 @@ def _find_matching_nodes_subset(all_facts, all_emotions, all_actions, index, lab
             break
 
     root_nodes = label_set_index.get(frozenset(), [])
-    if root_nodes and aggregate_pools(root_nodes):
+    if root_nodes and _has_reachable_sentences(root_nodes):
         fb = ["root_fallback"]
         if truncated:
             fb.append("subset_search_truncated")
```

### `src/tests/f006_retrieval_engine/test_retrieval_engine.py`

```diff
@@ -130,6 +130,35 @@ class TestSubsetMatchFallback:
             assert isinstance(nodes, list)
 
 
+class TestDescendIntoChildrenForPool:
+    def test_anxiety_node_returned_not_root(self, tree, index, label_set_index):
+        nodes, conf, fb = _find_matching_nodes_subset(
+            ["anxiety"], [], [], index, label_set_index
+        )
+        assert len(nodes) > 0
+        for n in nodes:
+            assert n.get("state_id", "") != "initial_contact"
+        assert "root_fallback" not in fb
+
+    def test_personal_info_node_returned_not_root(self, tree, index, label_set_index):
+        nodes, conf, fb = _find_matching_nodes_subset(
+            ["personal_info"], [], [], index, label_set_index
+        )
+        assert len(nodes) > 0
+        for n in nodes:
+            assert n.get("state_id", "") != "initial_contact"
+        assert "root_fallback" not in fb
+
+    def test_income_loss_node_returned_not_root(self, tree, index, label_set_index):
+        nodes, conf, fb = _find_matching_nodes_subset(
+            ["income_loss"], [], [], index, label_set_index
+        )
+        assert len(nodes) > 0
+        for n in nodes:
+            assert n.get("state_id", "") != "initial_contact"
+        assert "root_fallback" not in fb
+
+
 class TestFallbacksStillWork:
     async def test_empty_key_fallback(self, tree, index, label_set_index):
         result = await recommend(
```

## Before/After

| Input | Before | After |
|-------|--------|-------|
| `anxiety` | root (conf=0.2, root_fallback) | anxiety children (conf=0.95, descend) |
| `personal_info` | root (conf=0.2, root_fallback) | personal_info children (conf=0.95, descend) |
| `income_loss` | root (conf=0.2, root_fallback) | income_loss children (conf=0.95, descend) |
