(function () {
  const logic = window.UnifiedPortalLogic;
  const roleNames = { user: '航行助手', admin: '海事业务台' };
  const frames = {
    user: document.getElementById('userFrame'),
    admin: document.getElementById('adminFrame')
  };
  const panes = Object.fromEntries(logic.ROLES.map(role => [role, document.querySelector(`[data-pane="${role}"]`)]));
  const buttons = Object.fromEntries(logic.ROLES.map(role => [role, document.querySelector(`[data-role="${role}"]`)]));
  const frameStates = Object.fromEntries(logic.ROLES.map(role => [role, document.querySelector(`[data-frame-state="${role}"]`)]));
  const loadStatuses = { user: 'loading', admin: 'loading' };
  const loadTimers = {};
  const currentRoleLabel = document.getElementById('currentRoleLabel');
  const loadStatus = document.getElementById('loadStatus');
  let currentRole = logic.normalizeRole(location.hash);

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons({ attrs: { 'stroke-width': 1.8 } });
  }

  function updateLoadSummary() {
    const summary = logic.loadSummary(loadStatuses);
    loadStatus.className = `load-status is-${summary.kind}`;
    loadStatus.innerHTML = `<span class="status-dot"></span>${summary.text}`;
  }

  function setFrameStatus(role, status) {
    loadStatuses[role] = status;
    frameStates[role].className = `frame-state is-${status}`;
    updateLoadSummary();
  }

  function frameLooksValid(role) {
    try {
      const frameDocument = frames[role].contentDocument;
      if (!frameDocument || !frameDocument.body) return false;
      return frameDocument.title.includes(frames[role].dataset.expectedTitle);
    } catch (_error) {
      return false;
    }
  }

  function handleFrameLoad(role) {
    clearTimeout(loadTimers[role]);
    setFrameStatus(role, frameLooksValid(role) ? 'ready' : 'error');
    if (role === currentRole) requestFrameResize(role);
  }

  function armLoadTimeout(role) {
    clearTimeout(loadTimers[role]);
    loadTimers[role] = setTimeout(() => {
      if (loadStatuses[role] === 'loading') setFrameStatus(role, 'error');
    }, 20000);
  }

  function requestFrameResize(role) {
    const target = frames[role].contentWindow;
    if (!target) return;
    setTimeout(() => target.dispatchEvent(new Event('resize')), 40);
    setTimeout(() => target.dispatchEvent(new Event('resize')), 240);
  }

  function setRole(role, options = {}) {
    currentRole = logic.normalizeRole(role);
    logic.ROLES.forEach(item => {
      const active = item === currentRole;
      panes[item].classList.toggle('is-active', active);
      panes[item].setAttribute('aria-hidden', String(!active));
      buttons[item].classList.toggle('is-active', active);
      buttons[item].setAttribute('aria-selected', String(active));
      buttons[item].tabIndex = active ? 0 : -1;
    });
    currentRoleLabel.textContent = `当前：${roleNames[currentRole]}`;
    document.title = `海上异常监测智能体 · ${roleNames[currentRole]}`;
    if (options.updateHash !== false && location.hash !== logic.hashForRole(currentRole)) {
      history.replaceState(null, '', logic.hashForRole(currentRole));
    }
    requestFrameResize(currentRole);
  }

  function reloadRole(role) {
    setFrameStatus(role, 'loading');
    armLoadTimeout(role);
    frames[role].contentWindow.location.reload();
  }

  logic.ROLES.forEach(role => {
    buttons[role].addEventListener('click', () => setRole(role));
    frames[role].addEventListener('load', () => handleFrameLoad(role));
    frames[role].addEventListener('error', () => setFrameStatus(role, 'error'));
    document.querySelector(`[data-retry="${role}"]`).addEventListener('click', () => reloadRole(role));
    armLoadTimeout(role);
  });

  document.querySelector('.role-switch').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const nextRole = currentRole === 'user' ? 'admin' : 'user';
    setRole(nextRole);
    buttons[nextRole].focus();
  });

  window.addEventListener('hashchange', () => setRole(location.hash, { updateHash: false }));
  window.addEventListener('load', refreshIcons);

  window.UnifiedPortal = {
    setRole,
    reloadRole,
    getCurrentRole: () => currentRole,
    getLoadStatuses: () => ({ ...loadStatuses })
  };

  setRole(currentRole);
  refreshIcons();
})();
