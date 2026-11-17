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
    fieldEndpoint('context', state.project_id, state.inspection_id),
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
    fieldEndpoint('sync', state.project_id, state.inspection_id),
    {
      method: 'PUT',
      headers: {'content-type': 'application/json', 'X-OVK-Base-Revision': state.last_sync || 'new'},
      body: JSON.stringify(payload())
    }
  );
  const data = await response.json();
  if (response.status === 409 && data.detail?.code === 'OVK_FIELD_REVISION_CONFLICT') throw new Error('Serverunderlaget har ändrats. Lokalt arbete bevaras; synk stoppad.');
  if (!response.ok) throw new Error(JSON.stringify(data));
  state.last_sync = data.snapshot_sha256;
  return data;
};

syncPendingMedia = async function () {
  let uploaded = 0;
  for (const photo of state.photos.filter(item => item.sync_status !== 'synced')) {
    const media = await dbGet(MEDIA_STORE, mediaKey(state.project_id, state.inspection_id, photo.photo_id));
    if (!media || !media.blob) throw new Error('Saknar lokal mediablob för ' + photo.photo_id);
    const response = await crowAuthenticatedFetch(
      fieldEndpoint('media', state.project_id, state.inspection_id) + '/' + encodeURIComponent(photo.photo_id),
      {
        method: 'PUT',
        headers: {'content-type': photo.mime_type, 'X-OVK-Base-Revision': state.last_sync},
        body: media.blob
      }
    );
    const receipt = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(receipt));
    photo.sync_status = 'synced';
    state.last_sync = receipt.snapshot_sha256;
    media.media_id = receipt.media_id;
    media.evidence_id = receipt.evidence_id;
    media.synced_at = now();
    await dbPut(MEDIA_STORE, media);
    uploaded += 1;
  }
  return uploaded;
};

// A single in-flight sync per tab. Never clear dirty if edits arrived mid-flight.
const crowPersistOriginal = persist;
let crowEditVersion = 0;
let crowSyncInFlight = null;
let crowAutoTimer = null;
let crowSyncBlocked = false;
let crowSyncIdentity = null;
const CROW_AUTO_DELAY_MS = 8000;
const CROW_AUTO_INTERVAL_MS = 60000;

function crowSyncLabel(message, kind = '') {
  const status = $('syncStatus');
  status.className = 'status' + (kind ? ' ' + kind : '');
  status.textContent = message;
  const indicator = $('fieldSyncIndicator');
  if (indicator) {
    indicator.textContent = message;
    indicator.className = 'field-sync-indicator' + (kind ? ' ' + kind : '');
  }
}
function crowQueueAutoSync(delay = CROW_AUTO_DELAY_MS) {
  clearTimeout(crowAutoTimer);
  if (!state.dirty || !state.inspection_id || !state.project_id || crowSyncBlocked || !navigator.onLine) return;
  crowAutoTimer = setTimeout(() => { void syncDraft(); }, delay);
}
persist = async function () {
  // Increment before awaiting IndexedDB so an in-flight sync cannot clear new edits.
  crowEditVersion += 1;
  crowSyncBlocked = false;
  clearTimeout(crowAutoTimer);
  await crowPersistOriginal();
  crowSyncLabel('Sparad lokalt · väntar på synk');
  crowQueueAutoSync();
};

syncDraft = async function () {
  if (crowSyncInFlight) return crowSyncInFlight;
  if (!state.inspection_id || !state.project_id) {
    crowSyncLabel('Starta en rondering först.');
    return;
  }
  if (!navigator.onLine) {
    crowSyncLabel('Offline · sparad lokalt', 'warn');
    return;
  }
  const identity = state.project_id + '/' + state.inspection_id;
  if (crowSyncIdentity && crowSyncIdentity !== identity) crowSyncBlocked = false;
  crowSyncIdentity = identity;
  const version = crowEditVersion;
  const sync = async () => {
    try {
      crowSyncLabel('Synkroniserar…');
      await crowRequireSession();
      const current = await crowAuthenticatedFetch(fieldEndpoint('sync', state.project_id, state.inspection_id));
      if (current.ok) {
        const remote = await current.json();
        if (remote.snapshot_sha256 !== state.last_sync) {
          throw new Error('Serverunderlaget har ändrats på en annan enhet. Lokalt arbete bevaras; synk stoppad.');
        }
      } else if (current.status !== 404 || state.last_sync) {
        throw new Error('Serverrevisionen kunde inte verifieras. Synk stoppad.');
      }
      await syncContext();
      const summary = await syncSnapshot();
      const uploaded = await syncPendingMedia();
      if (uploaded) await syncSnapshot();
      if (state.project_id !== identity.split('/')[0] || state.inspection_id !== identity.split('/')[1]) {
        throw new Error('Aktiv besiktning ändrades under synk. Kontrollera uppdraget.');
      }
      // A newer local edit must remain dirty and be uploaded by a subsequent sync.
      const unchanged = crowEditVersion === version;
      await writeDraft(!unchanged);
      if (unchanged) {
        crowSyncLabel('Synkad · ' + state.last_sync.slice(0, 12) + '… · ' + uploaded +
          ' bilder · täckning ' + (summary.coverage_complete ? 'komplett' : 'ofullständig'), 'pass');
      } else {
        crowSyncLabel('Nya ändringar sparade lokalt · synkar igen');
      }
      crowSyncBlocked = false;
    } catch (error) {
      state.dirty = true;
      try { await writeDraft(true); } catch (_) { /* Do not hide the original sync error. */ }
      crowSyncBlocked = true; // No repeated requests on conflict or expired session.
      if (error instanceof CrowAuthenticationRequired) {
        crowSyncLabel('Sessionen har gått ut · sparad lokalt. Logga in och synka igen.', 'warn');
      } else {
        crowSyncLabel('Synk stoppad · sparad lokalt: ' + crowErrorText(error), 'warn');
      }
    }
  };
  crowSyncInFlight = sync().finally(() => {
    crowSyncInFlight = null;
    if (!crowSyncBlocked && state.dirty) crowQueueAutoSync(1000);
  });
  return crowSyncInFlight;
};

window.addEventListener('online', () => {
  if (state.dirty) {
    crowSyncBlocked = false;
    crowQueueAutoSync(1000);
  }
});
window.addEventListener('offline', () => {
  clearTimeout(crowAutoTimer);
  if (state.dirty) crowSyncLabel('Offline · sparad lokalt', 'warn');
});
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && state.dirty && navigator.onLine && !crowSyncBlocked) crowQueueAutoSync(1000);
});
setInterval(() => {
  if (state.dirty && !crowSyncBlocked) crowQueueAutoSync(1000);
}, CROW_AUTO_INTERVAL_MS);
// Restored drafts are loaded asynchronously during startup.
setTimeout(() => {
  if (state.dirty) {
    crowSyncLabel('Lokala ändringar väntar på synk');
    crowQueueAutoSync();
  }
}, 12000);

$('sync').onclick = syncDraft;
