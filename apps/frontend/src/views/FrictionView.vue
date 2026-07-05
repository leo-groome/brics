<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useBricsStore } from '../stores/brics';
import { AlertCircle, Check, Trash2, ArrowRight, Zap } from '@lucide/vue';


// Para evitar problemas de importación entre backend/frontend en empaquetado Vite, 
// definimos la lista de familias en local como fallback
const familiesList = [
  "Preliminares", "Demolicion", "Movimientos Tierra", "Cimentacion", 
  "Estructura Concreto", "Estructura Acero", "Albanileria", "Impermeabilizacion",
  "Tablarroca", "Plafones", "Pintura", "Pisos", "Recubrimientos Muros", 
  "Carpinteria", "Canceleria Aluminio", "Cristaleria", "Herreria", "Fachada",
  "Muebles Bano", "Muebles Cocina", "Equipamiento", "Instalacion Electrica", 
  "Iluminacion", "Instalacion Hidraulica", "Instalacion Sanitaria", 
  "Instalacion Gas", "Aire Acondicionado", "Voz Datos", "Seguridad CCTV", "Otros"
];

const store = useBricsStore();
const activeIndex = ref(0);

// Formulario de nuevo concepto
const newFamily = ref('Otros');
const newTechnicalConcept = ref('');
const newUnit = ref('pza');

onMounted(async () => {
  await store.fetchFrictionItems();
  // Inicializa atajos de teclado
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

const activeItem = ref<any>(null);

// Mantiene el item activo en base al índice seleccionado
const updateActiveItem = () => {
  if (store.frictionItems.length > 0) {
    if (activeIndex.value >= store.frictionItems.length) {
      activeIndex.value = store.frictionItems.length - 1;
    }
    activeItem.value = store.frictionItems[activeIndex.value];
    
    // Auto-rellena formulario con el texto crudo para facilitar la edición
    if (activeItem.value) {
      newTechnicalConcept.value = activeItem.value.raw_input;
    }
  } else {
    activeItem.value = null;
  }
};

// Observa cambios en los items de fricción
import { watch } from 'vue';
watch(() => store.frictionItems, () => {
  updateActiveItem();
}, { deep: true, immediate: true });

const selectItem = (index: number) => {
  activeIndex.value = index;
  updateActiveItem();
};

const handleSelectCandidate = async (candidateId: number) => {
  if (!activeItem.value) return;
  try {
    await store.resolveFriction(activeItem.value.budget_line_id, {
      action: 'select_candidate',
      concept_id: candidateId
    });
  } catch (e) {
    console.error(e);
  }
};

const handleCreateConcept = async () => {
  if (!activeItem.value || !newTechnicalConcept.value.trim()) return;
  try {
    await store.resolveFriction(activeItem.value.budget_line_id, {
      action: 'create_new_concept',
      family: newFamily.value,
      technical_concept: newTechnicalConcept.value.trim(),
      unit: newUnit.value
    });
    newTechnicalConcept.value = '';
  } catch (e) {
    console.error(e);
  }
};

const handleDiscardLine = async () => {
  if (!activeItem.value) return;
  try {
    await store.resolveFriction(activeItem.value.budget_line_id, {
      action: 'discard'
    });
  } catch (e) {
    console.error(e);
  }
};

// Atajos de teclado: 1-5 para seleccionar candidatos, D para descartar
const handleKeyDown = (e: KeyboardEvent) => {
  if (!activeItem.value) return;
  
  // Evitar atajos si se está editando el input
  if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA' || document.activeElement?.tagName === 'SELECT') {
    return;
  }

  const key = e.key.toLowerCase();
  
  if (key === 'd') {
    e.preventDefault();
    handleDiscardLine();
  } else if (key === 'n') {
    e.preventDefault();
    // Enfoca el input de creación
    document.getElementById('new-concept-input')?.focus();
  } else {
    const num = parseInt(key);
    if (!isNaN(num) && num >= 1 && num <= activeItem.value.top_candidates.length) {
      e.preventDefault();
      const cand = activeItem.value.top_candidates[num - 1];
      if (cand) {
        handleSelectCandidate(cand.concept_id);
      }
    }
  }
};

const formatConfidence = (val: number) => {
  return `${(val * 100).toFixed(1)}%`;
};
</script>

<template>
  <div class="friction-view animate-fade-in">
    <div class="header-section">
      <div>
        <h1>Matriz de Fricción</h1>
        <p>Estandarización manual de anomalías semánticas. Resuelve excepciones con atajos de teclado.</p>
      </div>
      <div v-if="store.frictionItems.length > 0" class="items-counter card">
        <span class="counter-label">Conceptos Pendientes</span>
        <span class="counter-val">{{ store.frictionItems.length }}</span>
      </div>
    </div>

    <!-- Vacío -->
    <div v-if="store.frictionItems.length === 0" class="empty-friction card">
      <div class="success-icon-wrapper">
        <Check :size="48" class="success-icon" />
      </div>
      <h2>¡Cero Fricción!</h2>
      <p>Todas las líneas del catálogo maestro han sido mapeadas correctamente con un nivel de confianza &ge; 95% o no hay presupuestos activos.</p>
    </div>

    <!-- Flujo de Trabajo -->
    <div v-else class="friction-container">
      <!-- Columna izquierda: Lista de anomalías -->
      <div class="friction-sidebar card">
        <h2>Pendientes</h2>
        <div class="items-list">
          <div 
            v-for="(item, idx) in store.frictionItems" 
            :key="item.budget_line_id"
            :class="['friction-sidebar-item', { active: idx === activeIndex }]"
            @click="selectItem(idx)"
          >
            <div class="item-raw">{{ item.raw_input }}</div>
            <div class="item-sub">Línea ID: #{{ item.budget_line_id }} • Cantidad: {{ item.quantity || '-' }}</div>
          </div>
        </div>
      </div>

      <!-- Columna derecha: Detalle y Resolución -->
      <div class="friction-workspace" v-if="activeItem">
        <!-- Encabezado de la tarjeta activa -->
        <div class="card active-concept-card">
          <div class="card-status-label">
            <AlertCircle :size="16" /> Requiere revisión humana
          </div>
          <div class="active-concept-title">
            "{{ activeItem.raw_input }}"
          </div>
          <div class="active-concept-meta">
            <span>Cantidad: <strong>{{ activeItem.quantity || '-' }}</strong></span>
            <span>ID de Línea: <strong>{{ activeItem.budget_line_id }}</strong></span>
            <span class="shortcut-indicator">Tip: Presiona números [1-5] para asociar o [D] para descartar</span>
          </div>
        </div>

        <!-- Candidatos Encontrados -->
        <div class="candidates-section">
          <h3>Candidatos del Catálogo Maestro</h3>
          <div class="candidates-list">
            <div 
              v-for="(cand, idx) in activeItem.top_candidates" 
              :key="cand.concept_id"
              class="candidate-card card"
              @click="handleSelectCandidate(cand.concept_id)"
            >
              <div class="candidate-number">{{ Number(idx) + 1 }}</div>
              <div class="candidate-info">
                <div class="candidate-desc">{{ cand.technical_concept }}</div>
                <div class="candidate-meta">
                  <span class="candidate-family">{{ cand.family }}</span>
                  <span class="divider">•</span>
                  <span class="candidate-unit">{{ cand.unit }}</span>
                </div>
              </div>
              <div class="candidate-match">
                <div class="match-score font-mono">{{ formatConfidence(cand.confidence) }}</div>
                <div class="match-label">Similitud</div>
              </div>
              <div class="candidate-action">
                <button class="btn btn-secondary btn-icon-only">
                  <Check :size="18" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Acciones: Crear o Descartar -->
        <div class="actions-section">
          <!-- Crear concepto -->
          <div class="card create-concept-card">
            <div class="card-header-icon">
              <Zap :size="18" class="zap-icon" />
              <h3>Crear Nuevo Concepto Canónico</h3>
            </div>
            <p>Si ninguno de los candidatos es adecuado, normaliza e introduce este concepto en el catálogo maestro.</p>
            
            <form @submit.prevent="handleCreateConcept" class="create-form">
              <div class="form-row">
                <div class="input-group">
                  <label class="input-label">Descripción Técnica Canónica</label>
                  <input 
                    id="new-concept-input"
                    v-model="newTechnicalConcept" 
                    type="text" 
                    class="input-field" 
                    required 
                  />
                </div>
              </div>
              
              <div class="form-row grid-2">
                <div class="input-group">
                  <label class="input-label">Familia</label>
                  <select v-model="newFamily" class="input-field">
                    <option v-for="fam in familiesList" :key="fam" :value="fam">
                      {{ fam }}
                    </option>
                  </select>
                </div>
                
                <div class="input-group">
                  <label class="input-label">Unidad</label>
                  <select v-model="newUnit" class="input-field">
                    <option value="pza">pza</option>
                    <option value="m2">m2</option>
                    <option value="m3">m3</option>
                    <option value="ml">ml</option>
                    <option value="kg">kg</option>
                    <option value="ton">ton</option>
                    <option value="lote">lote</option>
                    <option value="jgo">jgo</option>
                    <option value="salida">salida</option>
                    <option value="lt">lt</option>
                    <option value="ml_cable">ml_cable</option>
                    <option value="servicio">servicio</option>
                  </select>
                </div>
              </div>

              <div class="form-actions">
                <button type="button" @click="handleDiscardLine" class="btn btn-danger">
                  <Trash2 :size="18" /> Descartar Línea [D]
                </button>
                <button type="submit" class="btn btn-primary">
                  Crear y Asociar <ArrowRight :size="18" />
                </button>
              </div>
            </form>
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
  margin-bottom: 1.5rem;
}

.items-counter {
  padding: 0.75rem 1.5rem;
  background: rgba(245, 158, 11, 0.08);
  border-color: rgba(245, 158, 11, 0.25);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.counter-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.counter-val {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--accent-friction);
}

.empty-friction {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6rem 2rem;
  text-align: center;
  gap: 1rem;
}

.success-icon-wrapper {
  background: var(--accent-auto-glow);
  border: 1px solid rgba(16, 185, 129, 0.3);
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.success-icon {
  color: var(--accent-auto);
}

.friction-container {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 2rem;
  align-items: start;
}

.friction-sidebar {
  padding: 1.25rem 0;
  max-height: 700px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.friction-sidebar h2 {
  font-size: 1.1rem;
  padding: 0 1.25rem 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.items-list {
  overflow-y: auto;
  flex: 1;
}

.friction-sidebar-item {
  padding: 0.9rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s ease;
}

.friction-sidebar-item:hover {
  background: rgba(255, 255, 255, 0.02);
}

.friction-sidebar-item.active {
  background: rgba(245, 158, 11, 0.07);
  border-left: 3px solid var(--accent-friction);
}

.item-raw {
  font-size: 0.9rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

.friction-workspace {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.active-concept-card {
  border-left: 4px solid var(--accent-friction);
  background: rgba(245, 158, 11, 0.02);
}

.card-status-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.775rem;
  color: var(--accent-friction);
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}

.active-concept-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 0.75rem;
  line-height: 1.3;
}

.active-concept-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  align-items: center;
  flex-wrap: wrap;
}

.shortcut-indicator {
  margin-left: auto;
  background: rgba(255, 255, 255, 0.05);
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  color: var(--text-muted);
  border: 1px solid var(--border-color);
}

.candidates-section h3 {
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
  color: var(--text-muted);
}

.candidates-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.candidate-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  cursor: pointer;
}

.candidate-card:hover {
  border-color: rgba(92, 98, 236, 0.4);
  background: rgba(92, 98, 236, 0.02);
}

.candidate-number {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
}

.candidate-card:hover .candidate-number {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.candidate-info {
  flex: 1;
}

.candidate-desc {
  font-size: 0.95rem;
  font-weight: 500;
  margin-bottom: 0.15rem;
}

.candidate-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.775rem;
  color: var(--text-muted);
}

.candidate-family {
  background: rgba(255, 255, 255, 0.03);
  padding: 0.05rem 0.35rem;
  border-radius: var(--radius-sm);
}

.candidate-unit {
  font-family: monospace;
}

.candidate-match {
  text-align: right;
  margin-right: 0.5rem;
}

.match-score {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--accent-auto);
}

.match-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.create-concept-card {
  border-top: 1px solid var(--border-color);
}

.card-header-icon {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.zap-icon {
  color: var(--primary);
}

.create-concept-card p {
  font-size: 0.85rem;
  margin-bottom: 1.25rem;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
}
</style>
