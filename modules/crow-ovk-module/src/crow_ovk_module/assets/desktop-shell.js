// Gemensam vänsternavigation för OVK:s skrivbordsarbetsplats.
// Varje skrivbordssida har ett tomt <nav id="ovkNav"> och anropar ovkShell.mount().
(function () {
  'use strict';

  // De åtta arbetsytorna. En yta utan egen sida ännu är antingen en förvald
  // vy av översikten (vy) eller markerad som kommande (href saknas).
  const WORKSPACES = [
    { id: 'oversikt', text: 'Översikt och arbetskö', href: '/ovk' },
    { id: 'uppdrag', text: 'Uppdrag och planering', href: '/ovk/besiktning' },
    { id: 'fastigheter', text: 'Kunder och fastigheter', href: '/ovk/fastighet' },
    { id: 'besiktningar', text: 'Besiktningar och uppföljning', href: '/ovk?vy=besiktningar' },
    { id: 'granskning', text: 'Granskning', href: '/ovk?vy=granskning' },
    { id: 'dokument', text: 'Protokoll, intyg och bilagor', href: '/ovk/intyg' },
    { id: 'bevakning', text: 'Bevakning och ombesiktningar', href: '/ovk/bevakning' },
    { id: 'administration', text: 'Administration och inställningar', href: null },
  ];
  // Sidor som tar ett förvalt projekt i adressen.
  const PROJECT_AWARE = new Set(['uppdrag', 'bevakning']);

  function currentWorkspace() {
    const path = location.pathname.replace(/\/+$/, '') || '/';
    if (path === '/ovk') {
      const view = new URLSearchParams(location.search).get('vy');
      return WORKSPACES.some(item => item.id === view) ? view : 'oversikt';
    }
    const match = WORKSPACES.find(item => item.href && !item.href.includes('?') && item.href === path);
    return match ? match.id : null;
  }

  function mount(active) {
    const nav = document.getElementById('ovkNav');
    if (!nav) return;
    const current = active || currentWorkspace();
    nav.replaceChildren();
    for (const item of WORKSPACES) {
      if (!item.href) {
        const pending = document.createElement('span');
        pending.className = 'ovk-nav-pending';
        pending.setAttribute('aria-disabled', 'true');
        pending.textContent = item.text;
        const note = document.createElement('small');
        note.textContent = 'Kommer';
        pending.append(' ', note);
        nav.append(pending);
        continue;
      }
      const link = document.createElement('a');
      link.href = item.href;
      link.dataset.workspace = item.id;
      link.textContent = item.text;
      if (item.id === current) {
        link.className = 'active';
        link.setAttribute('aria-current', 'page');
      }
      nav.append(link);
    }
  }

  function setProject(projectId) {
    const nav = document.getElementById('ovkNav');
    if (!nav) return;
    for (const link of nav.querySelectorAll('a[data-workspace]')) {
      if (!PROJECT_AWARE.has(link.dataset.workspace)) continue;
      const item = WORKSPACES.find(entry => entry.id === link.dataset.workspace);
      link.href = projectId ? item.href + '?project_id=' + encodeURIComponent(projectId) : item.href;
    }
  }

  window.ovkShell = { mount, setProject, currentWorkspace, workspaces: WORKSPACES };
})();
