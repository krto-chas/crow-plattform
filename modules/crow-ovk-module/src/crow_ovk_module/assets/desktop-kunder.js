// Kundregister: läser och sparar via /api/ovk/kunder. Kunden är den som
// besiktningen görs åt. All text sätts med textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const FIELDS = ['Namn', 'Organisationsnummer', 'Kontaktperson', 'Telefon', 'Epost', 'Referens'];
  const ADDRESSES = { postadress: 'kundPost', faktureringsadress: 'kundFaktura' };
  let kunder = null;
  let editing = null;
  let revision = 0;
  let openRevision = 0;
  let onChange = null;
  // Bekräftelsen från senaste sparning, visad tills nästa händelse i panelen.
  let saved = '';

  function newId() {
    const bytes = crypto.getRandomValues(new Uint8Array(12));
    return 'kund-' + Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  function status(text, warn) {
    const node = $('kundStatus');
    node.className = warn ? 'status warn' : 'muted';
    node.textContent = text;
  }

  function fillSelect() {
    const select = $('kund');
    const chosen = select.value;
    select.replaceChildren(new Option('— Ingen kund —', ''));
    for (const kund of kunder) select.append(new Option(kund.namn, kund.kund_id));
    choose(chosen);
  }

  // Väljer kund i fastighetsformuläret. En koppling till en kund som inte går
  // att läsa behålls som ett eget alternativ i stället för att tappas vid sparande.
  function choose(kundId) {
    const select = $('kund');
    for (const option of [...select.options]) if (option.dataset.unknown) option.remove();
    if (kundId && ![...select.options].some(option => option.value === kundId)) {
      const unknown = new Option('Okänd kund', kundId);
      unknown.dataset.unknown = '1';
      select.append(unknown);
    }
    select.value = kundId || '';
  }

  function renderList() {
    const body = $('kundItems');
    body.replaceChildren();
    for (const kund of kunder) {
      const row = body.insertRow();
      const name = row.insertCell();
      const title = document.createElement('strong');
      title.textContent = kund.namn;
      name.append(title);
      const contact = row.insertCell();
      contact.textContent = [kund.kontaktperson, kund.telefon, kund.epost].filter(Boolean).join(' · ') || '—';
      const count = row.insertCell();
      count.textContent = kund.antal_fastigheter === null ? '—' : String(kund.antal_fastigheter);
      const actions = row.insertCell();
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'button secondary';
      edit.textContent = 'Ändra';
      edit.addEventListener('click', () => openForm(kund));
      actions.append(edit);
    }
    $('kundTable').hidden = !kunder.length;
    $('kundEmpty').hidden = Boolean(kunder.length);
  }

  // Statusraden beskriver alltid det senast hämtade läget.
  function renderStatus(payload) {
    const notes = [];
    if (payload.ej_lasbara.length) {
      notes.push(payload.ej_lasbara.length === 1
        ? 'En kundpost går inte att läsa och saknas i listan (' + payload.ej_lasbara[0] + ').'
        : payload.ej_lasbara.length + ' kundposter går inte att läsa och saknas i listan (' + payload.ej_lasbara.join(', ') + ').');
    }
    if (!payload.antal_fastigheter_kant) notes.push('Antal fastigheter per kund kan inte anges: ett projekt gick inte att läsa.');
    status([saved].concat(notes).filter(Boolean).join(' '), notes.length > 0);
  }

  // Öppnar formuläret. En befintlig kund hämtas då i sin helhet: listan saknar
  // organisationsnumret, och revisionen ska vara den som gäller just nu.
  async function openForm(listed) {
    let kund = null;
    if (listed) {
      const ticket = ++openRevision;
      try {
        const response = await fetch('/api/ovk/kunder/' + encodeURIComponent(listed.kund_id), { cache: 'no-store' });
        if (!response.ok) throw new Error(String(response.status));
        kund = await response.json();
      } catch (error) {
        if (ticket === openRevision) status('Kunden kunde inte öppnas. Kontrollera anslutningen och försök igen.', true);
        return;
      }
      if (ticket !== openRevision) return;
    } else {
      openRevision += 1;
    }
    editing = kund ? { id: kund.kund_id, revision: kund.revision } : { id: newId(), revision: 'new' };
    $('kundFormTitle').textContent = kund ? 'Ändra kund' : 'Ny kund';
    for (const field of FIELDS) $('kund' + field).value = kund ? kund[field.toLowerCase()] || '' : '';
    for (const [key, prefix] of Object.entries(ADDRESSES)) {
      const address = (kund && kund[key]) || {};
      $(prefix + 'Gata').value = address.gata || '';
      $(prefix + 'Postnr').value = address.postnr || '';
      $(prefix + 'Ort').value = address.ort || '';
    }
    $('kundForm').hidden = false;
    $('kundFormStatus').textContent = '';
    $('kundNamn').focus();
  }

  function closeForm() {
    // En pågående hämtning ska inte öppna formuläret igen efter Avbryt.
    openRevision += 1;
    editing = null;
    $('kundForm').hidden = true;
  }

  function formPayload() {
    const payload = {};
    for (const field of FIELDS) payload[field.toLowerCase()] = $('kund' + field).value.trim();
    for (const [key, prefix] of Object.entries(ADDRESSES)) {
      payload[key] = {
        gata: $(prefix + 'Gata').value.trim(),
        postnr: $(prefix + 'Postnr').value.trim(),
        ort: $(prefix + 'Ort').value.trim(),
      };
    }
    return payload;
  }

  async function save(event) {
    event.preventDefault();
    if (!editing) return;
    const target = editing;
    const note = $('kundFormStatus');
    $('kundSave').disabled = true;
    note.textContent = 'Sparar…';
    try {
      const response = await fetch('/api/ovk/kunder/' + encodeURIComponent(target.id), {
        method: 'PUT',
        headers: { 'content-type': 'application/json', 'X-OVK-Base-Revision': target.revision },
        body: JSON.stringify(formPayload()),
      });
      const body = await response.json().catch(() => ({}));
      if (response.status === 409) {
        note.textContent = body.detail && body.detail.code === 'KUND_UNREADABLE'
          ? 'Den sparade kundposten går inte att läsa och kan inte ändras här.'
          : 'Kunden har ändrats av någon annan sedan du öppnade den. Dina ändringar är inte sparade. Stäng formuläret och öppna kunden igen.';
        // Listan hämtas om, så att kunden öppnas med aktuella uppgifter nästa gång.
        load();
        return;
      }
      if (response.status === 422) {
        note.textContent = String(body.detail && body.detail.message).includes('organisationsnummer')
          ? 'Organisationsnumret stämmer inte. Kontrollera siffrorna, eller lämna fältet tomt.'
          : 'Uppgifterna kunde inte sparas. Kontrollera namn och e-postadress.';
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      closeForm();
      saved = 'Kunden ' + body.namn + ' är sparad.';
      await load();
      if (onChange) onChange();
    } catch (error) {
      note.textContent = 'Kunden kunde inte sparas. Kontrollera anslutningen och försök igen.';
    } finally {
      $('kundSave').disabled = false;
    }
  }

  async function load() {
    const current = ++revision;
    try {
      const response = await fetch('/api/ovk/kunder', { cache: 'no-store' });
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      if (current !== revision) return;
      kunder = payload.kunder;
      renderList();
      fillSelect();
      renderStatus(payload);
    } catch (error) {
      if (current !== revision) return;
      // En tidigare hämtad lista står kvar: den är fortfarande det senast kända.
      if (kunder === null) {
        $('kundTable').hidden = true;
        $('kundEmpty').hidden = true;
      }
      status('Kunderna kunde inte hämtas. Kontrollera anslutningen och ladda om sidan.', true);
    }
  }

  function init(options) {
    onChange = options && options.onChange;
    $('kundNew').addEventListener('click', () => { saved = ''; openForm(null); });
    $('kundCancel').addEventListener('click', closeForm);
    $('kundForm').addEventListener('submit', save);
  }

  // loaded() avgör om fastighetsformuläret får skicka kundkopplingen: utan en
  // hämtad kundlista vet formuläret inte vad som är valt och ska inte ändra den.
  window.ovkKunder = { init, load, choose, loaded: () => kunder !== null };
})();
