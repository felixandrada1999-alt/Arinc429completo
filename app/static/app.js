const instrumentSelect = document.querySelector('#instrument');
const valueInput = document.querySelector('#value');
const unitLabel = document.querySelector('#unit');
const rangeHint = document.querySelector('#range-hint');
const message = document.querySelector('#form-message');
const rows = document.querySelector('#shipment-list');
const emptyState = document.querySelector('#empty-state');
let instruments = [];
let editingId = null;

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Error HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function selectedInstrument() {
  return instruments.find((item) => item.id === Number(instrumentSelect.value));
}

function updateInstrumentHint() {
  const item = selectedInstrument();
  if (!item) return;
  unitLabel.textContent = item.unit;
  valueInput.min = item.min_value;
  valueInput.max = item.max_value;
  rangeHint.textContent = `Rango permitido: ${item.min_value} a ${item.max_value} ${item.unit}`;
}

function playShipmentAudio(value, instrument) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error('Este navegador no permite generar audio.');

  const audio = new AudioContextClass();
  const oscillator = audio.createOscillator();
  const gain = audio.createGain();
  const normalized = Math.min(1, Math.max(0, (value - instrument.min_value) / (instrument.max_value - instrument.min_value)));
  const now = audio.currentTime;
  oscillator.frequency.value = 440;
  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(normalized * 0.15, now + 0.03);
  gain.gain.setValueAtTime(normalized * 0.15, now + 0.35);
  gain.gain.linearRampToValueAtTime(0, now + 0.4);
  oscillator.connect(gain).connect(audio.destination);
  oscillator.start(now);
  oscillator.stop(now + 0.42);
  oscillator.onended = () => audio.close();
}

async function loadInstruments() {
  instruments = await request('/api/instruments');
  instrumentSelect.innerHTML = instruments.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join('');
  updateInstrumentHint();
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

async function loadShipments() {
  const shipments = await request('/api/shipments');
  rows.innerHTML = shipments.map((item) => `
    <tr>
      <td class="instrument-name">${escapeHtml(item.instrument_name)}</td>
      <td class="value-cell">${item.value}<span class="unit">${escapeHtml(item.unit)}</span></td>
      <td class="mono">${item.arinc_hex}</td>
      <td><span class="badge ${item.transmitted_at ? 'sent' : ''}">${item.transmitted_at ? 'Transmitido' : 'Registrado'}</span></td>
      <td><div class="row-actions"><button class="icon-button" data-action="transmit" data-id="${item.id}">Transmitir</button><button class="icon-button" data-action="edit" data-id="${item.id}">Editar</button><button class="icon-button danger" data-action="delete" data-id="${item.id}">Eliminar</button></div></td>
    </tr>`).join('');
  emptyState.hidden = shipments.length > 0;
  document.querySelector('#count').textContent = `${shipments.length} ${shipments.length === 1 ? 'envío' : 'envíos'}`;
}

instrumentSelect.addEventListener('change', updateInstrumentHint);
document.querySelector('#shipment-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  message.textContent = '';
  const payload = { instrument_id: Number(instrumentSelect.value), value: Number(valueInput.value) };
  try {
    await request(editingId ? `/api/shipments/${editingId}` : '/api/shipments', {
      method: editingId ? 'PUT' : 'POST', body: JSON.stringify(payload),
    });
    if (!editingId) {
      try {
        playShipmentAudio(payload.value, selectedInstrument());
        message.textContent = 'Envío creado. El nivel relativo de audio representa el valor seleccionado.';
      } catch (audioError) {
        message.textContent = `Envío creado; no se pudo reproducir el audio: ${audioError.message}`;
      }
    }
    editingId = null;
    document.querySelector('#shipment-form button[type="submit"]').innerHTML = 'Crear envío <span aria-hidden="true">↗</span>';
    valueInput.value = '';
    await loadShipments();
  } catch (error) { message.textContent = error.message; }
});

rows.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const id = Number(button.dataset.id);
  try {
    if (button.dataset.action === 'delete') {
      if (!confirm('¿Eliminar este envío?')) return;
      await request(`/api/shipments/${id}`, { method: 'DELETE' });
      await loadShipments();
    } else if (button.dataset.action === 'transmit') {
      await request(`/api/shipments/${id}/transmit`, { method: 'POST' });
      message.textContent = 'Palabra ARINC enviada al puerto serial configurado.';
      await loadShipments();
    } else {
      const shipment = (await request('/api/shipments')).find((item) => item.id === id);
      if (!shipment) return;
      editingId = id;
      instrumentSelect.value = shipment.instrument_id;
      valueInput.value = shipment.value;
      updateInstrumentHint();
      document.querySelector('#shipment-form button[type="submit"]').innerHTML = 'Guardar cambios <span aria-hidden="true">↗</span>';
      document.querySelector('.composer').scrollIntoView({ behavior: 'smooth' });
    }
  } catch (error) { message.textContent = error.message; }
});

document.querySelector('#preview-audio').addEventListener('click', () => {
  message.textContent = '';
  try {
    playShipmentAudio(Number(valueInput.value), selectedInstrument());
  } catch (error) {
    message.textContent = error.message;
  }
});

Promise.all([loadInstruments(), loadShipments()]).catch((error) => { message.textContent = error.message; });
