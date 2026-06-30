let cy, treeData, nodeMap={}, dialogData=[], currentDialog=null, tracePath=[], traceIdx=-1, playTimer=null, isPlaying=false, cachedTurnNodeMap=null, viewingDialog=false, addedNodeIds=new Set(), addedEdgeKeys=new Set();

const CY_STYLE=[
  {selector:'node[type="opening"]',style:{'shape':'round-rectangle','width':280,'height':44,'background-color':'#052e16','border-color':'#22c55e','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#4ade80','font-size':14,'font-weight':600,'font-family':'-apple-system,sans-serif','text-wrap':'wrap','text-max-width':260}},
  {selector:'node[type="decision"]',style:{'shape':'round-rectangle','width':280,'height':44,'background-color':'#1e3a5f','border-color':'#3b82f6','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#60a5fa','font-size':13,'font-weight':600,'font-family':'-apple-system,sans-serif','text-wrap':'wrap','text-max-width':260}},
  {selector:'node[type="emotion"]',style:{'shape':'ellipse','width':200,'height':50,'background-color':'#2e1065','border-color':'#a78bfa','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#c4b5fd','font-size':13,'font-weight':600,'font-family':'-apple-system,sans-serif'}},
  {selector:'node[type="action"]',style:{'shape':'diamond','width':200,'height':100,'background-color':'#422006','border-color':'#f59e0b','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#fbbf24','font-size':13,'font-weight':600,'font-family':'-apple-system,sans-serif'}},
  {selector:'node[type="ending"]',style:{'shape':'ellipse','width':180,'height':60,'background-color':'#422006','border-color':'#f59e0b','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#fbbf24','font-size':14,'font-weight':600,'font-family':'-apple-system,sans-serif'}},
  {selector:'node[type="abrupt"]',style:{'shape':'triangle','width':160,'height':80,'background-color':'#450a0a','border-color':'#ef4444','border-width':2,'label':'data(label)','text-halign':'center','text-valign':'center','color':'#f87171','font-size':12,'font-weight':600,'font-family':'-apple-system,sans-serif'}},
  {selector:'edge',style:{'width':2,'line-color':'#334155','target-arrow-color':'#334155','target-arrow-shape':'triangle','curve-style':'bezier','arrow-scale':1.4,'label':'data(label)','font-size':9,'font-weight':500,'color':'#64748b','text-rotation':'autorotate','text-margin-y':-5,'text-wrap':'wrap','text-max-width':100}},
  {selector:'edge.action-flow',style:{'width':1,'line-color':'#475569','target-arrow-color':'#475569','line-style':'dashed','label':'','curve-style':'bezier','arrow-scale':1.4}},
  {selector:'node.on-path',style:{'border-width':2,'border-color':'#94a3b8','background-opacity':1}},
  {selector:'edge.on-path',style:{'width':2,'line-color':'#60a5fa','target-arrow-color':'#60a5fa','color':'#60a5fa'}},
  {selector:'node.off-path',style:{'opacity':0.2}},
  {selector:'edge.off-path',style:{'opacity':0.1}},
  {selector:'node.highlighted',style:{'border-width':3,'border-color':'#ffffff','background-color':'#1e3a5f'}},
  {selector:'edge.edge-highlighted',style:{'width':3,'line-color':'#fbbf24','target-arrow-color':'#fbbf24','color':'#fbbf24','line-style':'solid'}},
];

function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function nodeType(node,depth){
  if(depth===0) return 'opening';
  if(node.state_id==='abrupt_end') return 'abrupt';
  if(node.state_id==='normal_end') return 'ending';
  const bk=node.branch_key||{};
  const hasFacts=bk.facts&&bk.facts.length>0;
  const hasEmotions=bk.emotions&&bk.emotions.length>0;
  if(!hasFacts&&hasEmotions) return 'emotion';
  if(bk.action) return 'action';
  return 'decision';
}

function indexTree(node,parentId=null,depth=0){
  const id=node.node_id||(node.state_id+'_'+Math.random().toString(36).slice(2,6));
  node._id=id;node._parentId=parentId;node._depth=depth;node._type=nodeType(node,depth);
  if(!nodeMap[id]) nodeMap[id]=node;
  (node.children||[]).forEach(c=>indexTree(c,id,depth+1));
}

function treeToCytoscape(node,pid=null,depth=0){
  const id=node._id, type=node._type, pool=node.sentence_pool||[], kids=node.children||[];
  let label=node.state_id.replace(/^[afe]:/,'');
  const cyNodes=[];
  const cyEdges=[];
  const crossEdges=[];
  if(!addedNodeIds.has(id)){
    cyNodes.push({data:{id,label,type,nodeRef:id,poolSize:pool.length}});
    addedNodeIds.add(id);
  }
  if(pid!==null){
    const bk=node.branch_key||{};
    let bl='';
    if(bk.facts&&bk.facts.length) bl+=bk.facts.join(', ');
    if(bk.emotions&&bk.emotions.length) bl+=(bl?' | ':'')+bk.emotions.join(', ');
    if(bk.action) bl=bk.action;
    if(bk.abrupt) bl='abrupt';
    if(bk.end_type==='normal') bl='normal end';
    if(bk.end_type==='abrupt') bl='abrupt end';
    if(!bl) bl='∅';
    const ek=pid+'->'+id;
    if(!addedEdgeKeys.has(ek)){
      cyEdges.push({data:{source:pid,target:id,label:bl,weight:1}});
      addedEdgeKeys.add(ek);
    }
  }
  for(const child of kids){
    const sub=treeToCytoscape(child,id,depth+1);
    cyNodes.push(...sub.nodes);
    cyEdges.push(...sub.edges);
    crossEdges.push(...sub.crossEdges);
  }
  const actionKids=kids.filter(c=>c._type==='action');
  const nonActionKids=kids.filter(c=>c._type!=='action');
  if(actionKids.length&&nonActionKids.length){
    for(const ak of actionKids){
      for(const nak of nonActionKids){
        const ek=ak._id+'->'+nak._id;
        if(!addedEdgeKeys.has(ek)){
          crossEdges.push({data:{source:ak._id,target:nak._id,label:'',weight:0,classes:'action-flow'}});
          addedEdgeKeys.add(ek);
        }
      }
    }
  }
  return {nodes:cyNodes,edges:cyEdges,crossEdges,leafActions:[]};
}

function addLeafToEndEdges(elements,crossEdges,treeData){
  const normalEnd=Object.values(nodeMap).find(n=>n.state_id==='normal_end');
  const abruptEnd=Object.values(nodeMap).find(n=>n.state_id==='abrupt_end');
  if(!normalEnd||!abruptEnd) return;
  const normalId=normalEnd._id, abruptId=abruptEnd._id;
  const existingEdges=new Set(elements.edges.map(e=>e.data.source+'->'+e.data.target));
  for(const node of Object.values(nodeMap)){
    if(node._type==='action'&&!node.children?.length){
      const srcId=node._id;
      const hasClosing=(node.sentence_pool||[]).some(s=>s.collector_action==='closure'||s.collector_action==='goodbye');
      const endId=hasClosing?normalId:abruptId;
      const ek=srcId+'->'+endId;
      if(!existingEdges.has(ek)&&!addedEdgeKeys.has(ek)){
        crossEdges.push({data:{source:srcId,target:endId,label:'',weight:0,classes:'action-flow'}});
        existingEdges.add(ek);
        addedEdgeKeys.add(ek);
      }
    }
  }
}

function buildGraph(elements,crossEdges){
  if(cy) cy.destroy();
  cy=cytoscape({
    container:document.getElementById('cy'),
    elements,
    style:CY_STYLE,
    layout:{name:'dagre',rankDir:'TB',spacingFactor:1.2,nodeSep:30,rankSep:120},
    userZoomingEnabled:true,userPanningEnabled:true,boxSelectionEnabled:false,
  });
  if(crossEdges&&crossEdges.length) cy.add(crossEdges.map(e=>({group:'edges',data:e.data,classes:e.data.classes||''})));
  applyDepthSpacing();
  cy.on('tap','node',function(e){
    const node=e.target;
    const refId=node.data('nodeRef');
    cy.edges().removeClass('edge-highlighted');
    node.connectedEdges().addClass('edge-highlighted');
    if(refId) showNodeInfo(nodeMap[refId]);
  });
  cy.on('tap','edge',function(){cy.edges().removeClass('edge-highlighted');});
  cy.on('tap',function(e){if(e.target===cy){cy.edges().removeClass('edge-highlighted');document.getElementById('info-panel').classList.remove('open');}});
}

function applyDepthSpacing(){
  const sep=120;
  assignFullLayout(sep);
  const endIds=new Set();
  cy.nodes().forEach(n=>{if(n.data('type')==='ending'||n.data('type')==='abrupt') endIds.add(n.id());});
  let maxY=0;
  cy.nodes().forEach(n=>{if(!endIds.has(n.id())&&n.position('y')>maxY) maxY=n.position('y');});
  const endY=maxY+sep*2;
  let minX=Infinity, maxX=-Infinity;
  cy.nodes().forEach(n=>{if(!endIds.has(n.id())){if(n.position('x')<minX)minX=n.position('x');if(n.position('x')>maxX)maxX=n.position('x');}});
  const centerX=(minX+maxX)/2;
  const endNodes=cy.nodes().filter(n=>endIds.has(n.id()));
  const endCount=endNodes.length;
  const endSpacing=200;
  const startX=centerX-(endCount-1)*endSpacing/2;
  endNodes.forEach((n,i)=>{
    n.position({x:startX+i*endSpacing,y:endY});
  });
}

function assignFullLayout(sep){
  const depthGroups={};
  cy.nodes().forEach(n=>{
    const refId=n.data('nodeRef');
    const ref=refId?nodeMap[refId]:null;
    const d=ref?ref._depth:0;
    if(!(d in depthGroups)) depthGroups[d]=[];
    depthGroups[d].push(n);
  });
  const sortedDepths=Object.keys(depthGroups).map(Number).sort((a,b)=>a-b);
  const depthY={};
  for(let i=0;i<sortedDepths.length;i++){
    const d=sortedDepths[i];
    if(i===0) depthY[d]=0;
    else{
      const prevD=sortedDepths[i-1];
      const mult=prevD===0?3:prevD<=2?2:1;
      const extra=prevD>=3?0.5:0;
      depthY[d]=depthY[prevD]+sep*(mult+extra);
    }
  }
  for(const d of sortedDepths){
    const y=depthY[d];
    depthGroups[d].forEach(n=>{
      n.position({x:n.position('x'),y:y});
    });
  }
  enforceParentAboveChild(sep);
}

function enforceParentAboveChild(sep){
  const treeEdges=cy.edges().filter(e=>!e.hasClass('action-flow'));
  const nodeTreeDepth={};
  cy.nodes().forEach(n=>{
    const refId=n.data('nodeRef');
    const ref=refId?nodeMap[refId]:null;
    nodeTreeDepth[n.id()]=ref?ref._depth:0;
  });
  const nodeY={};
  cy.nodes().forEach(n=>{nodeY[n.id()]=n.position('y');});
  const forwardEdges=treeEdges.filter(e=>{
    const src=e.data('source'),tgt=e.data('target');
    return (nodeTreeDepth[tgt]||0)>(nodeTreeDepth[src]||0);
  });
  let changed=true;
  let iterations=0;
  while(changed&&iterations<50){
    changed=false;
    iterations++;
    forwardEdges.forEach(e=>{
      const src=e.data('source'),tgt=e.data('target');
      if(nodeY[tgt]<=nodeY[src]){
        nodeY[tgt]=nodeY[src]+sep;
        changed=true;
      }
    });
  }
  cy.nodes().forEach(n=>{
    const y=nodeY[n.id()];
    if(y!==undefined&&y!==n.position('y')){
      n.position({x:n.position('x'),y:y});
    }
  });
}

function countNodes(n,visited=new Set()){if(visited.has(n._id))return 0;visited.add(n._id);return 1+(n.children||[]).reduce((s,c)=>s+countNodes(c,visited),0);}

Promise.all([
  fetch('../../f005_context_scoring/data/decision_tree_scored.json?_='+Date.now()).then(r=>r.json()),
  fetch('../../f004_decision_tree/data/dialog_records.json?_='+Date.now()).then(r=>r.json()),
]).then(([tree,dialogs])=>{
  treeData=tree;
  dialogData=dialogs;
  nodeMap={};
  addedNodeIds=new Set();
  addedEdgeKeys=new Set();
  indexTree(tree);
  const{nodes,edges,crossEdges}=treeToCytoscape(tree);
  addLeafToEndEdges({nodes,edges},crossEdges,tree);
  const total=countNodes(tree);
  document.getElementById('stats').textContent=`${total} nodes · ${dialogs.length} dialogs · 1 opening · 1 normal end · 1 abrupt end`;
  buildGraph({nodes,edges},crossEdges,{0:3,1:3,2:2});

  const sel=document.getElementById('dialog-select');
  dialogs.forEach((d,i)=>{
    const opt=document.createElement('option');
    opt.value=d.call_id;
    const hasClosing=d.turns.some(t=>t.action==='closure'||t.action==='goodbye');
    opt.textContent=`${i+1}. ${d.call_id.slice(-6)} (${d.turns.length} turns${hasClosing?' → normal':' → abrupt'})`;
    sel.appendChild(opt);
  });
  sel.addEventListener('change',()=>selectDialog(sel.value));
  renderFlow(null);
});
