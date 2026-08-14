class CrowAuthenticationRequired extends Error {
  constructor() {
    super('Authentication required');
    this.name = 'CrowAuthenticationRequired';
  }
}

async function crowAuthenticatedFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store'
  });
  if (response.status === 401) throw new CrowAuthenticationRequired();
  return response;
}

async function crowRequireSession() {
  const response = await crowAuthenticatedFetch('/api/auth/me');
  if (!response.ok) {
    const data = await response.json();
    throw new Error(JSON.stringify(data));
  }
}

syncContext = async function () {
  const response = await crowAuthenticatedFetch(
    '/api/ovk/field/context/' + encodeURIComponent(state.inspection_id),
    {
      method: 'PUT',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({
        project_id: state.project_id,
        inspector: state.inspector,
        previous_inspection_id: state.previous_inspection_id,
        system_type: state.system_type
      })
    }
  );
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data;
};

syncSnapshot = async function () {
  const response = await crowAuthenticatedFetch(
    '/api/ovk/field/sync/' + encodeURIComponent(state.inspection_id),
    {
      method: 'PUT',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(payload())
    }
  );
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  state.last_sync = data.snapshot_sha256;
  return data;
};

syncPendingMedia = async function () {
  let uploaded = 0;
  for (const photo of state.photos.filter(item => item.sync_status !== 'synced')) {
    const media = await dbGet('media', photo.photo_id);
    if (!media || !media.blob) throw new Error('Saknar lokal mediablob för ' + photo.photo_id);
    const response = await crowAuthenticatedFetch(
      '/api/ovk/field/media/' + encodeURIComponent(state.inspection_id) + '/' + encodeURIComponent(photo.photo_id),
      {
        method: 'PUT',
        headers: {'content-type': photo.mime_type},
        body: media.blob
      }
    );
    const receipt = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(receipt));
    photo.sync_status = 'synced';
    media.media_id = receipt.media_id;
    media.evidence_id = receipt.evidence_id;
    media.synced_at = now();
    await dbPut('media', media);
    uploaded += 1;
  }
  return uploaded;
};

syncDraft = async function () {
  if (!state.inspection_id) {
    $('syncStatus').textContent = 'Starta en rondering först.';
    return;
  }
  if (!navigator.onLine) {
    $('syncStatus').textContent = 'Offline · allt ligger kvar säkert lokalt.';
    return;
  }
  try {
    $('syncStatus').className = 'status';
    $('syncStatus').textContent = 'Kontrollerar session…';
    await crowRequireSession();
    $('syncStatus').textContent = 'Synkar kontext…';
    await syncContext();
    $('syncStatus').textContent = 'Synkar snapshot…';
    const summary = await syncSnapshot();
    const uploaded = await syncPendingMedia();
    if (uploaded) {
      $('syncStatus').textContent = 'Media verifierad · uppdaterar snapshot…';
      await syncSnapshot();
    }
    state.dirty = false;
    await writeDraft(false);
    $('syncStatus').className = 'status pass';
    $('syncStatus').textContent = 'Synkad · ' + state.last_sync.slice(0, 12) + '… · ' + uploaded +
      ' bilder · täckning ' + (summary.coverage_complete ? 'komplett' : 'ofullständig');
  } catch (error) {
    state.dirty = true;
    await writeDraft(true);
    $('syncStatus').className = 'status warn';
    if (error instanceof CrowAuthenticationRequired) {
      $('syncStatus').textContent =
        'Sessionen saknas eller har gått ut. Ronderingen är kvar lokalt. Logga in igen och återgå till Fältläge för att synka.';
      return;
    }
    $('syncStatus').textContent = 'Synkfel: ' + String(error);
  }
};

$('sync').onclick = syncDraft;
