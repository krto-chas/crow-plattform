(() => {
  const params = new URLSearchParams(window.location.search);
  const requestedProject = params.get('project_id');
  const requestedView = params.get('view');

  function currentProjectId() {
    return document.querySelector('.project-item.active')?.dataset.id || requestedProject || '';
  }

  function ventHref() {
    const projectId = currentProjectId();
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return `/vent${query}`;
  }

  function disableLegacyVent() {
    if (typeof window.renderVent === 'function') {
      window.renderVent = () => {};
    }
  }

  async function ventIsAvailable() {
    try {
      const response = await fetch('/api/me/modules');
      if (!response.ok) return false;
      const payload = await response.json();
      return (payload.modules || []).some(module => module.id === 'vent');
    } catch (error) {
      console.warn('Kunde inte läsa aktiva produktmoduler.', error);
      return false;
    }
  }

  function updateProductLinks() {
    const rail = document.getElementById('ventProductRail');
    const button = document.getElementById('openVentProduct');
    if (rail) rail.href = ventHref();
    if (button) button.href = ventHref();
  }

  function installVentProductLink() {
    disableLegacyVent();

    const oldRailButton = document.querySelector('[data-view="vent"]');
    if (oldRailButton) {
      const link = document.createElement('a');
      link.id = 'ventProductRail';
      link.className = oldRailButton.className;
      link.title = 'Ventilation';
      link.textContent = oldRailButton.textContent || 'V';
      link.href = ventHref();
      oldRailButton.replaceWith(link);
    }

    const workspaceHead = document.querySelector('.workspace-head');
    const upload = workspaceHead?.querySelector('.upload');
    if (workspaceHead && upload && !document.getElementById('openVentProduct')) {
      const link = document.createElement('a');
      link.id = 'openVentProduct';
      link.className = 'secondary';
      link.textContent = 'Öppna Vent';
      link.href = ventHref();
      link.style.textDecoration = 'none';
      link.style.marginLeft = 'auto';
      link.style.marginRight = '10px';
      workspaceHead.insertBefore(link, upload);
    }

    const projectList = document.getElementById('projectList');
    if (projectList) {
      new MutationObserver(updateProductLinks).observe(projectList, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
      });
    }
    updateProductLinks();
  }

  function removeLegacyVentButton() {
    disableLegacyVent();
    document.querySelector('[data-view="vent"]')?.remove();
  }

  async function openRequestedContext() {
    if (requestedProject && typeof window.openProject === 'function') {
      try {
        await window.openProject(requestedProject);
      } catch (error) {
        console.warn('Kunde inte öppna begärt Workbench-projekt.', error);
      }
    }
    if (requestedView && requestedView !== 'vent' && typeof window.switchView === 'function') {
      window.switchView(requestedView);
    }
  }

  window.addEventListener('load', async () => {
    if (await ventIsAvailable()) installVentProductLink();
    else removeLegacyVentButton();
    await openRequestedContext();
    updateProductLinks();
  }, {once: true});
})();
