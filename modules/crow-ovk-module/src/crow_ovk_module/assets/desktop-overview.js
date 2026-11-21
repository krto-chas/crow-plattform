// Översikt och arbetskö: läser GET /api/ovk/uppdrag och visar uppdragen med
// härledd status och nästa steg. All text sätts med textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  // Ordningen i arbetskön: det som kräver handling först.
  const ORDER = [
    'utfardande_avbrutet', 'att_granska', 'leveransklar', 'pagaende', 'planerad',
    'ej_planerad', 'atgarder_oppna', 'ombesiktning', 'utfardad',
  ];
  const ALWAYS_SHOWN = ['planerad', 'pagaende', 'att_granska', 'leveransklar'];
  // Arbetsytor som ännu är förvalda vyer av översikten.
  const VIEWS = {
    besiktningar: { text: 'Besiktningar och uppföljning', statuses: ['pagaende', 'atgarder_oppna'] },
    granskning: { text: 'Granskning', statuses: ['att_granska', 'leveransklar', 'utfardande_avbrutet'] },
  };
  const REASONS = {
    post: 'besiktningsposten går inte att läsa',
    identitet: 'posten pekar på ett annat uppdrag än platsen den ligger på',
    falt: 'fältunderlaget går inte att läsa',
    omigrerad: 'äldre fältunderlag är inte flyttat in i projektet',
    intyg: 'intygets ställning går inte att fastställa',
    projekt: 'projektets register går inte att läsa',
  };

  let data = null;
  let revision = 0;

  function selectedStatuses() {
    const value = $('overviewFilter').value;
    if (!value) return null;
    if (value.startsWith('vy:')) return new Set(VIEWS[value.slice(3)].statuses);
    return new Set([value]);
  }

  function matches(item, search) {
    if (!search) return true;
    return [item.fastighetsbeteckning, item.objekt, item.adress, item.byggnad, item.besiktningsman]
      .some(value => String(value || '').toLocaleLowerCase('sv').includes(search));
  }

  function cell(row, ...lines) {
    const td = row.insertCell();
    lines.filter(line => line && line.text).forEach((line, index) => {
      const part = document.createElement(index || line.plain ? 'span' : 'strong');
      if (index) part.className = 'muted';
      part.textContent = line.text;
      if (index) td.append(document.createElement('br'));
      td.append(part);
    });
    if (!td.childNodes.length) td.textContent = '—';
    return td;
  }

  function hints(item) {
    const notes = [];
    if (item.falt.synkad && !item.falt.avslutat && ['att_granska', 'leveransklar'].includes(item.status)) {
      notes.push('Fältarbetet är inte klarmarkerat i fältappen.');
    }
    if (item.oppna_granskningar) notes.push(item.oppna_granskningar + ' granskningsbeslut väntar.');
    return notes;
  }

  function renderQueue() {
    const queue = $('queue');
    queue.replaceChildren();
    const filter = $('overviewFilter');
    for (const status of ORDER) {
      const count = data.antal[status] || 0;
      if (!count && !ALWAYS_SHOWN.includes(status)) continue;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'card metric ovk-queue-card';
      button.dataset.status = status;
      button.setAttribute('aria-pressed', String(filter.value === status));
      const label = document.createElement('span');
      label.className = 'muted';
      label.textContent = data.statusar[status];
      const number = document.createElement('strong');
      number.textContent = String(count);
      button.append(label, number);
      queue.append(button);
    }
  }

  function renderRows() {
    const search = $('overviewSearch').value.trim().toLocaleLowerCase('sv');
    const statuses = selectedStatuses();
    const rows = data.uppdrag
      .filter(item => (!statuses || statuses.has(item.status)) && matches(item, search))
      .sort((a, b) =>
        ORDER.indexOf(a.status) - ORDER.indexOf(b.status)
        || String(a.planerat_datum || '9999').localeCompare(String(b.planerat_datum || '9999'))
        || String(a.fastighetsbeteckning || a.objekt).localeCompare(String(b.fastighetsbeteckning || b.objekt), 'sv'));
    const body = $('overviewItems');
    body.replaceChildren();
    for (const item of rows) {
      const row = body.insertRow();
      row.dataset.status = item.status;
      cell(row,
        { text: item.fastighetsbeteckning || item.objekt },
        { text: [item.adress, item.byggnad].filter(Boolean).join(' · ') });
      cell(row, { text: item.besiktningsman, plain: true });
      cell(row, { text: item.planerat_datum, plain: true });
      cell(row, { text: item.system.join(', '), plain: true });
      const status = row.insertCell();
      const pill = document.createElement('span');
      pill.className = 'pill ovk-status';
      pill.textContent = item.status_text;
      status.append(pill);
      for (const note of hints(item)) {
        const hint = document.createElement('span');
        hint.className = 'muted ovk-hint';
        hint.textContent = note;
        status.append(hint);
      }
      const next = row.insertCell();
      const link = document.createElement('a');
      link.className = 'button';
      link.href = item.nasta_steg.href;
      link.textContent = item.nasta_steg.text;
      next.append(link);
    }
    $('overviewTable').hidden = !rows.length;
    const empty = $('overviewEmpty');
    empty.hidden = Boolean(rows.length);
    empty.textContent = data.uppdrag.length
      ? 'Inga uppdrag matchar urvalet.'
      : 'Det finns inga uppdrag ännu. Börja med Ny OVK.';
    $('overviewStatus').textContent = rows.length === data.uppdrag.length
      ? 'Visar ' + rows.length + ' uppdrag.'
      : 'Visar ' + rows.length + ' av ' + data.uppdrag.length + ' uppdrag.';
  }

  function renderWarning() {
    const warning = $('overviewWarning');
    warning.replaceChildren();
    warning.hidden = data.fullstandig;
    if (data.fullstandig) return;
    const lead = document.createElement('strong');
    lead.textContent = 'Översikten är ofullständig. ';
    const text = document.createElement('span');
    text.textContent = data.ej_lasbara.length + ' uppdrag eller projekt kunde inte läsas och saknas i listan och i antalen:';
    const list = document.createElement('ul');
    for (const entry of data.ej_lasbara) {
      const line = document.createElement('li');
      const target = entry.inspection_id ? 'Uppdrag i projekt ' + entry.project_id : 'Projekt ' + entry.project_id;
      line.textContent = target + ': ' + (REASONS[entry.orsak] || 'okänt fel') + '.';
      list.append(line);
    }
    warning.append(lead, text, list);
  }

  function render() {
    if (!data) return;
    renderWarning();
    renderQueue();
    renderRows();
  }

  function fillFilter() {
    const filter = $('overviewFilter');
    const chosen = filter.dataset.initial ?? filter.value;
    filter.replaceChildren(new Option('Alla statusar', ''));
    for (const [id, view] of Object.entries(VIEWS)) filter.append(new Option(view.text, 'vy:' + id));
    for (const status of ORDER) filter.append(new Option(data.statusar[status], status));
    filter.value = [...filter.options].some(option => option.value === chosen) ? chosen : '';
    delete filter.dataset.initial;
  }

  async function load() {
    const current = ++revision;
    $('overviewStatus').textContent = 'Laddar uppdrag…';
    $('overviewWarning').hidden = true;
    try {
      const response = await fetch('/api/ovk/uppdrag', { cache: 'no-store' });
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      if (current !== revision) return;
      data = payload;
      fillFilter();
      render();
    } catch (error) {
      if (current !== revision) return;
      data = null;
      $('queue').replaceChildren();
      $('overviewItems').replaceChildren();
      $('overviewTable').hidden = true;
      $('overviewEmpty').hidden = true;
      $('overviewStatus').textContent = 'Uppdragen kunde inte hämtas. Kontrollera anslutningen och försök igen med Uppdatera.';
    }
  }

  function init() {
    const view = new URLSearchParams(location.search).get('vy');
    if (VIEWS[view]) $('overviewFilter').dataset.initial = 'vy:' + view;
    $('overviewSearch').addEventListener('input', () => { if (data) renderRows(); });
    $('overviewFilter').addEventListener('change', render);
    $('refreshOverview').addEventListener('click', load);
    $('queue').addEventListener('click', event => {
      const button = event.target.closest('button[data-status]');
      if (!button) return;
      const filter = $('overviewFilter');
      filter.value = filter.value === button.dataset.status ? '' : button.dataset.status;
      render();
    });
  }

  window.ovkOverview = { init, load };
})();
