function toggleView(){
  if(viewingDialog){
    viewingDialog=false;
    document.getElementById('btn-view').classList.remove('active');
    // treeToCytoscape skips ids already in these sets — reset so the full graph rebuilds
    addedNodeIds=new Set();
    addedEdgeKeys=new Set();
    const{nodes,edges,crossEdges}=treeToCytoscape(treeData);
    addLeafToEndEdges({nodes,edges},crossEdges,treeData);
    buildGraph({nodes,edges},crossEdges);
    if(tracePath.length) highlightPath(tracePath);
    else cy.fit(undefined,40);
    return;
  }
  if(!currentDialog||!tracePath.length) return;
  viewingDialog=true;
  document.getElementById('btn-view').classList.add('active');
  buildViewGraph();
  cy.nodes().addClass('on-path');
  cy.edges().addClass('on-path');
}

function buildViewGraph(){
  const seq=buildDialogEdges(currentDialog.call_id).filter(id=>nodeMap[id]);
  if(!seq.length) return;
  const sep=320;
  const seen=new Set();
  const cyNodes=[];
  const cyEdges=[];
  const nodeRow={};
  let row=0;
  for(let i=0;i<seq.length;i++){
    const id=seq[i];
    const ref=nodeMap[id];
    if(!ref) continue;
    const isFirst=!seen.has(id);
    seen.add(id);
    if(isFirst){
      const label=ref.state_id.replace(/^[afe]:/,'');
      cyNodes.push({data:{id,label,type:ref._type,nodeRef:id,poolSize:(ref.sentence_pool||[]).length}});
      nodeRow[id]=row;
      row++;
    }
  }
  for(let i=1;i<seq.length;i++){
    const src=seq[i-1],tgt=seq[i];
    if(!nodeMap[src]||!nodeMap[tgt]) continue;
    const ek=src+'->'+tgt;
    if(cyEdges.some(e=>e.data.source===src&&e.data.target===tgt)) continue;
    const ref=nodeMap[tgt];
    const bk=ref?.branch_key||{};
    let bl='';
    if(bk.facts&&bk.facts.length) bl+=bk.facts.join(', ');
    if(bk.emotions&&bk.emotions.length) bl+=(bl?' | ':'')+bk.emotions.join(', ');
    if(bk.action) bl=bk.action;
    if(!bl) bl='∅';
    const isBack=nodeRow[tgt]<=nodeRow[src];
    cyEdges.push({data:{source:src,target:tgt,label:bl},classes:isBack?'back-edge':''});
  }
  if(cy) cy.destroy();
  cy=cytoscape({
    container:document.getElementById('cy'),
    elements:{nodes:cyNodes,edges:cyEdges},
    style:CY_STYLE.concat([
      {selector:'edge.back-edge',style:{'line-style':'dashed','line-color':'#94a3b8','target-arrow-color':'#94a3b8','width':1.5}},
    ]),
    layout:{name:'preset'},
    userZoomingEnabled:true,userPanningEnabled:true,boxSelectionEnabled:false,
  });
  const rowNodes={};
  cy.nodes().forEach(n=>{
    const r=nodeRow[n.id()];
    if(r!==undefined){
      n.position({x:0,y:r*sep});
      if(!rowNodes[r]) rowNodes[r]=[];
      rowNodes[r].push(n);
    }
  });
  for(const r in rowNodes){
    const group=rowNodes[r];
    if(group.length>1){
      const spacing=280;
      const startX=-(group.length-1)*spacing/2;
      group.forEach((n,i)=>{
        n.position({x:startX+i*spacing,y:n.position('y')});
      });
    }
  }
  const backEdgeSources=new Set();
  cy.edges().filter(e=>e.hasClass('back-edge')).forEach(e=>{
    backEdgeSources.add(e.data('source'));
  });
  const maxXByRow={};
  cy.nodes().forEach(n=>{
    const r=nodeRow[n.id()];
    if(r!==undefined){
      const x=n.position('x');
      if(!maxXByRow[r]||x>maxXByRow[r]) maxXByRow[r]=x;
    }
  });
  backEdgeSources.forEach(srcId=>{
    const srcNode=cy.getElementById(srcId);
    if(srcNode&&srcNode.length){
      const r=nodeRow[srcId];
      const offset=(maxXByRow[r]||0)+280;
      srcNode.position({x:offset,y:srcNode.position('y')});
    }
  });
  cy.fit(undefined,80);
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

function renderFlow(dialog){
  const flow=document.getElementById('flow');
  if(!dialog){flow.innerHTML='<div style="color:#64748b;font-size:11px;padding:8px">Select a dialog to trace</div>';return;}
  let h='';
  dialog.turns.forEach((t,i)=>{
    const isCollector=t.role==='催收员';
    const cls=isCollector?'collector':'customer';
    let meta='';
    if(t.action) meta+=`<span class="flow-tag action">${esc(t.action)}</span>`;
    if(t.willingness) meta+=`<span class="flow-tag willingness">${esc(t.willingness)}</span>`;
    if(t.gesture_type==='opening') meta+=`<span class="flow-tag gesture-open">OPENING</span>`;
    if(t.gesture_type==='ending') meta+=`<span class="flow-tag gesture-end">ENDING</span>`;
    (t.facts||[]).forEach(f=>meta+=`<span class="flow-tag fact">${esc(f)}</span>`);
    (t.emotions||[]).forEach(e=>meta+=`<span class="flow-tag emotion">${esc(e)}</span>`);
    h+=`<div class="flow-step" data-idx="${i}" onclick="goStep(${i})">`;
    h+=`<div class="flow-num ${cls}">${i+1}</div>`;
    h+=`<div class="flow-content">`;
    h+=`<div class="flow-role ${cls}">${isCollector?'Collector':'Customer'}</div>`;
    h+=`<div class="flow-text">${esc(t.text)}</div>`;
    if(meta) h+=`<div class="flow-meta">${meta}</div>`;
    h+=`</div></div>`;
  });
  flow.innerHTML=h;
}

function selectDialog(callId){
  stopPlay();
  cachedTurnNodeMap=null;
  if(viewingDialog) toggleView();
  currentDialog=dialogData.find(d=>d.call_id===callId)||null;
  if(!currentDialog){
    tracePath=[];traceIdx=-1;
    highlightPath(null);
    renderFlow(null);
    document.getElementById('node-info').innerHTML='';
    document.getElementById('info-panel').classList.remove('open');
    document.getElementById('btn-end').classList.remove('abrupt');
    return;
  }
  tracePath=traceDialogPath(callId);
  traceIdx=-1;
  highlightPath(tracePath);
  renderFlow(currentDialog);

  const hasClosing=currentDialog.turns.some(t=>t.action==='closure'||t.action==='goodbye');
  const endBtn=document.getElementById('btn-end');
  endBtn.classList.toggle('abrupt',!hasClosing);
  endBtn.textContent=hasClosing?'End':'Abrupt End';
}

function buildTurnNodeMap(){
  if(cachedTurnNodeMap) return cachedTurnNodeMap;
  return {};
}

function stopPlay(){
  if(playTimer){clearTimeout(playTimer);playTimer=null;}
  isPlaying=false;
  document.getElementById('btn-start').classList.remove('playing');
  document.getElementById('btn-start').textContent='Start';
}

function goStart(){
  if(!currentDialog) return;
  if(isPlaying){stopPlay();return;}
  isPlaying=true;
  document.getElementById('btn-start').classList.add('playing');
  document.getElementById('btn-start').textContent='Pause';
  traceIdx=-1;
  advanceStep();
}

function advanceStep(){
  if(!isPlaying||!currentDialog) return;
  traceIdx++;
  if(traceIdx>=currentDialog.turns.length){
    stopPlay();
    return;
  }
  activateStep(traceIdx);
  playTimer=setTimeout(()=>{requestAnimationFrame(advanceStep);}, 1400);
}

function goEnd(){
  stopPlay();
  if(!currentDialog) return;
  traceIdx=currentDialog.turns.length-1;
  activateStep(traceIdx);
}

function activateStep(idx){
  if(!currentDialog) return;
  const turnMap=buildTurnNodeMap();
  const nodeId=turnMap[idx];

  document.querySelectorAll('.flow-step').forEach(el=>el.classList.remove('active'));
  const stepEl=document.querySelector(`.flow-step[data-idx="${idx}"]`);
  if(stepEl){
    stepEl.classList.add('active');
    const flowContainer=document.getElementById('flow');
    const stepTop=stepEl.offsetTop - flowContainer.offsetTop;
    flowContainer.scrollTop = stepTop - 40;
  }

  if(nodeId){
    const cyNode=cy.getElementById(nodeId);
    if(cyNode&&cyNode.length>0){
      cy.nodes().removeClass('highlighted');
      cyNode.addClass('highlighted');
      cy.center(cyNode);
    }
    showNodeInfo(nodeMap[nodeId]);
  }
}

function goStep(idx){
  stopPlay();
  traceIdx=idx;
  activateStep(idx);
}

function showNodeInfo(node){
  const panel=document.getElementById('info-panel');
  if(!node){panel.classList.remove('open');document.getElementById('node-info').innerHTML='';return;}
  panel.classList.add('open');
  if(cachedTurnNodeMap&&node._id){
    const matchingTurns=Object.entries(cachedTurnNodeMap).filter(([idx,nid])=>nid===node._id).map(([idx])=>parseInt(idx));
    if(matchingTurns.length){
      const firstIdx=matchingTurns[0];
      const stepEl=document.querySelector(`.flow-step[data-idx="${firstIdx}"]`);
      if(stepEl){
        document.querySelectorAll('.flow-step').forEach(el=>el.classList.remove('active'));
        matchingTurns.forEach(idx=>{
          const el=document.querySelector(`.flow-step[data-idx="${idx}"]`);
          if(el) el.classList.add('active');
        });
        const flowPanel=document.getElementById('flow-panel');
        flowPanel.scrollTo({top:stepEl.offsetTop-flowPanel.offsetTop-20,behavior:'smooth'});
      }
    }
  }
  const ni=document.getElementById('node-info');
  const type=node._type;
  const tl={opening:'Opening (Start)',decision:'Decision Point',emotion:'Emotion',action:'Collector Action',ending:'Normal End',abrupt:'Abrupt End'};
  let h=`<h3>${esc(node.state_id)}</h3>`;
  h+=`<div class="ni-section"><div class="ni-title">Type</div>${tl[type]||type}</div>`;
  const bk=node.branch_key||{};
  h+=`<div class="ni-section"><div class="ni-title">Branch Key</div>`;
  (bk.facts||[]).forEach(f=>h+=`<span class="ni-tag fact">${esc(f)}</span>`);
  (bk.emotions||[]).forEach(e=>h+=`<span class="ni-tag emotion">${esc(e)}</span>`);
  if(!bk.facts?.length&&!bk.emotions?.length&&!bk.abrupt&&!bk.end_type) h+=`<span style="color:#64748b">∅</span>`;
  h+=`</div>`;
  const inf=node.inherited_facts||[];
  h+=`<div class="ni-section"><div class="ni-title">Inherited Facts</div>`;
  if(inf.length) inf.forEach(f=>h+=`<span class="ni-tag fact">${esc(f)}</span>`);
  else h+=`<span style="color:#64748b">∅</span>`;
  h+=`</div>`;
  const rawPool=node.sentence_pool||[];
  const seen=new Set();
  const pool=[];
  for(const s of rawPool){const k=s.script_text||'';if(!seen.has(k)){seen.add(k);pool.push(s);}}
  h+=`<div class="ni-section"><div class="ni-title">Sentences (${pool.length}${pool.length<rawPool.length?' (deduped from '+rawPool.length+')':''})</div>`;
  pool.slice(0,10).forEach(s=>{
    let tags='';
    if(s.collector_action) tags+=`<span class="flow-tag action" style="margin-right:3px">${esc(s.collector_action)}</span>`;
    if(s.customer_willingness) tags+=`<span class="flow-tag willingness" style="margin-right:3px">${esc(s.customer_willingness)}</span>`;
    const fc=s.fact_context||[];
    if(fc.length) tags+=fc.map(f=>`<span class="flow-tag fact" style="margin-right:3px">${esc(f)}</span>`).join('');
    let scores='';
    if(s.win_rate!==undefined){
      const wr=s.win_rate;
      const wrCls=wr>=0.6?'score-high':wr<0.4?'score-low':'score';
      const wrPct=Math.round(wr*100);
      scores+=`<span class="score-row"><span>HWR</span><span class="sbar"><span class="sbar-fill" style="width:${wrPct}%;background:${wr>=0.6?'#22c55e':wr<0.4?'#ef4444':'#f59e0b'}"></span></span><span>${wrPct}%</span></span>`;
    }
    if(s.sas!==undefined){
      const sa=s.sas;
      const saPct=Math.round(sa*100);
      scores+=`<span class="score-row"><span>SAS</span><span class="sbar"><span class="sbar-fill" style="width:${saPct}%;background:${sa>=0.7?'#22c55e':sa<0.4?'#ef4444':'#f59e0b'}"></span></span><span>${saPct}%</span></span>`;
    }
    if(s.bg_bitmask_int!==undefined){
      scores+=`<span class="score-row"><span>CTX</span><span>0b${s.bg_bitmask_int.toString(2).padStart(10,'0')}</span></span>`;
    }
    h+=`<div class="ni-script">${tags}<span class="stxt">${esc(s.script_text)}</span>${scores}<div class="smeta">${esc(s.script_id)}</div></div>`;
  });
  if(pool.length>10) h+=`<div style="color:#64748b;font-size:10px">...and ${pool.length-10} more</div>`;
  h+=`</div>`;
  ni.innerHTML=h;
}
