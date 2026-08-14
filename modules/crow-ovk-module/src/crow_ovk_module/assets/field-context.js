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

restoreLatest = async function () {
  if (!requestedProjectId && !requestedInspectionId) {
    await originalRestoreLatest();
    updateFieldContextLinks();
    return;
  }

  applyExplicitContext();
  if (requestedInspectionId) {
    const exact = await dbGet('drafts', requestedInspectionId);
    if (exact && (!requestedProjectId || exact.project_id === requestedProjectId)) {
      Object.assign(state, DEFAULT_STATE(), {
        project_id: exact.project_id || requestedProjectId || 'adhoc',
        inspection_id: exact.inspection_id || requestedInspectionId,
        inspector: exact.inspector || '',
        system_type: exact.system_type || 'F',
        previous_inspection_id: exact.previous_inspection_id || null,
        historical_findings: exact.historical_findings || [],
        units: exact.units || [],
        rooms: exact.rooms || [],
        findings: exact.findings || [],
        photos: exact.photos || [],
        measurements: exact.measurements || [],
        window_vents: exact.window_vents || [],
        technical_spaces: exact.technical_spaces || [],
        checkpoints: exact.checkpoints || [],
        dirty: Boolean(exact.dirty),
        last_sync: exact.last_sync || null,
        defects: state.defects,
        checklists: state.checklists
      });
      $('inspection').value = state.inspection_id;
      $('inspector').value = state.inspector;
      $('systemType').value = state.system_type;
      ensureProject(state.project_id);
      $('project').value = state.project_id;
      $('draftStatus').className = 'status pass';
      $('draftStatus').textContent = 'Återställd vald lokal session · ' + state.inspection_id;
      if (state.units.length) {
        renderRond();
        view('viewRond');
      }
    } else {
      $('draftStatus').textContent = 'Projekt och besiktnings-ID valda från OVK-arbetsytan. Ingen lokal session återställd.';
    }
  } else {
    $('draftStatus').textContent = 'Projekt valt från OVK-arbetsytan. Starta eller återställ en besiktning i detta projekt.';
  }
  await loadHistory();
  updateFieldContextLinks();
};

$('generate').onclick = async () => {
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
