function makeBranchKey(state){
  if(!state) return {};
  const key={};
  if(state.facts&&state.facts.length) key.facts=[...state.facts].sort();
  if(state.emotions&&state.emotions.length) key.emotions=[...state.emotions].sort();
  return key;
}

function findChildByFact(node, fact){
  for(const c of (node.children||[])){
    const f=c.branch_key?.facts;
    if(f&&f.length===1&&f[0]===fact) return c;
  }
  return null;
}

function findChildByEmotion(node, emotion){
  for(const c of (node.children||[])){
    const e=c.branch_key?.emotions;
    if(e&&e.includes(emotion)&&!c.branch_key?.facts?.length) return c;
  }
  return null;
}

function findChildByFactAndEmotion(node, fact, emotion){
  for(const c of (node.children||[])){
    const f=c.branch_key?.facts;
    const e=c.branch_key?.emotions;
    if(f&&f.length===1&&f[0]===fact&&e&&e.length===1&&e[0]===emotion) return c;
  }
  return null;
}

function findChildByAction(node, action){
  for(const c of (node.children||[])){
    if(c.branch_key?.action===action) return c;
  }
  return null;
}

function findChildWithSentence(node, scriptId){
  for(const c of (node.children||[])){
    if((c.sentence_pool||[]).some(s=>s.script_id===scriptId)) return c;
  }
  return null;
}

function traceDialogPath(callId){
  const dlg=dialogData.find(d=>d.call_id===callId);
  if(!dlg) return [];

  const path=[];
  const turnNodeMap={};
  let currentNode=treeData;
  let contextNode=treeData;
  path.push(currentNode._id);
  turnNodeMap[0]=currentNode._id;

  for(let i=1;i<dlg.turns.length;i++){
    const t=dlg.turns[i];
    const facts=(t.facts||[]).sort();
    const emotions=(t.emotions||[]).sort();
    const action=t.action;

    if(t.role==='客户'){
      const knownFacts=new Set(contextNode.inherited_facts||[]);
      for(const fact of facts){
        if(knownFacts.has(fact)) continue;
        let child=findChildByFact(contextNode, fact);
        if(!child){
          for(const c of (contextNode.children||[])){
            child=findChildByFact(c, fact);
            if(child){if(!path.includes(c._id))path.push(c._id);contextNode=c;break;}
          }
        }
        if(!child) child=findChildByFact(currentNode, fact);
        if(child){
          if(!path.includes(child._id)) path.push(child._id);
          currentNode=child;
          contextNode=child;
          knownFacts.add(fact);
        }
      }

      for(const emotion of emotions){
        let child=findChildByEmotion(contextNode, emotion);
        if(!child){
          for(const c of (contextNode.children||[])){
            child=findChildByEmotion(c, emotion);
            if(child){if(!path.includes(c._id))path.push(c._id);contextNode=c;break;}
          }
        }
        if(!child&&facts.length){
          const lastFact=facts[facts.length-1];
          child=findChildByFactAndEmotion(contextNode, lastFact, emotion);
        }
        if(!child) child=findChildByEmotion(currentNode, emotion);
        if(child){
          if(!path.includes(child._id)) path.push(child._id);
          currentNode=child;
          contextNode=child;
        }
      }

      turnNodeMap[i]=currentNode._id;
    } else if(t.role==='催收员'){
      if(action){
        let child=findChildByAction(contextNode, action);
        if(child){
          if(!path.includes(child._id)) path.push(child._id);
          currentNode=child;
        }
      }
      turnNodeMap[i]=currentNode._id;
    } else {
      turnNodeMap[i]=currentNode._id;
    }
  }

  const hasClosing=dlg.turns.some(t=>t.action==='closure'||t.action==='goodbye');
  const endNode=Object.values(nodeMap).find(n=>n.state_id===(hasClosing?'normal_end':'abrupt_end'));
  if(endNode&&!path.includes(endNode._id)) path.push(endNode._id);

  cachedTurnNodeMap=turnNodeMap;
  return path;
}

function buildDialogEdges(callId){
  const dlg=dialogData.find(d=>d.call_id===callId);
  if(!dlg) return [];

  const seq=[];
  let currentNode=treeData;
  let contextNode=treeData;
  seq.push(currentNode._id);

  for(let i=1;i<dlg.turns.length;i++){
    const t=dlg.turns[i];
    const facts=(t.facts||[]).sort();
    const emotions=(t.emotions||[]).sort();
    const action=t.action;

    if(t.role==='客户'){
      const knownFacts=new Set(contextNode.inherited_facts||[]);
      for(const fact of facts){
        if(knownFacts.has(fact)) continue;
        let child=findChildByFact(contextNode, fact);
        if(!child){
          for(const c of (contextNode.children||[])){
            child=findChildByFact(c, fact);
            if(child){seq.push(c._id);contextNode=c;break;}
          }
        }
        if(!child) child=findChildByFact(currentNode, fact);
        if(child){seq.push(child._id);currentNode=child;contextNode=child;knownFacts.add(fact);}
      }
      for(const emotion of emotions){
        let child=findChildByEmotion(contextNode, emotion);
        if(!child){
          for(const c of (contextNode.children||[])){
            child=findChildByEmotion(c, emotion);
            if(child){seq.push(c._id);contextNode=c;break;}
          }
        }
        if(!child&&facts.length){
          const lastFact=facts[facts.length-1];
          child=findChildByFactAndEmotion(contextNode, lastFact, emotion);
        }
        if(!child) child=findChildByEmotion(currentNode, emotion);
        if(child){seq.push(child._id);currentNode=child;contextNode=child;}
      }
    } else if(t.role==='催收员'){
      if(action){
        let child=findChildByAction(contextNode, action);
        if(child){seq.push(child._id);currentNode=child;}
      }
    }
  }

  const hasClosing=dlg.turns.some(t=>t.action==='closure'||t.action==='goodbye');
  const endNode=Object.values(nodeMap).find(n=>n.state_id===(hasClosing?'normal_end':'abrupt_end'));
  if(endNode) seq.push(endNode._id);

  return seq;
}

function highlightPath(path){
  cy.elements().removeClass('on-path off-path highlighted');
  cy.elements().style('opacity','');
  if(!path||path.length===0){
    cy.elements().style('opacity','');
    return;
  }
  const pathSet=new Set(path);
  cy.nodes().forEach(n=>{
    if(pathSet.has(n.id())) n.addClass('on-path');
    else n.addClass('off-path');
  });
  cy.edges().forEach(e=>{
    if(pathSet.has(e.data('source'))&&pathSet.has(e.data('target'))) e.addClass('on-path');
    else e.addClass('off-path');
  });
  const pathEles=cy.nodes().filter(n=>pathSet.has(n.id()));
  cy.animate({center:{eles:pathEles}},{duration:400});
}
