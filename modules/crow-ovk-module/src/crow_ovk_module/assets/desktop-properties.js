// Fastighetsregister: läser GET /api/ovk/fastigheter och visar organisationens
// fastigheter över alla projekt. All text sätts med textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  let data = null;
  let revision = 0;
  let onOpen = null;

  function matches(item, search) {
    if (!search) return true;
    return [item.fastighetsbeteckning, item.gata, item.ort, item.byggnadsagare, item.kund && item.kund.namn]
      .concat(item.byggnader.map(byggnad => byggnad.namn))
      .some(value => String(value || '').toLocaleLowerCase('sv').includes(search));
  }

  function cell(row, primary, secondary) {
    const td = row.insertCell();
    if (!primary && !secondary) { td.textContent = '—'; return td; }
    if (primary) {
      const main = document.createElement('span');
      main.textContent = primary;
      td.append(main);
    }
    if (secondary) {
      if (primary) td.append(document.createElement('br'));
      const sub = document.createElement('span');
      sub.className = 'muted';
      sub.textContent = secondary;
      td.append(sub);
    }
    return td;
  }

  function hint(td, text) {
    const note = document.createElement('span');
    note.className = 'muted register-hint';
    note.textContent = text;
    td.append(note);
  }

  function renderRows() {
    const search = $('registerSearch').value.trim().toLocaleLowerCase('sv');
    const rows = data.fastigheter.filter(item => matches(item, search));
    const body = $('registerItems');
    body.replaceChildren();
    for (const item of rows) {
      const row = body.insertRow();
      const name = row.insertCell();
      const title = document.createElement('strong');
      title.textContent = item.fastighetsbeteckning;
      name.append(title);
      const address = [item.gata, [item.postnr, item.ort].filter(Boolean).join(' ')].filter(Boolean).join(', ');
      if (address) {
        const line = document.createElement('span');
        line.className = 'muted';
        line.textContent = address;
        name.append(document.createElement('br'), line);
      }
      if (item.forekomster > 1) {
        const note = document.createElement('span');
        note.className = 'muted register-hint';
        note.textContent = 'Finns ' + item.forekomster + ' gånger i registret med samma beteckning och ort.';
        name.append(note);
      }
      cell(row, item.kund ? item.kund.namn || 'Okänd kund' : null);
      cell(row, item.byggnadsagare);
      cell(row, item.byggnader.length ? String(item.byggnader.length) : null,
        item.byggnader.map(byggnad => byggnad.namn).filter(Boolean).join(', '));
      const issued = cell(row, item.senast_utfardat, item.antal_besiktningar
        ? item.antal_besiktningar + (item.antal_besiktningar === 1 ? ' besiktning' : ' besiktningar')
        : 'Ingen besiktning');
      if (item.intyg_oklart) hint(issued, 'Intygets ställning går inte att fastställa.');
      const next = cell(row, item.nasta_besiktning);
      // En frist för en byggnad får inte se ut att gälla hela fastigheten.
      if (item.senast_utfardat && item.byggnader_utan_frist) {
        hint(next, item.byggnader_utan_frist === 1
          ? '1 byggnad saknar gällande frist.'
          : item.byggnader_utan_frist + ' byggnader saknar gällande frist.');
      }
      const actions = row.insertCell();
      actions.className = 'register-actions';
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'button secondary';
      open.textContent = 'Öppna';
      open.addEventListener('click', () => { if (onOpen) onOpen(item.project_id, item.fastighet_id); });
      const start = document.createElement('a');
      start.className = 'button';
      start.textContent = 'Ny besiktning';
      start.href = '/ovk/besiktning?new=1&project_id=' + encodeURIComponent(item.project_id)
        + '&fastighet_id=' + encodeURIComponent(item.fastighet_id);
      actions.append(open, start);
    }
    $('registerTable').hidden = !rows.length;
    const empty = $('registerEmpty');
    empty.hidden = Boolean(rows.length);
    if (data.fastigheter.length) empty.textContent = 'Inga fastigheter matchar sökningen.';
    else if (data.fullstandig) empty.textContent = 'Inga fastigheter är registrerade ännu. Lägg upp den första nedan.';
    else empty.textContent = 'Inga fastigheter kunde läsas. Se varningen ovan.';
    $('registerStatus').textContent = rows.length === data.fastigheter.length
      ? 'Visar ' + rows.length + (rows.length === 1 ? ' fastighet.' : ' fastigheter.')
      : 'Visar ' + rows.length + ' av ' + data.fastigheter.length + ' fastigheter.';
  }

  function renderWarning() {
    const warning = $('registerWarning');
    warning.replaceChildren();
    warning.hidden = data.fullstandig;
    if (data.fullstandig) return;
    const lead = document.createElement('strong');
    lead.textContent = 'Registret är ofullständigt. ';
    const text = document.createElement('span');
    const reasons = {
      projekt: 'registren går inte att läsa',
      identitet: 'en post pekar på annan plats än där den ligger',
      intyg: 'ett intyg anger ett annat projekt',
    };
    text.textContent = 'Fastigheterna i följande projekt saknas i listan: '
      + data.ej_lasbara.map(entry => entry.project_id + ' (' + (reasons[entry.orsak] || 'okänt fel') + ')').join(', ') + '.';
    warning.append(lead, text);
  }

  async function load() {
    const current = ++revision;
    $('registerStatus').textContent = 'Laddar fastigheter…';
    $('registerWarning').hidden = true;
    try {
      const response = await fetch('/api/ovk/fastigheter', { cache: 'no-store' });
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      if (current !== revision) return;
      data = payload;
      renderWarning();
      renderRows();
    } catch (error) {
      if (current !== revision) return;
      data = null;
      $('registerItems').replaceChildren();
      $('registerTable').hidden = true;
      $('registerEmpty').hidden = true;
      $('registerStatus').textContent = 'Fastigheterna kunde inte hämtas. Kontrollera anslutningen och försök igen med Uppdatera.';
    }
  }

  function init(options) {
    onOpen = options && options.onOpen;
    $('registerSearch').addEventListener('input', () => { if (data) renderRows(); });
    $('registerRefresh').addEventListener('click', load);
  }

  window.ovkProperties = { init, load };
})();
