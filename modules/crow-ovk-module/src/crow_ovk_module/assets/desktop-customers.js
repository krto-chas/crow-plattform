// Kundregister: läser och sparar via /api/ovk/kunder. Kunden är den som
// besiktningen görs åt. All text sätts med textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const FIELDS = ['Namn', 'Kontaktperson', 'Telefon', 'Epost', 'Referens'];
  const ADDRESSES = { postadress: 'kundPost', faktureringsadress: 'kundFaktura' };
  let customers = null;
  let editing = null;
  let revision = 0;
  let onChange = null;

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
    for (const customer of customers) select.append(new Option(customer.namn, customer.kund_id));
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
    for (const customer of customers) {
      const row = body.insertRow();
      const name = row.insertCell();
      const title = document.createElement('strong');
      title.textContent = customer.namn;
      name.append(title);
      const contact = row.insertCell();
      contact.textContent = [customer.kontaktperson, customer.telefon, customer.epost].filter(Boolean).join(' · ') || '—';
      const count = row.insertCell();
      count.textContent = customer.antal_fastigheter === null ? '—' : String(customer.antal_fastigheter);
      const actions = row.insertCell();
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'button secondary';
      edit.textContent = 'Ändra';
      edit.addEventListener('click', () => openForm(customer));
      actions.append(edit);
    }
    $('kundTable').hidden = !customers.length;
    $('kundEmpty').hidden = Boolean(customers.length);
  }

  function openForm(customer) {
    editing = customer ? { id: customer.kund_id, revision: customer.revision } : { id: newId(), revision: 'new' };
    $('kundFormTitle').textContent = customer ? 'Ändra kund' : 'Ny kund';
    for (const field of FIELDS) $('kund' + field).value = customer ? customer[field.toLowerCase()] || '' : '';
    for (const [key, prefix] of Object.entries(ADDRESSES)) {
      const address = (customer && customer[key]) || {};
      $(prefix + 'Gata').value = address.gata || '';
      $(prefix + 'Postnr').value = address.postnr || '';
      $(prefix + 'Ort').value = address.ort || '';
    }
    $('kundForm').hidden = false;
    $('kundFormStatus').textContent = '';
    $('kundNamn').focus();
  }

  function closeForm() {
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
        note.textContent = 'Kunden har ändrats av någon annan sedan du öppnade den. Dina ändringar är inte sparade. Uppdatera listan och öppna kunden igen.';
        return;
      }
      if (response.status === 422) {
        note.textContent = 'Uppgifterna kunde inte sparas. Kontrollera namn och e-postadress.';
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      closeForm();
      status('Kunden ' + body.namn + ' är sparad.');
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
      customers = payload.kunder;
      renderList();
      fillSelect();
      if (!$('kundStatus').textContent || $('kundStatus').textContent.startsWith('Laddar')) {
        status(payload.fullstandig ? '' : 'Antal fastigheter per kund kan inte anges: ett projekt gick inte att läsa.', !payload.fullstandig);
      }
    } catch (error) {
      if (current !== revision) return;
      customers = null;
      $('kundTable').hidden = true;
      $('kundEmpty').hidden = true;
      status('Kunderna kunde inte hämtas. Kontrollera anslutningen och ladda om sidan.', true);
    }
  }

  function init(options) {
    onChange = options && options.onChange;
    $('kundNew').addEventListener('click', () => openForm(null));
    $('kundCancel').addEventListener('click', closeForm);
    $('kundForm').addEventListener('submit', save);
  }

  // loaded() avgör om fastighetsformuläret får skicka kundkopplingen: utan en
  // hämtad kundlista vet formuläret inte vad som är valt och ska inte ändra den.
  window.ovkCustomers = { init, load, choose, loaded: () => customers !== null };
})();
