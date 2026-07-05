<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useBricsStore } from '../stores/brics';
import { Plus, FileText, Upload, RefreshCw, Layers } from '@lucide/vue';

const store = useBricsStore();

// Formulario de presupuesto
const projectName = ref('');
const projectType = ref('comercial');
const region = ref('Aguascalientes');

// Entrada BOM
const bomInput = ref('');

onMounted(() => {
  store.fetchBudgets();
});

const handleCreateBudget = async () => {
  if (!projectName.value) return;
  try {
    await store.createBudget(projectName.value, projectType.value, region.value);
    projectName.value = '';
  } catch (e) {
    console.error(e);
  }
};

const handleUploadBOM = async () => {
  if (!store.activeBudget || !bomInput.value.trim()) return;
  
  // Parsea las líneas crudas pegadas
  // Formato admitido: "Descripción del concepto | cantidad | unidad" o solo "Descripción del concepto"
  const rawLines = bomInput.value.split('\n').filter(l => l.trim() !== '');
  const linesPayload = rawLines.map(line => {
    const parts = line.split('|');
    const raw_input = parts[0].trim();
    let quantity = null;
    let unit = null;
    
    if (parts.length > 1) {
      const q = parseFloat(parts[1].trim());
      if (!isNaN(q)) quantity = q;
    }
    if (parts.length > 2) {
      unit = parts[2].trim().toLowerCase();
    }
    
    return { raw_input, quantity, unit };
  });


  try {
    await store.uploadBOM(store.activeBudget.id, linesPayload);
    bomInput.value = '';
  } catch (e) {
    console.error(e);
  }
};

const getStatusBadgeClass = (status: string) => {
  switch (status) {
    case 'auto': return 'badge badge-auto';
    case 'friction': return 'badge badge-friction';
    case 'missing': return 'badge badge-missing';
    case 'resolved': return 'badge badge-resolved';
    default: return 'badge';
  }
};

const formatConfidence = (val: number | null) => {
  if (val === null) return '-';
  return `${(val * 100).toFixed(1)}%`;
};

const budgetTotalRange = computed(() => {
  if (store.activeLines.length === 0) return '$0.00';
  let minTotal = 0;
  let hasPending = false;
  
  for (const line of store.activeLines) {
    if (line.unit_price) {
      minTotal += (line.quantity || 1) * line.unit_price;
    } else {
      hasPending = true;
    }
  }
  
  if (hasPending) {
    return `Mínimo $${minTotal.toLocaleString('es-MX', { minimumFractionDigits: 2 })} (Pendiente cotizar)`;
  }
  return `$${minTotal.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
});
</script>

<template>
  <div class="dashboard-view animate-fade-in">
    <div class="header-section">
      <div>
        <h1>Dashboard de Presupuestos</h1>
        <p>Estandarización semántica instantánea y cotizaciones automáticas.</p>
      </div>
      <div v-if="store.activeBudget" class="budget-summary card">
        <div class="summary-label">Presupuesto Activo</div>
        <div class="summary-title">{{ store.activeBudget.project_name }}</div>
        <div class="summary-value">{{ budgetTotalRange }}</div>
      </div>
    </div>

    <div class="grid-layout">
      <!-- Panel de Creación / Carga -->
      <div class="side-panel-grid">
        <div class="card form-card">
          <h2>Nuevo Presupuesto</h2>
          <form @submit.prevent="handleCreateBudget" class="form-container">
            <div class="input-group">
              <label class="input-label">Nombre del Proyecto</label>
              <input v-model="projectName" type="text" class="input-field" placeholder="Ej. Agencia Chevrolet Norte" required />
            </div>
            
            <div class="input-group">
              <label class="input-label">Tipo de Proyecto</label>
              <select v-model="projectType" class="input-field">
                <option value="residencial">Residencial</option>
                <option value="comercial">Comercial</option>
                <option value="agencia_auto">Agencia de Autos</option>
                <option value="industrial">Industrial</option>
                <option value="otro">Otro</option>
              </select>
            </div>
            
            <div class="input-group">
              <label class="input-label">Región Geográfica</label>
              <input v-model="region" type="text" class="input-field" placeholder="Ej. Aguascalientes" required />
            </div>

            <button type="submit" class="btn btn-primary" :disabled="store.loading">
              <Plus :size="18" /> Crear Presupuesto
            </button>
          </form>
        </div>

        <div v-if="store.activeBudget" class="card form-card">
          <h2>Ingesta de BOM (Catálogo)</h2>
          <p class="section-desc">Pega tu catálogo de conceptos. Una línea por renglón.</p>
          <div class="format-tip">
            Formato: <code>Descripción del concepto | cantidad | unidad</code>
          </div>
          <form @submit.prevent="handleUploadBOM" class="form-container">
            <div class="input-group">
              <textarea 
                v-model="bomInput" 
                rows="6" 
                class="input-field textarea-field" 
                placeholder="Ej:&#10;Luminaria LED 15w empotrada | 24 | pza&#10;Cable cobre calibre 12 | 120 | ml&#10;Concreto fc=250 kg/cm2 | 12 | m3"
                required
              ></textarea>
            </div>

            <button type="submit" class="btn btn-primary" :disabled="store.loading">
              <Upload :size="18" /> Procesar Catálogo
            </button>
          </form>
        </div>
      </div>

      <!-- Tabla de Líneas del Presupuesto Activo -->
      <div class="main-panel-grid">
        <div class="card table-card">
          <div class="table-header">
            <div>
              <h2>Líneas de Presupuesto</h2>
              <p v-if="store.activeBudget">Conceptos procesados para: <strong>{{ store.activeBudget.project_name }}</strong></p>
              <p v-else>Selecciona o crea un presupuesto a la izquierda para empezar.</p>
            </div>
            <button 
              v-if="store.activeBudget" 
              @click="store.fetchBudgetLines(store.activeBudget.id)" 
              class="btn btn-secondary btn-icon-only"
              title="Refrescar precios"
            >
              <RefreshCw :size="16" />
            </button>
          </div>

          <div v-if="store.activeBudget && store.activeLines.length > 0" class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Concepto Crudo</th>
                  <th style="width: 100px;">Cant.</th>
                  <th style="width: 80px;">Unidad</th>
                  <th style="width: 130px;">Match Semántico</th>
                  <th style="width: 100px;">Confianza</th>
                  <th style="width: 120px;">Precio Unitario</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in store.activeLines" :key="line.id" class="table-row">
                  <td>
                    <div class="raw-input-cell" :title="line.raw_input">
                      {{ line.raw_input }}
                    </div>
                  </td>
                  <td>{{ line.quantity || '-' }}</td>
                  <td><span class="unit-text">{{ line.unit || '-' }}</span></td>
                  <td>
                    <span :class="getStatusBadgeClass(line.match_status)">
                      {{ line.match_status }}
                    </span>
                  </td>
                  <td class="font-mono">{{ formatConfidence(line.match_confidence) }}</td>
                  <td class="font-mono text-accent">
                    <span v-if="line.unit_price" class="resolved-price">
                      ${{ line.unit_price.toLocaleString('es-MX', { minimumFractionDigits: 2 }) }}
                    </span>
                    <span v-else class="pending-price">
                      Pendiente
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="store.activeBudget" class="empty-state">
            <Layers :size="48" class="empty-icon" />
            <h3>Presupuesto sin líneas</h3>
            <p>Pega un catálogo de conceptos a la izquierda para empezar el procesamiento semántico.</p>
          </div>
          
          <div v-else class="empty-state">
            <FileText :size="48" class="empty-icon" />
            <h3>Sin presupuesto activo</h3>
            <p>Crea un presupuesto a la izquierda para poder procesar catálogos BOM.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.budget-summary {
  padding: 1rem 1.75rem;
  background: rgba(92, 98, 236, 0.08);
  border-color: rgba(92, 98, 236, 0.25);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.summary-label {
  font-size: 0.775rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.15rem;
}

.summary-title {
  font-size: 0.95rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.summary-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--primary);
  font-family: monospace;
}

.grid-layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 2rem;
  align-items: start;
}

.side-panel-grid {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-card h2 {
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
}

.section-desc {
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.format-tip {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.775rem;
  font-family: monospace;
  margin-bottom: 1rem;
  color: var(--text-muted);
}

.format-tip code {
  color: var(--text-main);
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.textarea-field {
  resize: vertical;
  font-family: monospace;
  font-size: 0.85rem;
  line-height: 1.4;
}

.table-card {
  padding: 0;
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.table-header h2 {
  font-size: 1.25rem;
  margin-bottom: 0.25rem;
}

.btn-icon-only {
  padding: 0.5rem;
  border-radius: var(--radius-sm);
}

.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.9rem;
}

.data-table th {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-muted);
  font-weight: 500;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: rgba(255, 255, 255, 0.01);
}

.data-table td {
  padding: 0.9rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.table-row:hover {
  background: rgba(255, 255, 255, 0.015);
}

.raw-input-cell {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.unit-text {
  font-family: monospace;
  background: rgba(255, 255, 255, 0.03);
  padding: 0.15rem 0.4rem;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
}

.font-mono {
  font-family: monospace;
  font-size: 0.875rem;
}

.resolved-price {
  color: var(--accent-auto);
  font-weight: 600;
}

.pending-price {
  color: var(--text-muted);
  font-style: italic;
  font-size: 0.8rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6rem 2rem;
  text-align: center;
  gap: 0.5rem;
}

.empty-icon {
  color: var(--text-muted);
  opacity: 0.4;
  margin-bottom: 0.5rem;
}
</style>
