(function() {
  fetch('../../f016_sentence_augmentation/data/augmented_sentences.json?_=' + Date.now())
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || !data.augmentations) return;
      function walk(node) {
        var aug = data.augmentations[node.node_id];
        if (aug && aug.sentences) {
          aug.sentences.forEach(function(s) { s._augmented = true; });
          node.sentence_pool = (node.sentence_pool || []).concat(aug.sentences);
        }
        if (node.children) node.children.forEach(walk);
      }
      walk(treeData);
    })
    .catch(function(e) { console.warn('augment overlay failed:', e); });
})();
