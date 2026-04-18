// convierte dias a texto legible
function days_to_human(days) {
  if (!days && days !== 0) return '—';
  if (days === 0) return 'Al nacer';
  if (days < 30) return days + ' día' + (days > 1 ? 's' : '');
  if (days < 365) {
    const m = Math.floor(days / 30);
    return m + ' mes' + (m > 1 ? 'es' : '');
  }
  const y = Math.floor(days / 365);
  const m = Math.floor((days % 365) / 30);
  return y + ' año' + (y > 1 ? 's' : '') + (m ? ' ' + m + ' mes' + (m > 1 ? 'es' : '') : '');
}

// notificaciones toast
const Toast = {
  show(msg, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    t.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, duration);
  }
};

// cierre de mensajes flash
document.addEventListener('click', e => {
  if (e.target.classList.contains('close-flash')) {
    e.target.closest('.flash-msg')?.remove();
  }
});

// autoremoción de mensajes flash
document.querySelectorAll('.flash-msg').forEach(el => {
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = '0.5s'; setTimeout(() => el.remove(), 500); }, 5000);
});

// filtro de búsqueda en tablas
function initTableSearch(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    table.querySelectorAll('tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

// tabs
function initTabs(containerSelector) {
  document.querySelectorAll(containerSelector || '.tabs').forEach(tabs => {
    tabs.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        tabs.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const panels = tabs.closest('.card-body, .tab-wrapper, [data-tabs-parent]') || document;
        document.querySelectorAll('.tab-panel').forEach(p => {
          p.classList.toggle('active', p.id === target);
        });
      });
    });
  });
}

// modals
function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }
function closeAllModals() { document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open')); }

document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) closeAllModals();
  if (e.target.dataset.openModal) openModal(e.target.dataset.openModal);
  if (e.target.dataset.closeModal) closeModal(e.target.dataset.closeModal);
});

// confirmar eliminación (para prevenir eliminaciones accidentales)
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm || '¿Estás seguro?')) e.preventDefault();
  });
});

// lista dinamica de dosis
function addDoseToList(containerId, doseData) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const item = document.createElement('div');
  item.className = 'dose-item';
  item.innerHTML = `
    <span class="badge badge-primary">${doseData.tipo}</span>
    <span>${doseData.label}</span>
    <button type="button" class="remove-dose" onclick="this.closest('.dose-item').remove()">✕</button>
    <input type="hidden" name="dosis_ids" value="${doseData.id}">
  `;
  container.appendChild(item);
}

// fortaleza de contraseña
function initPasswordStrength(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const fill  = document.querySelector('.pwd-strength-fill');
  const label = document.querySelector('.pwd-strength-label');
  if (!fill || !label) return;

  const levels = [
    { min: 0,  pct: '10%', color: '#DC2626', text: 'Muy débil' },
    { min: 1,  pct: '30%', color: '#EA580C', text: 'Débil' },
    { min: 3,  pct: '55%', color: '#D97706', text: 'Regular' },
    { min: 5,  pct: '78%', color: '#16A34A', text: 'Fuerte' },
    { min: 7,  pct: '100%',color: '#166534', text: 'Muy fuerte' },
  ];

  input.addEventListener('input', () => {
    const v = input.value;
    let score = 0;
    if (v.length >= 8) score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v)) score++;
    if (/[a-z]/.test(v)) score++;
    if (/\d/.test(v)) score++;
    if (/[!@#$%^&*]/.test(v)) score++;
    if (v.length >= 16) score++;

    const level = [...levels].reverse().find(l => score >= l.min) || levels[0];
    fill.style.width = level.pct;
    fill.style.background = level.color;
    label.textContent = level.text;
  });
}

// simulador de scanner nfc
const NFC = {
  scanning: false,

  async scan(onResult, onError) {
    if (this.scanning) return;
    this.scanning = true;
    const ring = document.querySelector('.nfc-ring');
    const statusEl = document.getElementById('nfc-status');

    ring?.classList.add('scanning');
    if (statusEl) statusEl.textContent = 'Leyendo NFC…';

    // usar lector nfc web si es posible
    if ('NDEFReader' in window) {
      try {
        const reader = new NDEFReader();
        await reader.scan();
        reader.addEventListener('reading', ({ message }) => {
          const uid = message.records[0]?.data ? new TextDecoder().decode(message.records[0].data) : 'UNKNOWN';
          this._stopScan(ring, statusEl, 'Paciente encontrado');
          onResult(uid);
        });
        return;
      } catch (_) {  }
    }

    // fallback (2s delay)
    const uid = document.getElementById('sim-nfc-uid')?.value || 'NFC-SIM-001';
    setTimeout(() => {
      this._stopScan(ring, statusEl, 'Paciente encontrado');
      onResult(uid);
    }, 2000);
  },

  _stopScan(ring, statusEl, msg) {
    this.scanning = false;
    ring?.classList.remove('scanning');
    if (statusEl) statusEl.textContent = msg;
  }
};

// renderer de busqueda de paciente 
function renderPatientCard(data, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const p = data.paciente;
  container.innerHTML = `
    <div class="patient-card mb-20">
      <div class="pc-name">${p.nombre}</div>
      <div class="pc-meta">
        <span>📅 Nacimiento: <strong>${formatDate(p.fecha_nac)}</strong></span>
        <span>🎂 Edad: <strong>${p.edad_texto}</strong></span>
        <span>⚧ Sexo: <strong>${p.sexo === 'M' ? 'Masculino' : 'Femenino'}</strong></span>
        <span>🪪 CURP: <strong>${p.curp}</strong></span>
      </div>
    </div>
    <h4 class="mb-16 fw-600">Historial de Vacunación</h4>
    ${renderHistoryTable(data.historial, p.id)}
  `;

  // mostrar boton de registro
  const regBtn = document.getElementById('btn-register');
  if (regBtn) {
    regBtn.style.display = 'inline-flex';
    regBtn.onclick = () => {
      const url = new URL(regBtn.dataset.url, window.location.origin);
      url.searchParams.set('paciente_id', p.id);
      window.location.href = url.toString();
    };
  }
}

function renderHistoryTable(historial, pacienteId) {
  if (!historial?.length) return '<p class="text-muted text-center">No hay dosis en el esquema.</p>';

  const rows = historial.map(d => `
    <tr class="status-${d.status}">
      <td class="fw-600">${d.vacuna_nombre}</td>
      <td>${d.dosis_tipo}</td>
      <td>${d.edad_texto || '—'}</td>
      <td><span class="badge badge-${d.status}">${d.status_label}</span></td>
      <td>${d.aplicacion_timestamp ? formatDatetime(d.aplicacion_timestamp) : '—'}</td>
      <td>${d.responsable || '—'}</td>
      <td>${d.centro_nombre || '—'}</td>
      <td class="text-muted fs-sm">${d.aplicacion_observaciones || '—'}</td>
    </tr>
  `).join('');

  return `
    <div class="table-wrapper">
      <table class="table" id="history-table">
        <thead>
          <tr>
            <th>Vacuna</th><th>Dosis</th><th>Edad recomendada</th>
            <th>Estado</th><th>Fecha aplicación</th>
            <th>Responsable</th><th>Centro</th><th>Observaciones</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// historial de paciente AJAX
async function loadChildHistory(pacienteId) {
  const container = document.getElementById('history-container');
  if (!container) return;

  container.innerHTML = `<div class="text-center" style="padding:40px"><div class="spinner" style="border-color:rgba(124,58,237,.3);border-top-color:var(--primary);width:32px;height:32px"></div></div>`;

  try {
    const res  = await fetch(`/api/historial/${pacienteId}`);
    const data = await res.json();

    // Update chips
    document.querySelectorAll('.child-chip').forEach(c => {
      c.classList.toggle('active', c.dataset.id == pacienteId);
    });

    container.innerHTML = renderHistoryTable(data);
  } catch (err) {
    container.innerHTML = '<p class="text-muted text-center">Error cargando historial.</p>';
  }
}

// centros cercanos AJAX
async function searchCenters(vacunaId) {
  const container = document.getElementById('centers-list');
  if (!container) return;
  container.innerHTML = `<div class="text-center" style="padding:30px"><div class="spinner" style="border-color:rgba(37,99,235,.3);border-top-color:var(--secondary);width:28px;height:28px"></div><p class="mt-16 text-muted">Buscando centros…</p></div>`;

  try {
    const res     = await fetch(`/api/centros-cercanos?vacuna_id=${vacunaId}`);
    const centros = await res.json();
    if (!centros.length) {
      container.innerHTML = '<p class="text-muted text-center">No se encontraron centros con stock disponible.</p>';
      return;
    }
    container.innerHTML = centros.map(c => `
      <div class="card mb-12">
        <div class="card-body">
          <div class="d-flex align-center gap-16" style="justify-content:space-between;flex-wrap:wrap">
            <div>
              <div class="fw-700">${c.centro_nombre}</div>
              <div class="text-muted fs-sm">${c.centro_calle} ${c.centro_numero}, ${c.ciudad_nombre}</div>
              <div class="text-muted fs-sm mt-4">🕐 ${c.centro_horario_inicio || '—'} – ${c.centro_horario_fin || '—'} | 📞 ${c.centro_telefono || '—'}</div>
            </div>
            <div class="text-center">
              <div class="fw-700" style="font-size:1.4rem;color:var(--success)">${c.stock_total}</div>
              <div class="text-muted fs-sm">dosis disponibles</div>
            </div>
          </div>
        </div>
      </div>
    `).join('');

    // actualizar marcadores de mapa
    if (window._leafletMap) {
      window._leafletMap.eachLayer(l => { if (l instanceof L.Marker) window._leafletMap.removeLayer(l); });
      centros.forEach(c => {
        if (c.centro_latitud && c.centro_longitud) {
          L.marker([c.centro_latitud, c.centro_longitud])
            .addTo(window._leafletMap)
            .bindPopup(`<strong>${c.centro_nombre}</strong><br>Stock: ${c.stock_total} dosis`);
        }
      });
    }
  } catch (_) {
    container.innerHTML = '<p class="text-muted text-center">Error al buscar centros.</p>';
  }
}

// mapa leaflet
function initMap(lat = 25.6866, lng = -100.3161, zoom = 12) {
  if (!document.getElementById('map')) return;
  if (!window.L) { console.warn('Leaflet not loaded'); return; }

  const map = L.map('map').setView([lat, lng], zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);
  window._leafletMap = map;

  // Try geolocalización
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      map.setView([pos.coords.latitude, pos.coords.longitude], 13);
    });
  }
}

// simulador beacon
function simulateBeacon(centerName, vaccines, waitCount) {
  const modal = document.getElementById('beacon-modal');
  if (!modal) return;

  document.getElementById('beacon-center-name').textContent = centerName;
  document.getElementById('beacon-wait-count').textContent = waitCount;

  const vaccineList = document.getElementById('beacon-vaccines');
  if (vaccineList) {
    vaccineList.innerHTML = vaccines.map(v =>
      `<div class="d-flex align-center gap-10 mb-8">
         <span class="badge badge-applicable">${v.nombre}</span>
         <span class="fs-sm text-muted">Stock: ${v.stock} dosis</span>
       </div>`
    ).join('');
  }
  openModal('beacon-modal');
}

// gráficos de reportes
async function loadReportCharts(params) {
  const url = `/admin/api/reporte-datos?${new URLSearchParams(params)}`;
  try {
    const res  = await fetch(url);
    const data = await res.json();
    renderBarChart('chart-por-mes', data.por_mes);
    renderPieChart('chart-top-vacunas', data.top_vacunas);
  } catch (_) {}
}

function renderBarChart(containerId, data) {
  if (!window.Highcharts || !data?.length) return;
  Highcharts.chart(containerId, {
    chart: { type: 'column', backgroundColor: 'transparent' },
    title: { text: 'Aplicaciones por mes', style: { fontFamily: 'Inter', fontSize: '14px', fontWeight: '600' } },
    xAxis: { categories: data.map(d => d.mes), crosshair: true },
    yAxis: { min: 0, title: { text: 'Aplicaciones' } },
    colors: ['#7C3AED'],
    series: [{ name: 'Aplicaciones', data: data.map(d => parseInt(d.total)) }],
    credits: { enabled: false }
  });
}

function renderPieChart(containerId, data) {
  if (!window.Highcharts || !data?.length) return;
  Highcharts.chart(containerId, {
    chart: { type: 'pie', backgroundColor: 'transparent' },
    title: { text: 'Top vacunas aplicadas', style: { fontFamily: 'Inter', fontSize: '14px', fontWeight: '600' } },
    series: [{
      name: 'Aplicaciones',
      colorByPoint: true,
      data: data.map(d => ({ name: d.vacuna_nombre, y: parseInt(d.total) }))
    }],
    colors: ['#7C3AED','#2563EB','#16A34A','#D97706','#EA580C','#DC2626','#8B5CF6','#60A5FA'],
    credits: { enabled: false }
  });
}

// dropdowns cascada (pais → estado → ciudad) 
function initCascadingDropdowns() {
  const paisSel   = document.getElementById('pais_sel');
  const estadoSel = document.getElementById('estado_sel');
  const ciudadSel = document.getElementById('ciudad_sel');

  if (!paisSel || !estadoSel) return;

  paisSel.addEventListener('change', async () => {
    estadoSel.innerHTML = '<option value="">— Selecciona estado —</option>';
    if (ciudadSel) ciudadSel.innerHTML = '<option value="">— Selecciona ciudad —</option>';
    if (!paisSel.value) return;
    const res     = await fetch(`/admin/api/estados/${paisSel.value}`);
    const estados = await res.json();
    estados.forEach(e => {
      estadoSel.insertAdjacentHTML('beforeend', `<option value="${e.estado_id}">${e.estado_nombre}</option>`);
    });
  });

  if (ciudadSel) {
    estadoSel.addEventListener('change', async () => {
      ciudadSel.innerHTML = '<option value="">— Selecciona ciudad —</option>';
      if (!estadoSel.value) return;
      const res     = await fetch(`/admin/api/ciudades/${estadoSel.value}`);
      const cities  = await res.json();
      cities.forEach(c => {
        ciudadSel.insertAdjacentHTML('beforeend', `<option value="${c.ciudad_id}">${c.ciudad_nombre}</option>`);
      });
    });
  }
}

// helpers de fechas
function formatDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function formatDatetime(str) {
  if (!str) return '—';
  const d = new Date(str);
  return d.toLocaleString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Init on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initCascadingDropdowns();
  initPasswordStrength('new_password');

  // Auto-init buesquedas de tablas
  document.querySelectorAll('[data-search-table]').forEach(input => {
    initTableSearch(input.id, input.dataset.searchTable);
  });

  // boton scan NFC
  document.getElementById('btn-scan-nfc')?.addEventListener('click', () => {
    const nfcUid = document.getElementById('nfc-uid-input')?.value?.trim();
    if (nfcUid) {
      // input manual de NFC (simulador)
      fetchPatientByNfc(nfcUid);
    } else {
      NFC.scan(
        uid => fetchPatientByNfc(uid),
        err => Toast.show('Error al leer NFC: ' + err, 'error')
      );
    }
  });

  // busqueda CURP
  document.getElementById('btn-search-curp')?.addEventListener('click', () => {
    const curp = document.getElementById('curp-input')?.value?.trim().toUpperCase();
    if (!curp) return Toast.show('Ingresa un CURP válido', 'error');
    fetchPatientByCurp(curp);
  });

  // busqueda Certificado de Nacimiento
  document.getElementById('btn-search-cert')?.addEventListener('click', () => {
    const cert = document.getElementById('cert-nac-input')?.value?.trim();
    if (!cert) return Toast.show('Ingresa un N° de Certificado de Nacimiento', 'error');
    fetchPatientByCertNac(cert);
  });
});

async function fetchPatientByNfc(uid) {
  const res = await fetch('/clinico/api/nfc', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uid: uid })
  });
  if (res.ok) {
    const data = await res.json();
    renderPatientCard(data, 'patient-result');
  } else {
    Toast.show('Paciente no encontrado para este NFC', 'error');
  }
}

async function fetchPatientByCurp(curp) {
  const res = await fetch('/clinico/api/curp', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curp })
  });
  if (res.ok) {
    const data = await res.json();
    renderPatientCard(data, 'patient-result');
  } else {
    Toast.show('Paciente no encontrado con ese CURP', 'error');
  }
}

async function fetchPatientByCertNac(cert_nac) {
  const res = await fetch('/clinico/api/cert-nac', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cert_nac })
  });
  if (res.ok) {
    const data = await res.json();
    renderPatientCard(data, 'patient-result');
  } else {
    Toast.show('Paciente no encontrado con ese Certificado de Nacimiento', 'error');
  }
}
