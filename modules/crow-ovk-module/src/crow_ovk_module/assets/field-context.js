const requestedParams = new URLSearchParams(location.search);
const requestedProjectId = requestedParams.get('project_id') || '';
const requestedInspectionId = requestedParams.get('inspection_id') || '';
const originalRestoreLatest = restoreLatest;
const originalGenerateHandler = $('generate').onclick;

function fieldContextQuery() {
  const params = new URLSearchParams();
  const projectId = $('project').value || requestedProjectId;
  const inspectionId = $('inspection').value.trim() || requestedInspectionId;
  if (projectId) params.set('project_id', projectId);
  if (inspectionId) params.set('inspection_id', inspectionId);
  return params.toString();
}

function updateFieldContextLinks() {
  const query = fieldContextQuery();
  $('workbenchLink').href = '/ovk/besiktning' + (query ? '?' + query : '');
}

function applyExplicitContext() {
  if (requestedProjectId) {
    ensureProject(requestedProjectId);
    $('project').value = requestedProjectId;
    state.project_id = requestedProjectId;
  }
  if (requestedInspectionId) {
    $('inspection').value = requestedInspectionId;
    state.inspection_id = requestedInspectionId;
  }
  updateFieldContextLinks();
}

restoreLatest = async function (requested=null) {
  const restored = await originalRestoreLatest(requested);
  updateFieldContextLinks();
  return restored;
};

$('generate').onclick = async () => {
  if ($('start').disabled || !$('systemType').value) return;
  state.project_id = $('project').value;
  state.inspection_id = $('inspection').value.trim();
  state.inspector = $('inspector').value.trim();
  state.system_type = $('systemType').value;
  await originalGenerateHandler();
  updateFieldContextLinks();
};
$('project').addEventListener('change', updateFieldContextLinks);
$('inspection').addEventListener('input', updateFieldContextLinks);
updateFieldContextLinks();
