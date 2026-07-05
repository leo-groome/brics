<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useBricsStore } from '../stores/brics';
import { Plus, Trash2, Phone, CheckSquare, Square, UserPlus } from '@lucide/vue';

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

// Formulario de proveedor
const name = ref('');
const whatsappNumber = ref('');
const selectedFamilies = ref<string[]>([]);
const active = ref(true);

onMounted(() => {
  store.fetchSuppliers();
});

const toggleFamily = (fam: string) => {
  const idx = selectedFamilies.value.indexOf(fam);
  if (idx > -1) {
    selectedFamilies.value.splice(idx, 1);
  } else {
    selectedFamilies.value.push(fam);
  }
};

const handleCreateSupplier = async () => {
  if (!name.value || !whatsappNumber.value) return;
  
  // Limpia el número de WhatsApp a formato internacional básico si es necesario
  let cleanNumber = whatsappNumber.value.trim().replace(/\D/g, '');
  if (!cleanNumber.startsWith('52') && cleanNumber.length === 10) {
    cleanNumber = '52' + cleanNumber; // Asume México por defecto
  }
  
  try {
    await store.createSupplier({
      name: name.value,
      whatsapp_number: cleanNumber,
      families: selectedFamilies.value,
      active: active.value
    });
    
    // Resetea formulario
    name.value = '';
    whatsappNumber.value = '';
    selectedFamilies.value = [];
    active.value = true;
  } catch (e) {
    console.error(e);
  }
};

const handleDelete = async (id: number) => {
  if (confirm('¿Estás seguro de que deseas eliminar este proveedor?')) {
    try {
      await store.deleteSupplier(id);
    } catch (e) {
      console.error(e);
    }
  }
};
</script>

<template>
  <div class="suppliers-view animate-fade-in">
    <div class="header-section">
      <div>
        <h1>Directorio de Proveedores</h1>
        <p>Registra y gestiona proveedores asociados a familias de materiales para cotizaciones por WhatsApp.</p>
      </div>
    </div>

    <div class="grid-layout">
      <!-- Columna izquierda: Registro de proveedor -->
      <div class="card form-card">
        <div class="card-title-icon">
          <UserPlus :size="20" class="icon-accent" />
          <h2>Nuevo Proveedor</h2>
        </div>
        
        <form @submit.prevent="handleCreateSupplier" class="form-container">
          <div class="input-group">
            <label class="input-label">Nombre del Proveedor</label>
            <input v-model="name" type="text" class="input-field" placeholder="Ej. Aceros del Centro" required />
          </div>

          <div class="input-group">
            <label class="input-label">Número de WhatsApp</label>
            <input v-model="whatsappNumber" type="text" class="input-field" placeholder="Ej. 4491234567" required />
            <span class="input-help">Formatos válidos: 10 dígitos (local) o con código de país.</span>
          </div>

          <!-- Selector de Familias -->
          <div class="input-group">
            <label class="input-label">Familias de Materiales</label>
            <div class="families-selector">
              <div 
                v-for="fam in familiesList" 
                :key="fam" 
                :class="['family-checkbox-card', { checked: selectedFamilies.includes(fam) }]"
                @click="toggleFamily(fam)"
              >
                <CheckSquare v-if="selectedFamilies.includes(fam)" :size="16" class="check-icon" />
                <Square v-else :size="16" class="check-icon" />
                <span>{{ fam }}</span>
              </div>
            </div>
          </div>

          <div class="input-group checkbox-row">
            <input type="checkbox" v-model="active" id="active-checkbox" />
            <label for="active-checkbox">Proveedor Activo</label>
          </div>

          <button type="submit" class="btn btn-primary" :disabled="store.loading">
            <Plus :size="18" /> Registrar Proveedor
          </button>
        </form>
      </div>

      <!-- Columna derecha: Listado de proveedores -->
      <div class="card list-card">
        <h2>Proveedores Registrados</h2>
        
        <div v-if="store.suppliers.length > 0" class="suppliers-list">
          <div v-for="sup in store.suppliers" :key="sup.id" class="supplier-item card">
            <div class="sup-main-info">
              <div class="sup-name-row">
                <span class="sup-name">{{ sup.name }}</span>
                <span :class="['sup-status', { active: sup.active }]">
                  {{ sup.active ? 'Activo' : 'Inactivo' }}
                </span>
              </div>
              <div class="sup-phone font-mono">
                <Phone :size="14" /> {{ sup.whatsapp_number }}
              </div>
              
              <!-- Chips de familias -->
              <div class="sup-families">
                <span v-for="fam in sup.families" :key="fam" class="family-chip">
                  {{ fam }}
                </span>
                <span v-if="!sup.families || sup.families.length === 0" class="no-families-chip">
                  Sin familias asignadas
                </span>
              </div>
            </div>
            
            <div class="sup-actions">
              <button @click="handleDelete(sup.id)" class="btn btn-danger btn-icon-only" title="Eliminar Proveedor">
                <Trash2 :size="16" />
              </button>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <Phone :size="48" class="empty-icon" />
          <h3>Sin proveedores registrados</h3>
          <p>Llena el formulario a la izquierda para registrar a tus proveedores de confianza.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header-section {
  margin-bottom: 1.5rem;
}

.card-title-icon {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.icon-accent {
  color: var(--primary);
}

.grid-layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 2rem;
  align-items: start;
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.input-help {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.families-selector {
  border: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.15);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 250px;
  overflow-y: auto;
}

.family-checkbox-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.6rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.family-checkbox-card:hover {
  background: rgba(255, 255, 255, 0.03);
}

.family-checkbox-card.checked {
  background: rgba(92, 98, 236, 0.08);
  border-color: rgba(92, 98, 236, 0.2);
  color: var(--text-main);
}

.check-icon {
  color: var(--text-muted);
}

.checked .check-icon {
  color: var(--primary);
}

.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-row input {
  width: 16px;
  height: 16px;
}

.checkbox-row label {
  font-size: 0.9rem;
  color: var(--text-main);
  user-select: none;
}

.list-card {
  min-height: 500px;
}

.list-card h2 {
  font-size: 1.25rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.suppliers-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 700px;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.supplier-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.015);
}

.supplier-item:hover {
  background: rgba(255, 255, 255, 0.025);
  border-color: rgba(255, 255, 255, 0.12);
}

.sup-main-info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
}

.sup-name-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.sup-name {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
}

.sup-status {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
  border: 1px solid var(--border-color);
}

.sup-status.active {
  background: var(--accent-auto-glow);
  color: var(--accent-auto);
  border-color: rgba(16, 185, 129, 0.2);
}

.sup-phone {
  font-size: 0.85rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.sup-families {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.2rem;
}

.family-chip {
  background: rgba(92, 98, 236, 0.06);
  border: 1px solid rgba(92, 98, 236, 0.15);
  color: #a5b4fc;
  font-size: 0.725rem;
  padding: 0.1rem 0.45rem;
  border-radius: var(--radius-sm);
}

.no-families-chip {
  font-size: 0.725rem;
  color: var(--text-muted);
  font-style: italic;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8rem 2rem;
  text-align: center;
  gap: 0.5rem;
}

.empty-icon {
  color: var(--text-muted);
  opacity: 0.4;
  margin-bottom: 0.5rem;
}
</style>
