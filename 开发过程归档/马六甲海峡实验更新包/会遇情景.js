(() => {
  'use strict';
  const originalOverview = showOverviewPage;
  const key = 'malacca-encounter-intro-v2';
  let audio = null, muted = false, soundNodes = [], chosen = null;
  let seen = false, animation = 0, pending = null, priorFocus = null, expanded = false;
  try { seen = sessionStorage.getItem(key) === 'seen'; } catch (_) { /* Private/file browser contexts can disable storage. */ }
  const intro = document.createElement('section');
  intro.id = 'encounterIntro'; intro.hidden = true;
  intro.setAttribute('role', 'dialog'); intro.setAttribute('aria-modal', 'true'); intro.setAttribute('aria-labelledby', 'encTitle');
  intro.innerHTML = `<header class="enc-header"><div><strong id="encTitle">一次未能及时错开的会遇</strong><span class="enc-label">情景夸张演示，非当前船舶事故</span></div><div class="enc-controls"><button class="enc-action" id="encSound" aria-pressed="false" title="切换音效">音效：开</button><button class="enc-action" id="encExit">返回总览</button></div></header>
    <div class="enc-stage"><div class="enc-status"><span id="encPhase" role="status">01 / 港口交汇</span><span>港口情景 · 非真实预测</span></div>
    <canvas class="enc-canvas" width="1120" height="490" aria-label="两艘扁平风格船舶在港口接近并发生示意碰撞"></canvas>
    <div class="enc-question"><h2 id="encQuestion">繁忙港口里，一次近距离交汇</h2><p id="encCaption">两艘船正在驶向同一片水域。</p><button id="encContinue" class="enc-action primary">跳过演示，进入分析</button></div></div>`;
  document.body.append(intro);
  const canvas = intro.querySelector('canvas'), ctx = canvas.getContext('2d');
  const neighbors = document.createElement('section');
  neighbors.className = 'enc-neighbors'; neighbors.setAttribute('aria-label', '周边船舶');
  const analysis = document.createElement('section');
  analysis.id = 'encAnalysis'; analysis.hidden = true;
  analysis.innerHTML = `<header class="enc-header"><div><strong id="encAnalysisTitle" tabindex="-1">船舶会遇分析</strong><span class="enc-label" id="encAnalysisTime"></span></div><div class="enc-controls"><button class="enc-action" id="encReport">综合安全报告</button><button class="enc-action" id="encBack">返回总览</button></div></header><div class="enc-analysis-body"><main id="encPrimary"></main><aside id="encAside"></aside></div>`;
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
  function ship(x, y, angle, color, tanker = false, scale = 1) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(angle); ctx.scale(scale, scale);
    ctx.fillStyle = '#38616b33'; ctx.beginPath(); ctx.ellipse(-12, 8, 67, 24, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#f8fcfb'; ctx.strokeStyle = '#395963'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(62, 0); ctx.quadraticCurveTo(46, -24, 25, -24); ctx.lineTo(-55, -24); ctx.lineTo(-55, 24); ctx.lineTo(25, 24); ctx.quadraticCurveTo(46, 24, 62, 0); ctx.fill(); ctx.stroke();
    ctx.fillStyle = color; ctx.fillRect(-48, -19, 74, 38);
    ctx.fillStyle = '#fff'; ctx.fillRect(-43, -16, 17, 32); ctx.fillStyle = '#244851'; ctx.fillRect(-40, -10, 10, 20);
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = tanker ? '#f6dfb0' : ['#efbd62', '#a5d7cf', '#dce9ed'][i];
      if (tanker) { ctx.beginPath(); ctx.arc(-13 + i * 16, 0, 7, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.fillRect(-18 + i * 15, -15, 11, 13); ctx.fillRect(-18 + i * 15, 2, 11, 13); }
    }
    ctx.restore();
  }
  function scene(progress) {
    const mobile = canvas.clientWidth < 600;
    canvas.width = mobile ? 600 : 1120; canvas.height = mobile ? 600 : 490;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h); ctx.fillStyle = '#c9e6eb'; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#b0d5db'; ctx.lineWidth = 2;
    for (let y = 35; y < h; y += 45) for (let x = 25; x < w; x += 100) { ctx.beginPath(); ctx.moveTo(x,y); ctx.quadraticCurveTo(x+16,y+6,x+34,y); ctx.stroke(); }
    ctx.fillStyle = '#e3e9df'; ctx.fillRect(0,0,w,90); ctx.fillStyle = '#b8c9c6'; ctx.fillRect(0,80,w,14);
    for (let i = 0; i < (mobile ? 3 : 6); i++) {
      const x = 35 + i * 170; ctx.fillStyle = '#829c9c'; ctx.fillRect(x,90,55,65);
      ctx.fillStyle = ['#6e9c99','#ddaa65','#8194ae'][i%3]; ctx.fillRect(x,25,45,35); ctx.fillRect(x+50,25,45,35);
      ctx.strokeStyle = '#56767a'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x+25,80); ctx.lineTo(x+25,10); ctx.lineTo(x+100,10); ctx.stroke();
    }
    ctx.fillStyle = '#73999a'; ctx.fillRect(w-100,h-80,100,18); ctx.fillRect(w-100,h-80,18,80);
    ship(w*.18, 183, Math.PI, '#5e8297', false, .52); ship(w*.76, 180, 0, '#919eaa', true, .55);
    const t = progress < .20 ? 0 : Math.min(1, ((progress-.20)/.35)**2), cx = w*.56, cy = h*.57;
    const hit = progress >= .55, after = Math.max(0, (progress-.55)*9);
    if (progress > .35) {
      ctx.fillStyle = '#d85f5020'; ctx.beginPath(); ctx.arc(cx,cy,72,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#c65a4b'; ctx.setLineDash([5,5]); ctx.stroke(); ctx.setLineDash([]);
    }
    const ax = cx - (mobile ? 235 : 430)*(1-t)-37, by = cy+(mobile ? 230 : 190)*(1-t)+33;
    ctx.save();
    if (hit && after < .45 && !matchMedia('(prefers-reduced-motion: reduce)').matches) ctx.translate(Math.sin(after*65)*4*(1-after/.45), Math.cos(after*55)*3);
    if (!hit) {
      ctx.strokeStyle = '#f5ffffcc'; ctx.lineWidth = 3;
      for (let i=0;i<4;i++) {
        const drift = (progress*160+i*19)%80;
        ctx.beginPath(); ctx.moveTo(ax-56-drift,cy-24+i*10); ctx.lineTo(ax-110-drift-t*80,cy-27+i*12); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx-8+i*10,by+55+drift); ctx.lineTo(cx-12+i*12,by+95+drift+t*40); ctx.stroke();
      }
    }
    ship(ax, cy-8, hit ? -.10 : 0, '#198777', false, .85);
    ship(cx+9, by, -Math.PI/2+(hit ? .1 : 0), '#d49b46', true, .85);
    if (hit) {
      ctx.globalAlpha = Math.max(0, 1-after/1.5);
      ctx.strokeStyle = '#edfaff'; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.ellipse(cx,cy,35+after*110,20+after*65,0,0,Math.PI*2); ctx.stroke();
      ctx.globalAlpha = 1;
      const flame = Math.max(0,1-after/1.6);
      for (let i=0;i<12;i++) {
        const a = i*2.399;
        ctx.fillStyle = i%2 ? '#f7b83b' : '#e96732';
        ctx.beginPath(); ctx.arc(cx+Math.cos(a)*25*flame,cy+Math.sin(a)*19*flame,(9+i%4)*flame,0,Math.PI*2); ctx.fill();
      }
      for (let i=0;i<26;i++) {
        const a=i*2.399, spread=30+after*(45+i%6*10);
        ctx.globalAlpha = Math.max(0,1-after/1.25); ctx.strokeStyle = i%2 ? '#fff1b0' : '#ed9230'; ctx.lineWidth=2;
        ctx.beginPath(); ctx.moveTo(cx+Math.cos(a)*spread,cy+Math.sin(a)*spread+after*after*15);
        ctx.lineTo(cx+Math.cos(a)*(spread+9),cy+Math.sin(a)*(spread+9)+after*after*15); ctx.stroke();
      }
      for (let i=0;i<7;i++) {
        ctx.globalAlpha = Math.min(.48,after*.5)*Math.max(.25,1-after/6);
        ctx.fillStyle = ['#52656d','#72848b','#9aa9ab'][i%3];
        ctx.beginPath(); ctx.arc(cx+(i-3)*10+after*8,cy-20-after*19-i*5,12+after*7+i%3*4,0,Math.PI*2); ctx.fill();
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
        document.getElementById('encPhase').textContent = ['01 / 港口交汇','02 / 未及时错开','03 / 示意碰撞'][phase];
        document.getElementById('encQuestion').textContent = ['繁忙港口里，一次近距离交汇','速度越快，调整余地越小','如何提前识别危险会遇，让避碰更智能？'][phase];
        document.getElementById('encCaption').textContent = ['两艘船正在驶向同一片水域。','本情景中，两船保持原航向，未能及时错开。','从周边船舶的位置与航向开始观察。'][phase];
        document.getElementById('encContinue').textContent = phase === 2 ? '进入会遇分析' : '跳过演示，进入分析';
      }
      if (p < 1) animation = requestAnimationFrame(frame);
    }
    animation = requestAnimationFrame(frame);
  }
  function renderNeighbors() {
    const time = currentTime();
    const result = EncounterMath.neighbors(DATA.vessels, selected.mmsi, time);
    const rows = expanded ? result.rows : result.rows.slice(0,5);
    chosen = result.rows.find(r => String(r.vessel.mmsi) === String(chosen?.vessel.mmsi)) || result.rows[0] || null;
    document.getElementById('encAnalysisTime').textContent = `${formatTime(time)} · 历史回放已暂停`;
    neighbors.innerHTML = `<h2>周边目标 <small>${result.rows.length}</small></h2><p class="enc-note">按最后报告位置距离排序，不代表风险排序</p>
      <div class="enc-target-list">${rows.map(r => `<button class="enc-target enc-target-item ${r===chosen?'enc-picked':''}" data-target="${escape(r.vessel.mmsi)}"><span>${escape(r.vessel.name || '未命名')}<small>${escape(r.vessel.mmsi)} · ${escape(r.vessel.category)}</small></span><strong>${r.distance.toFixed(2)}<small>海里</small></strong></button>`).join('')}</div>
      ${rows.length ? '' : '<p class="enc-note">当前回放时刻没有可比较的有效邻船位置。</p>'}
      <div class="enc-footer"><button class="enc-action" id="encMore" ${result.rows.length <= 5 ? 'hidden' : ''}>${expanded ? '收起列表' : `全部 ${result.rows.length} 艘`}</button><button class="enc-action" id="encReplay">重看会遇演示</button></div>`;
    neighbors.querySelector('#encMore').onclick = () => { expanded = !expanded; renderNeighbors(); };
    neighbors.querySelector('#encReplay').onclick = () => { pending = { mmsi: selected.mmsi, pan: false }; pauseReplay(); present(); };
    neighbors.querySelectorAll('[data-target]').forEach(button => button.onclick = () => {
      const r = result.rows.find(r => String(r.vessel.mmsi) === button.dataset.target);
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
    primary.innerHTML = `<div class="enc-kicker">船对观察 / 非碰撞预报</div><h1>${escape(selected.name || '本船')} <span>与</span> ${escape(target.vessel.name || '目标船')}</h1>
      <div class="enc-metrics"><div><span>最后报告位置距离</span><strong>${target.distance.toFixed(2)} <small>海里</small></strong></div><div><span>航向夹角</span><strong>${target.course.delta === null ? '暂不比较' : `${target.course.delta.toFixed(1)}°`}</strong></div></div>
      <div class="enc-relative" aria-label="本船与目标船的相对方位示意"><span class="enc-north">N ↑</span><span class="enc-diagram-note">${coincident ? '报告位置重合 · 图标分开显示' : '方位示意 · 非等比例海图'}</span>
        <div class="enc-own-icon" style="left:${coincident?35:50}%;top:50%">${shipSvg(selected.category,'#178878',90,false)}<b>本船</b></div>
        <div class="enc-other-icon" style="left:${x}%;top:${y}%">${shipSvg(target.vessel.category,'#c38c37',90,false)}<b>目标船${target.distance<.001?'（位置重合）':''}</b></div></div>
      <p class="enc-note">距离来自不同时间的最后报告位置；图标不表示航向。航向夹角不能证明航线交叉或即将碰撞。</p>
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
