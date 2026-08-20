(() => {
  const requestedProject = new URLSearchParams(window.location.search).get('project_id');

  function currentProjectId() {
    return document.querySelector('.project-item.active')?.dataset.id || requestedProject || '';
  }

  function ventHref(fragment = '') {
    const projectId = currentProjectId();
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return `/vent${query}${fragment}`;
  }

  function updateProductLinks() {
    const rail = document.getElementById('ventProductRail');
    const button = document.getElementById('openVentProduct');
    if (rail) rail.href = ventHref();
    if (button) button.href = ventHref();
  }

  function installVentProductLink() {
    if (typeof window.renderVent === 'function') {
      window.renderVent = () => {};
    }

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

  async function openRequestedProject() {
    if (!requestedProject || typeof window.openProject !== 'function') return;
    try {
      await window.openProject(requestedProject);
    } catch (error) {
      console.warn('Kunde inte öppna begärt Workbench-projekt.', error);
    }
  }

  window.addEventListener('load', async () => {
    installVentProductLink();
    await openRequestedProject();
    updateProductLinks();
  }, {once: true});
})();
