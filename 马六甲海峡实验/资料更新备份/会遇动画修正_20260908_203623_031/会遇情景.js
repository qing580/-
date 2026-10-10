(() => {
  'use strict';
  const originalOverview = showOverviewPage;
  const key = 'malacca-encounter-intro-v3';
  let audio = null, muted = false, soundNodes = [], chosen = null;
  let seen = false, animation = 0, pending = null, priorFocus = null, expanded = false;
  try { seen = sessionStorage.getItem(key) === 'seen'; } catch (_) { /* Private/file browser contexts can disable storage. */ }
  const intro = document.createElement('section');
  intro.id = 'encounterIntro'; intro.hidden = true;
  intro.setAttribute('role', 'dialog'); intro.setAttribute('aria-modal', 'true'); intro.setAttribute('aria-labelledby', 'encTitle');
  intro.innerHTML = `<header class="enc-header"><div><strong id="encTitle">繁忙港区会遇风险情景</strong><span class="enc-label">情景夸张演示，非当前船舶事故</span></div><div class="enc-controls"><button class="enc-action" id="encSound" aria-pressed="false" title="切换音效">音效：开</button><button class="enc-action" id="encExit">返回总览</button></div></header>
    <div class="enc-stage"><div class="enc-status"><span id="encPhase" role="status">01 / 繁忙港口</span><span>港口情景 · 非真实预测</span></div>
    <canvas class="enc-canvas" width="1120" height="490" aria-label="两艘扁平风格船舶在港口接近并发生示意碰撞"></canvas>
    <div class="enc-question"><h2 id="encQuestion">繁忙港口里，一次近距离交汇</h2><p id="encCaption">两艘船正在驶向同一片水域。</p><button id="encContinue" class="enc-action primary">跳过演示，进入分析</button></div></div>`;
  document.body.append(intro);
  const canvas = intro.querySelector('canvas'), ctx = canvas.getContext('2d');
  const neighbors = document.createElement('section');
  neighbors.className = 'enc-neighbors'; neighbors.setAttribute('aria-label', '周边船舶');
  const analysis = document.createElement('section');
  analysis.id = 'encAnalysis'; analysis.hidden = true;
  analysis.innerHTML = `<header class="enc-header"><div><strong id="encAnalysisTitle" tabindex="-1">船舶会遇风险研判</strong><span class="enc-label" id="encAnalysisTime"></span></div><div class="enc-controls"><button class="enc-action" id="encReport">综合安全报告</button><button class="enc-action" id="encBack">返回总览</button></div></header><div class="enc-analysis-body"><main id="encPrimary"></main><aside id="encAside"></aside></div>`;
  document.body.append(analysis);
  analysis.querySelector('#encAside').append(neighbors);
  analysis.querySelector('#encBack').onclick = () => { analysis.hidden = true; originalOverview(); };
  analysis.querySelector('#encReport').onclick = () => { analysis.hidden = true; showDetailPage(); };
  const reportBack = document.createElement('button');
  reportBack.className = 'enc-action'; reportBack.textContent = '返回会遇分析';
  document.querySelector('.detail-top').append(reportBack);
  reportBack.onclick = () => { pauseReplay(); showAnalysis(); };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const age = value => value < 1 ? '不足1分钟' : `${value.toFixed(1)}分钟前`;

  function closeIntro() {
    cancelAnimationFrame(animation); animation = 0; intro.hidden = true;
    stopSound();
    analysis.inert = false;
    document.getElementById('overviewPage').inert = false;
    document.getElementById('detailPage').inert = false;
  }
  function enter() {
    const target = pending;
    closeIntro();
    if (!target) return;
    selectVessel(target.mmsi, target.pan);
    chosen = null; showAnalysis();
  }
  function exit() {
    closeIntro(); analysis.hidden = true; originalOverview();
    if (priorFocus?.isConnected) priorFocus.focus();
  }
  intro.querySelector('#encContinue').onclick = enter;
  intro.querySelector('#encExit').onclick = exit;
  intro.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); exit(); }
    if (event.key === 'Tab') {
      const first = intro.querySelector('#encSound'), last = intro.querySelector('#encContinue');
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  function stopSound() {
    soundNodes.forEach(node => { try { node.stop(); } catch (_) {} }); soundNodes = [];
    if (audio?.state === 'running') audio.suspend().catch(() => {});
  }
  function enableSound() {
    if (muted) return;
    try {
      audio ||= new (window.AudioContext || window.webkitAudioContext)();
      audio.resume().catch(() => { document.getElementById('encSound').textContent = '音效不可用'; });
    } catch (_) { document.getElementById('encSound').textContent = '音效不可用'; }
  }
  function sound(impact) {
    if (muted || !audio || audio.state !== 'running') return;
    const now = audio.currentTime, gain = audio.createGain();
    gain.connect(audio.destination);
    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(impact ? .17 : .045, now + .015);
    gain.gain.exponentialRampToValueAtTime(.001, now + (impact ? 1.05 : .38));
    if (impact) {
      const buffer = audio.createBuffer(1, audio.sampleRate * 1.15, audio.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i=0;i<data.length;i++) data[i] = (Math.random()*2-1)*Math.exp(-i/audio.sampleRate*3);
      const noise = audio.createBufferSource(), filter = audio.createBiquadFilter();
      filter.type = 'lowpass'; filter.frequency.value = 1500;
      noise.buffer = buffer; noise.connect(filter); filter.connect(gain); noise.start(); soundNodes.push(noise);
    }
    const tone = audio.createOscillator(); tone.type = impact ? 'sine' : 'triangle';
    tone.frequency.setValueAtTime(impact ? 130 : 360, now);
    tone.frequency.exponentialRampToValueAtTime(impact ? 35 : 230, now + .35);
    tone.connect(gain); tone.start(); tone.stop(now + (impact ? 1.1 : .4)); soundNodes.push(tone);
  }
  document.getElementById('encSound').onclick = () => {
    muted = !muted;
    document.getElementById('encSound').textContent = muted ? '音效：关' : '音效：开';
    document.getElementById('encSound').setAttribute('aria-pressed', String(muted));
    if (muted) stopSound(); else enableSound();
  };

  function showAnalysis() {
    closeIntro();
    document.getElementById('overviewPage').classList.add('hidden');
    document.getElementById('detailPage').classList.add('hidden');
    document.getElementById('alarmToast').classList.remove('show');
    analysis.hidden = false; renderNeighbors();
    document.getElementById('encAnalysisTitle').focus();
    window.scrollTo(0,0);
  }

  // Authored storyboard: positions are illustrative, never used by the AIS analysis.
  function ship(x, y, angle, color, type = 'cargo', scale = 1, alpha = 1) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(angle); ctx.scale(scale, scale); ctx.globalAlpha = alpha;
    ctx.fillStyle = '#315d6630'; ctx.beginPath(); ctx.ellipse(-9, 13, 72, 25, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fbffff'; ctx.strokeStyle = '#28494f'; ctx.lineWidth = 2.4;
    ctx.beginPath(); ctx.moveTo(70, 0); ctx.quadraticCurveTo(50, -27, 22, -28); ctx.lineTo(-58, -24); ctx.quadraticCurveTo(-69, 0, -58, 24); ctx.lineTo(22, 28); ctx.quadraticCurveTo(50, 27, 70, 0); ctx.fill(); ctx.stroke();
    ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(54,0); ctx.quadraticCurveTo(39,-18,17,-19); ctx.lineTo(-48,-17); ctx.lineTo(-50,17); ctx.lineTo(17,19); ctx.quadraticCurveTo(39,18,54,0); ctx.fill();
    ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#c7d7d8'; ctx.lineWidth = 1;
    ctx.fillRect(-52, -13, 18, 26); ctx.strokeRect(-52, -13, 18, 26);
    ctx.fillStyle = '#244851'; ctx.fillRect(-48, -8, 10, 5); ctx.fillRect(-48, 3, 10, 5);
    if (type === 'tanker') {
      ctx.fillStyle = '#ffe0a3';
      [-18, 0, 18].forEach(px => { ctx.beginPath(); ctx.arc(px, 0, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); });
      ctx.fillStyle = '#bc6f3c'; ctx.fillRect(31, -12, 6, 24);
    } else if (type === 'passenger') {
      ctx.fillStyle = '#dff2f5';
      for (let i = 0; i < 5; i++) ctx.fillRect(-20 + i * 12, -13, 7, 8);
      ctx.fillStyle = '#ffffffcc'; ctx.fillRect(-20, 4, 52, 9);
    } else if (type === 'tug') {
      ctx.fillStyle = '#f6c356'; ctx.fillRect(-18, -13, 26, 26);
      ctx.fillStyle = '#37626a'; ctx.beginPath(); ctx.arc(25, 0, 9, 0, Math.PI * 2); ctx.fill();
    } else {
      ['#f0bd59', '#6ab9b0', '#dfe8ed', '#e08362'].forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(-22 + i * 15, -14, 11, 12); ctx.fillRect(-22 + i * 15, 3, 11, 12); });
    }
    ctx.fillStyle = '#e7f2f3'; ctx.beginPath(); ctx.moveTo(54,0); ctx.lineTo(44,-7); ctx.lineTo(44,7); ctx.fill();
    ctx.restore();
  }
  function dock(x, y, width, height, accent) {
    ctx.fillStyle = '#9aa8a8'; ctx.fillRect(x, y, width, height);
    ctx.fillStyle = '#6f8383'; for (let i = 0; i < width; i += 28) ctx.fillRect(x + i, y + height, 10, 42);
    ctx.fillStyle = accent; ctx.fillRect(x + 12, y - 54, 58, 36); ctx.fillRect(x + 82, y - 54, 58, 36);
    ctx.strokeStyle = '#5d7477'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(x + 30, y - 4); ctx.lineTo(x + 30, y - 78); ctx.lineTo(x + 132, y - 78); ctx.stroke();
    ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x + 132, y - 78); ctx.lineTo(x + 106, y - 40); ctx.stroke();
  }
  function wake(x1, y1, x2, y2, alpha = .75) {
    ctx.strokeStyle = `rgba(247,255,255,${alpha})`; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.quadraticCurveTo((x1 + x2) / 2, y1 + 9, x2, y2); ctx.stroke();
  }
  function scene(progress) {
    const mobile = canvas.clientWidth < 600;
    canvas.width = mobile ? 600 : 1120; canvas.height = mobile ? 600 : 490;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h); ctx.fillStyle = '#bedfe5'; ctx.fillRect(0, 0, w, h);
    const grd = ctx.createLinearGradient(0, 0, 0, h);
    grd.addColorStop(0, '#d8eef0'); grd.addColorStop(.4, '#c3e2e7'); grd.addColorStop(1, '#a9d5dc');
    ctx.fillStyle = grd; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#e7e7d8'; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(w, 0); ctx.lineTo(w, 82); ctx.quadraticCurveTo(w * .72, 112, w * .48, 84); ctx.quadraticCurveTo(w * .23, 53, 0, 107); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#d3dac9'; ctx.beginPath(); ctx.moveTo(0, h); ctx.lineTo(w * .24, h); ctx.lineTo(w * .18, h - 92); ctx.quadraticCurveTo(w * .10, h - 62, 0, h - 72); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = '#f8ffffaa'; ctx.lineWidth = 2;
    for (let y = 132; y < h; y += 50) for (let x = 22; x < w; x += 95) { ctx.beginPath(); ctx.moveTo(x,y); ctx.quadraticCurveTo(x+15,y+6,x+34,y); ctx.stroke(); }
    ctx.strokeStyle = '#58899b70'; ctx.lineWidth = 4; ctx.setLineDash([18, 16]);
    ctx.beginPath(); ctx.moveTo(w * .08, h * .72); ctx.quadraticCurveTo(w * .47, h * .47, w * .98, h * .38); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(w * .22, h * .98); ctx.quadraticCurveTo(w * .48, h * .66, w * .86, h * .57); ctx.stroke(); ctx.setLineDash([]);
    dock(22, 86, mobile ? 200 : 360, 20, '#7aa7a4');
    if (!mobile) { dock(w - 355, 82, 330, 18, '#d5a35b'); }
    ctx.fillStyle = '#365b6299'; ctx.font = mobile ? '15px sans-serif' : '17px sans-serif'; ctx.fillText('港口作业区', 28, 34);
    ctx.font = '12px sans-serif'; ctx.fillText('主航道', w * .55, h * .39);
    const traffic = [
      [w*.14 + progress*34, h*.35, 0, '#6f8da2', 'passenger', .45],
      [w*.82 - progress*52, h*.24, Math.PI, '#9ba5ad', 'tanker', .48],
      [w*.20 + progress*62, h*.76, -.2, '#5a8e72', 'tug', .36],
      [w*.70 - progress*44, h*.77, Math.PI*.98, '#667c95', 'cargo', .42],
      [w*.40 + progress*30, h*.30, .04, '#bd7d5c', 'cargo', .38],
    ];
    traffic.slice(0, mobile ? 3 : traffic.length).forEach(s => ship(...s, .82));
    const t = progress < .18 ? 0 : Math.min(1, ((progress-.18)/.34)**2), cx = w*.56, cy = h*.57;
    const hit = progress >= .55, after = Math.max(0, (progress-.55)*9);
    if (progress > .35) {
      ctx.fillStyle = '#d84b3f24'; ctx.beginPath(); ctx.arc(cx,cy,78 + Math.sin(progress * 24) * 4,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#c64638'; ctx.lineWidth = 3; ctx.setLineDash([7,6]); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#b7332e'; ctx.font = 'bold 13px sans-serif'; ctx.fillText('会遇警戒区', cx - 36, cy - 86);
    }
    const ax = cx - (mobile ? 235 : 430)*(1-t)-37, by = cy+(mobile ? 230 : 190)*(1-t)+33;
    ctx.save();
    if (hit && after < .55 && !matchMedia('(prefers-reduced-motion: reduce)').matches) ctx.translate(Math.sin(after*76)*6*(1-after/.55), Math.cos(after*62)*5);
    if (!hit) {
      for (let i=0;i<4;i++) {
        const drift = (progress*210+i*21)%90;
        wake(ax-59-drift, cy-26+i*13, ax-125-drift-t*96, cy-29+i*14, .72);
        wake(cx-10+i*12, by+58+drift, cx-15+i*14, by+107+drift+t*48, .68);
      }
    }
    ship(ax, cy-8, hit ? -.15 : 0, '#198777', 'cargo', .86);
    ship(cx+9, by, -Math.PI/2+(hit ? .16 : 0), '#d49b46', 'tanker', .9);
    if (hit) {
      ctx.globalAlpha = Math.max(0, 1-after/1.5);
      ctx.strokeStyle = '#edfaff'; ctx.lineWidth = 5;
      ctx.beginPath(); ctx.ellipse(cx,cy,36+after*130,20+after*80,0,0,Math.PI*2); ctx.stroke();
      ctx.strokeStyle = '#d7413488'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(cx, cy, 88 + after * 28, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;
      const flame = Math.max(0,1-after/1.6);
      for (let i=0;i<18;i++) {
        const a = i*2.399;
        ctx.fillStyle = i%3 ? '#ffbd33' : '#ea4e34';
        ctx.beginPath(); ctx.arc(cx+Math.cos(a)*31*flame,cy+Math.sin(a)*23*flame,(8+i%5)*flame,0,Math.PI*2); ctx.fill();
      }
      for (let i=0;i<34;i++) {
        const a=i*2.399, spread=30+after*(45+i%6*10);
        ctx.globalAlpha = Math.max(0,1-after/1.25); ctx.strokeStyle = i%2 ? '#fff1b0' : '#ef7b2d'; ctx.lineWidth=i%3?2:3;
        ctx.beginPath(); ctx.moveTo(cx+Math.cos(a)*spread,cy+Math.sin(a)*spread+after*after*15);
        ctx.lineTo(cx+Math.cos(a)*(spread+13),cy+Math.sin(a)*(spread+13)+after*after*15); ctx.stroke();
      }
      for (let i=0;i<10;i++) {
        ctx.globalAlpha = Math.min(.54,after*.5)*Math.max(.25,1-after/6);
        ctx.fillStyle = ['#52656d','#72848b','#9aa9ab'][i%3];
        ctx.beginPath(); ctx.arc(cx+(i-5)*11+after*8,cy-24-after*20-i*5,13+after*8+i%3*4,0,Math.PI*2); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
    ctx.font = '13px sans-serif'; ctx.fillStyle = '#4c6c70'; ctx.fillText('港区 / 情景示意',18,h-18);
  }
  function present() {
    closeIntro(); priorFocus = document.activeElement;
    intro.hidden = false;
    document.getElementById('overviewPage').inert = true;
    document.getElementById('detailPage').inert = true;
    analysis.inert = true;
    document.getElementById('alarmToast').classList.remove('show');
    intro.querySelector('#encContinue').focus();
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    enableSound();
    const start = performance.now(); let lastPhase = -1, horn = false, impact = false;
    function frame(now) {
      const p = reduced ? 1 : Math.min(1, (now - start) / 9000);
      scene(p);
      if (!reduced && p >= .35 && !horn) { horn=true; sound(false); }
      if (!reduced && p >= .55 && !impact) { impact=true; sound(true); }
      const phase = p < .35 ? 0 : p < .55 ? 1 : 2;
      if (phase !== lastPhase) {
        lastPhase = phase;
        document.getElementById('encPhase').textContent = ['01 / 繁忙港口','02 / 危险接近','03 / 碰撞警示'][phase];
        document.getElementById('encQuestion').textContent = ['港区交通密集，船舶正在交汇','速度越快，调整余地越小','如何提前识别危险会遇，让避碰更智能？'][phase];
        document.getElementById('encCaption').textContent = ['多艘船在港池、航道和码头之间穿行。','本情景中，两船保持原航向，未能及时错开。','后续将按邻船紧急程度排序，并为 CPA / TCPA 专业判断预留接口。'][phase];
        document.getElementById('encContinue').textContent = phase === 2 ? '进入会遇分析' : '跳过演示，进入分析';
      }
      if (p < 1) animation = requestAnimationFrame(frame);
    }
    animation = requestAnimationFrame(frame);
  }
  function renderNeighbors() {
    const time = currentTime();
    const result = EncounterMath.neighbors(DATA.vessels, selected.mmsi, time);
    const rows = EncounterMath.rank(result.rows, 5);
    chosen = rows.find(r => String(r.vessel.mmsi) === String(chosen?.vessel.mmsi)) || rows[0] || null;
    document.getElementById('encAnalysisTime').textContent = `${formatTime(time)} · 历史回放已暂停`;
    neighbors.innerHTML = `<div class="enc-side-title"><h2>紧急程度排序</h2><small>Top ${rows.length} / ${result.rows.length}</small></div><p class="enc-note">只展示最需要先看的目标；评分由距离、航向夹角、航速和数据新鲜度综合得到。</p>
      <div class="enc-target-list">${rows.map((r, i) => `<button class="enc-target enc-target-item ${r===chosen?'enc-picked':''} enc-${r.risk.tone}" data-target="${escape(r.vessel.mmsi)}"><em>${i + 1}</em><span>${escape(r.vessel.name || '未命名')}<small>${escape(r.vessel.mmsi)} · ${escape(r.vessel.category)} · ${r.distance.toFixed(2)}海里</small></span><strong>${r.risk.score}<small>分</small></strong></button>`).join('')}</div>
      ${rows.length ? '' : '<p class="enc-note">当前回放时刻没有可比较的有效邻船位置。</p>'}
      <div class="enc-score-guide"><span><i class="critical"></i>72-100 紧急</span><span><i class="warning"></i>48-71 重点</span><span><i class="watch"></i>28-47 一般</span></div>
      <div class="enc-footer"><button class="enc-action" id="encReplay">重看会遇演示</button></div>`;
    neighbors.querySelector('#encReplay').onclick = () => { pending = { mmsi: selected.mmsi, pan: false }; pauseReplay(); present(); };
    neighbors.querySelectorAll('[data-target]').forEach(button => button.onclick = () => {
      const r = rows.find(r => String(r.vessel.mmsi) === button.dataset.target);
      chosen = r;
      neighbors.querySelectorAll('[data-target]').forEach(b => b.classList.toggle('enc-picked', b === button));
      renderPrimary(result.point, r, time);
    });
    renderPrimary(result.point, chosen, time);
  }
  function renderPrimary(point, target, time) {
    const primary = document.getElementById('encPrimary');
    if (!point || !target) {
      primary.innerHTML = `<h1>船舶会遇分析</h1><p class="enc-note">${escape(selected.name)} · ${escape(selected.mmsi)}</p><div class="enc-empty">${!point ? '本船暂无有效位置' : '当前时刻暂无可比较的邻船'}<p>没有足够的位置记录，暂不生成船对分析。</p></div>`;
      return;
    }
    const other = target.point;
    const deltaLon = ((Number(other.lon)-Number(point.lon)+540)%360)-180;
    const dx = deltaLon*Math.cos((Number(point.lat)+Number(other.lat))/2*Math.PI/180);
    const dy = Number(other.lat)-Number(point.lat), extent = Math.max(Math.abs(dx),Math.abs(dy),.000001);
    const coincident = target.distance < .001;
    const x = coincident ? 65 : 50+dx/extent*27, y = coincident ? 50 : 50-dy/extent*25;
    const value = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? '缺失' : Number(v).toFixed(1);
    const risk = target.risk || EncounterMath.risk(target);
    primary.innerHTML = `<div class="enc-hero enc-${risk.tone}"><div><div class="enc-kicker">首要会遇对象 / 工程化预警排序</div><h1>${escape(selected.name || '本船')} <span>与</span> ${escape(target.vessel.name || '目标船')}</h1><p>${escape(risk.level)}：先看它，因为它在当前回放时刻的综合紧急程度最高。</p></div><strong>${risk.score}<small>/100</small></strong></div>
      <div class="enc-metrics"><div><span>最后报告位置距离</span><strong>${target.distance.toFixed(2)} <small>海里</small></strong></div><div><span>航向夹角</span><strong>${target.course.delta === null ? '暂不比较' : `${target.course.delta.toFixed(1)}°`}</strong></div><div><span>目标数据新鲜度</span><strong>${age(target.age)}</strong></div></div>
      <div class="enc-relative" aria-label="本船与目标船的相对方位示意"><span class="enc-north">N ↑</span><span class="enc-diagram-note">${coincident ? '报告位置重合 · 图标分开显示' : '方位示意 · 非等比例海图'}</span>
        <div class="enc-own-icon" style="left:${coincident?35:50}%;top:50%">${shipSvg(selected.category,'#178878',90,false)}<b>本船</b></div>
        <div class="enc-other-icon" style="left:${x}%;top:${y}%">${shipSvg(target.vessel.category,'#c38c37',90,false)}<b>目标船${target.distance<.001?'（位置重合）':''}</b></div></div>
      <div class="enc-reason"><h2>为什么优先关注</h2><ul><li>距离贡献：${Math.round(risk.parts.distanceScore * 100)} / 100，距离越近越需要先看。</li><li>航向贡献：${Math.round(risk.parts.crossingScore * 100)} / 100，夹角越接近交叉会遇，关注度越高。</li><li>航速贡献：${Math.round(risk.parts.speedScore * 100)} / 100，速度越快，留给人工判断的时间越少。</li><li>新鲜度贡献：${Math.round(risk.parts.freshnessScore * 100)} / 100，越新的 AIS 位置越可信。</li></ul></div>
      <p class="enc-note">距离来自不同时间的最后报告位置；图标不表示航向。当前排序是 Demo 预警筛选逻辑，不能替代正式 CPA / TCPA 或 COLREGs 避碰决策。</p>
      <div class="enc-identities"><div><i class="enc-dot own"></i>本船 · ${escape(selected.category)}<strong>${escape(selected.mmsi)}</strong><span>位置：${age(Math.max(0,(time-Date.parse(point.time))/60000))}</span></div><div><i class="enc-dot other"></i>目标 · ${escape(target.vessel.category)}<strong>${escape(target.vessel.mmsi)}</strong><span>位置：${age(target.age)}</span></div></div>
      <details class="enc-details"><summary>数据详情与分析边界</summary><dl><dt>本船航速 / COG</dt><dd>${value(point.sog)} 节 / ${value(point.cog)}°</dd><dt>目标航速 / COG</dt><dd>${value(other.sog)} 节 / ${value(other.cog)}°</dd><dt>本船位置时间</dt><dd>${escape(point.time)}</dd><dt>目标位置时间</dt><dd>${escape(other.time)}</dd><dt>航向比较</dt><dd>${escape(target.course.label)}</dd><dt>CPA / TCPA</dt><dd>本期未计算，不提供危险接近倒计时或避让指令。</dd></dl></details>`;
  }
  openVesselDetail = function (mmsi, pan) {
    if (!activeVessels().some(v => String(v.mmsi) === String(mmsi))) return;
    pauseReplay(); expanded = false; pending = { mmsi, pan };
    if (!seen) {
      seen = true; try { sessionStorage.setItem(key,'seen'); } catch (_) { /* Use the in-memory flag. */ }
      present();
    } else enter();
  };
  showOverviewPage = function () { closeIntro(); analysis.hidden = true; originalOverview(); };
  document.getElementById('backBtn').onclick = showOverviewPage;
  window.addEventListener('pagehide', closeIntro);
})();
