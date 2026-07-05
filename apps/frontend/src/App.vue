<script setup lang="ts">
import { onMounted } from 'vue';
import { RouterLink, RouterView } from 'vue-router';
import { useBricsStore } from './stores/brics';
import { LayoutDashboard, AlertOctagon, Users, Hammer } from '@lucide/vue';

const store = useBricsStore();

onMounted(() => {
  // Carga inicial
  store.fetchFrictionItems();
  
  // Polling silencioso en background cada 10s para mantener actualizados los contadores de fricción
  setInterval(() => {
    store.fetchFrictionItems();
  }, 10000);
});
</script>

<template>
  <div class="app-container">
    <!-- Barra Lateral Premium -->
    <aside class="sidebar">
      <div class="brand-section">
        <Hammer :size="24" class="brand-logo" />
        <span class="brand-name">BRICS</span>
        <span class="brand-version">v1.0</span>
      </div>
      
      <nav class="nav-menu">
        <RouterLink to="/" class="nav-item" active-class="active">
          <LayoutDashboard :size="18" />
          <span>Dashboard</span>
        </RouterLink>
        
        <RouterLink to="/friction" class="nav-item nav-item-friction" active-class="active">
          <AlertOctagon :size="18" />
          <span>Matriz de Fricción</span>
          <span v-if="store.frictionItems.length > 0" class="badge-counter font-mono">
            {{ store.frictionItems.length }}
          </span>
        </RouterLink>
        
        <RouterLink to="/suppliers" class="nav-item" active-class="active">
          <Users :size="18" />
          <span>Proveedores</span>
        </RouterLink>
      </nav>
      
      <div class="sidebar-footer">
        <div class="footer-brand">VALTA OPERATIVE</div>
        <div class="footer-status font-mono">WAR MODE ACTIVE</div>
      </div>
    </aside>

    <!-- Área de Contenido Principal -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.brand-section {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 0.5rem;
}

.brand-logo {
  color: var(--primary);
  filter: drop-shadow(0 0 8px rgba(92, 98, 236, 0.4));
}

.brand-name {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: var(--text-main);
  background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-version {
  font-size: 0.65rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: monospace;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  color: var(--text-muted);
  text-decoration: none;
  border-radius: var(--radius-md);
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-main);
}

.nav-item.active {
  background: rgba(92, 98, 236, 0.08);
  border-color: rgba(92, 98, 236, 0.25);
  color: #a5b4fc;
}

.nav-item-friction.active {
  background: rgba(245, 158, 11, 0.08);
  border-color: rgba(245, 158, 11, 0.25);
  color: #fde047;
}

.badge-counter {
  margin-left: auto;
  background: var(--accent-friction);
  color: #000;
  font-size: 0.725rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  box-shadow: 0 2px 8px var(--accent-friction-glow);
}

.sidebar-footer {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.footer-brand {
  font-size: 0.725rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.footer-status {
  font-size: 0.65rem;
  color: var(--accent-auto);
  font-weight: 600;
  letter-spacing: 0.1em;
}
</style>
