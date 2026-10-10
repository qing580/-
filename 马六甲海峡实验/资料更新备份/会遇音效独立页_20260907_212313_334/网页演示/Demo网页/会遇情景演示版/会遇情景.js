(() => {
  'use strict';
  const originalOverview = showOverviewPage;
  const key = 'malacca-encounter-intro-v1';
  let seen = false, animation = 0, pending = null, priorFocus = null, expanded = false;
  try { seen = sessionStorage.getItem(key) === 'seen'; } catch (_) { /* Private/file browser contexts can disable storage. */ }
  const intro = document.createElement('section');
  intro.id = 'encounterIntro'; intro.hidden = true;
  intro.setAttribute('role', 'dialog'); intro.setAttribute('aria-modal', 'true'); intro.setAttribute('aria-labelledby', 'encTitle');
  intro.innerHTML = `<header class="enc-header"><div><strong id="encTitle">一次未能及时错开的会遇</strong><span class="enc-label">情景演示，非当前船舶事故</span></div><button class="enc-action" id="encExit">返回总览</button></header>
    <div class="enc-stage"><div class="enc-status"><span id="encPhase" role="status">01 / 港口交汇</span><span>港口情景 · 非真实预测</span></div>
    <canvas class="enc-canvas" width="1120" height="490" aria-label="两艘扁平风格船舶在港口接近并发生示意碰撞"></canvas>
    <div class="enc-question"><h2 id="encQuestion">繁忙港口里，一次近距离交汇</h2><p id="encCaption">两艘船正在驶向同一片水域。</p><button id="encContinue" class="enc-action primary">跳过演示，进入分析</button></div></div>`;
  document.body.append(intro);
  const canvas = intro.querySelector('canvas'), ctx = canvas.getContext('2d');
  const neighbors = document.createElement('section');
  neighbors.className = 'enc-neighbors'; neighbors.setAttribute('aria-label', '周边船舶');
  document.querySelector('.detail-main').prepend(neighbors);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const age = value => value < 1 ? '不足1分钟' : `${value.toFixed(1)}分钟前`;

  function closeIntro() {
    cancelAnimationFrame(animation); animation = 0; intro.hidden = true;
    document.getElementById('overviewPage').inert = false;
    document.getElementById('detailPage').inert = false;
  }
  function enter() {
    const target = pending;
    closeIntro();
    if (!target) return;
    selectVessel(target.mmsi, target.pan);
    showDetailPage(); renderNeighbors();
    const title = document.querySelector('.detail-title'); title.tabIndex = -1; title.focus();
  }
  function exit() {
    closeIntro(); originalOverview();
    if (priorFocus?.isConnected) priorFocus.focus();
  }
  intro.querySelector('#encContinue').onclick = enter;
  intro.querySelector('#encExit').onclick = exit;
  intro.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); exit(); }
    if (event.key === 'Tab') {
      const first = intro.querySelector('#encExit'), last = intro.querySelector('#encContinue');
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

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
    const t = Math.min(1, progress / .78), cx = w*.56, cy = h*.57;
    if (progress > .40) {
      ctx.fillStyle = '#d85f5020'; ctx.beginPath(); ctx.arc(cx,cy,72,0,Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#c65a4b'; ctx.setLineDash([5,5]); ctx.stroke(); ctx.setLineDash([]);
    }
    ship(cx - 245*(1-t)-37, cy-8, 0, '#198777', false, .85);
    ship(cx+9, cy+190*(1-t)+33, -Math.PI/2, '#d49b46', true, .85);
    if (progress >= .78) {
      ctx.strokeStyle = '#c24d43'; ctx.lineWidth = 3;
      for (let r of [35,52,69]) { ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke(); }
      ctx.fillStyle = '#a52c26'; ctx.font = 'bold 23px sans-serif'; ctx.fillText('!',cx-4,cy+8);
    }
    ctx.font = '13px sans-serif'; ctx.fillStyle = '#4c6c70'; ctx.fillText('港区 / 情景示意',18,h-18);
  }
  function present() {
    closeIntro(); priorFocus = document.activeElement;
    intro.hidden = false;
    document.getElementById('overviewPage').inert = true;
    document.getElementById('detailPage').inert = true;
    document.getElementById('alarmToast').classList.remove('show');
    intro.querySelector('#encContinue').focus();
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const start = performance.now(); let lastPhase = -1;
    function frame(now) {
      const p = reduced ? 1 : Math.min(1, (now - start) / 7200);
      scene(p);
      const phase = p < .4 ? 0 : p < .78 ? 1 : 2;
      if (phase !== lastPhase) {
        lastPhase = phase;
        document.getElementById('encPhase').textContent = ['01 / 港口交汇','02 / 未及时错开','03 / 示意碰撞'][phase];
        document.getElementById('encQuestion').textContent = ['繁忙港口里，一次近距离交汇','短距离交汇，留给调整的时间正在减少','如何提前识别危险会遇，让避碰更智能？'][phase];
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
    neighbors.innerHTML = `<h2>周边船舶 · 位置与航向观察</h2>
      <p class="enc-note">${escape(formatTime(time))} · 回放已暂停<br>最后报告位置距离，非同步实测距离。航向夹角不代表航线交叉或碰撞；本期未计算 CPA / TCPA。</p>
      <div class="enc-pair" id="encPair">本船 ${escape(selected.name)} · ${escape(selected.mmsi)}<br>${result.point ? `本船位置：${age(Math.max(0,(time-Date.parse(result.point.time))/60000))}` : '本船暂无有效位置'}</div>
      <div class="enc-table-wrap"><table class="enc-table"><thead><tr><th>目标船 / MMSI</th><th>距离 / 海里</th><th>位置记录</th><th>COG夹角</th></tr></thead><tbody>${rows.map(r => `<tr><td><button class="enc-target" data-target="${escape(r.vessel.mmsi)}">${escape(r.vessel.name || '未命名')}<small>${escape(r.vessel.mmsi)} · ${escape(r.vessel.category)}</small></button></td><td>${r.distance.toFixed(2)}</td><td>${age(r.age)}</td><td>${r.course.delta === null ? escape(r.course.label) : `${r.course.delta.toFixed(1)}°`}</td></tr>`).join('')}</tbody></table></div>
      ${rows.length ? '' : '<p class="enc-note">当前回放时刻没有可比较的有效邻船位置。</p>'}
      <div class="enc-footer"><button class="enc-action" id="encMore" ${result.rows.length <= 5 ? 'hidden' : ''}>${expanded ? '收起列表' : `全部 ${result.rows.length} 艘`}</button><button class="enc-action" id="encReplay">重看会遇演示</button></div>`;
    neighbors.querySelector('#encMore').onclick = () => { expanded = !expanded; renderNeighbors(); };
    neighbors.querySelector('#encReplay').onclick = () => { pending = { mmsi: selected.mmsi, pan: false }; pauseReplay(); present(); };
    neighbors.querySelectorAll('[data-target]').forEach(button => button.onclick = () => {
      const r = result.rows.find(r => String(r.vessel.mmsi) === button.dataset.target);
      neighbors.querySelectorAll('tr').forEach(tr => tr.classList.remove('enc-picked'));
      button.closest('tr').classList.add('enc-picked');
      document.getElementById('encPair').textContent = `本船 ${selected.name} (${selected.mmsi}) ↔ 目标 ${r.vessel.name || '未命名'} (${r.vessel.mmsi})；最后报告位置相距 ${r.distance.toFixed(2)} 海里。本船位置${age(Math.max(0,(time-Date.parse(result.point.time))/60000))}，目标位置${age(r.age)}。${r.course.label}${r.course.delta === null ? '' : `：${r.course.delta.toFixed(1)}°`}。`;
    });
  }
  openVesselDetail = function (mmsi, pan) {
    if (!activeVessels().some(v => String(v.mmsi) === String(mmsi))) return;
    pauseReplay(); expanded = false; pending = { mmsi, pan };
    if (!seen) {
      seen = true; try { sessionStorage.setItem(key,'seen'); } catch (_) { /* Use the in-memory flag. */ }
      present();
    } else enter();
  };
  showOverviewPage = function () { closeIntro(); originalOverview(); };
  document.getElementById('backBtn').onclick = showOverviewPage;
  window.addEventListener('pagehide', closeIntro);
})();
