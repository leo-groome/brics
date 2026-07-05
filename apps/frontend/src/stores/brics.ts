import { defineStore } from 'pinia';

const API_BASE = 'http://localhost:8000/api/v1';

export interface Budget {
  id: number;
  project_name: string | null;
  project_type: string | null;
  region: string | null;
  status: string;
}

export interface BudgetLine {
  id: number;
  raw_input: string;
  quantity: number | null;
  unit: string | null;
  matched_concept_id: number | null;
  match_confidence: number | null;
  match_status: string;
  unit_price: number | null;
}

export interface Candidate {
  concept_id: number;
  family: string;
  technical_concept: string;
  unit: string;
  confidence: number;
}

export interface FrictionItem {
  budget_line_id: number;
  budget_id: number;
  raw_input: string;
  quantity: number | null;
  top_candidates: Candidate[];
}

export interface Supplier {
  id: number;
  name: string;
  whatsapp_number: string;
  families: string[];
  active: boolean;
}

export const useBricsStore = defineStore('brics', {
  state: () => ({
    budgets: [] as Budget[],
    activeBudget: null as Budget | null,
    activeLines: [] as BudgetLine[],
    frictionItems: [] as FrictionItem[],
    suppliers: [] as Supplier[],
    loading: false,
    error: null as string | null,
  }),

  actions: {
    async fetchBudgets() {
      this.loading = true;
      try {
        // En el backend no hay endpoint list budgets, pero si se agrega después, o podemos crear uno.
        // Si no está, podemos simular que el backend devuelve un listado o manejarlo localmente por el momento.
        // El api/v1/budgets.py tiene GET /budgets/{id}. Vamos a implementar un mock/fetch si falla.
        const res = await fetch(`${API_BASE}/budgets`);
        if (res.ok) {
          this.budgets = await res.json();
        }
      } catch (err: any) {
        console.warn('Falla al listar presupuestos (endpoint no implementado en backend)', err);
      } finally {
        this.loading = false;
      }
    },

    async createBudget(projectName: string, projectType: string, region: string) {
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch(`${API_BASE}/budgets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_name: projectName,
            project_type: projectType,
            region,
          }),
        });
        if (!res.ok) throw new Error('Error al crear el presupuesto');
        const data = await res.json();
        this.budgets.push(data);
        this.activeBudget = data;
        return data;
      } catch (err: any) {
        this.error = err.message;
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async fetchBudget(id: number) {
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch(`${API_BASE}/budgets/${id}`);
        if (!res.ok) throw new Error('Error al obtener presupuesto');
        this.activeBudget = await res.json();
        await this.fetchBudgetLines(id);
      } catch (err: any) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    async fetchBudgetLines(budgetId: number) {
      try {
        const res = await fetch(`${API_BASE}/budgets/${budgetId}/lines`);
        if (res.ok) {
          this.activeLines = await res.json();
        }
      } catch (err) {
        console.error('Error fetching budget lines', err);
      }
    },

    async uploadBOM(budgetId: number, lines: { raw_input: string; quantity: number | null; unit: string | null }[]) {
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch(`${API_BASE}/budgets/${budgetId}/lines/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lines }),
        });
        if (!res.ok) throw new Error('Error al subir el catálogo BOM');
        const data = await res.json();
        this.activeLines = data;
        // Al subir, recargamos la lista de fricción
        await this.fetchFrictionItems();
        return data;
      } catch (err: any) {
        this.error = err.message;
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async fetchFrictionItems() {
      try {
        const res = await fetch(`${API_BASE}/friction/pending`);
        if (res.ok) {
          this.frictionItems = await res.json();
        }
      } catch (err) {
        console.error('Error fetching friction items', err);
      }
    },

    async resolveFriction(lineId: number, payload: any) {
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch(`${API_BASE}/friction/${lineId}/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Error al resolver fricción');
        const data = await res.json();
        
        // Remover de la lista local de fricción
        this.frictionItems = this.frictionItems.filter(item => item.budget_line_id !== lineId);
        
        // Actualizar la línea de presupuesto correspondiente si está en el presupuesto activo
        if (this.activeBudget) {
          await this.fetchBudgetLines(this.activeBudget.id);
        }
        return data;
      } catch (err: any) {
        this.error = err.message;
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async fetchSuppliers() {
      try {
        const res = await fetch(`${API_BASE}/suppliers`);
        if (res.ok) {
          this.suppliers = await res.json();
        }
      } catch (err) {
        console.error('Error fetching suppliers', err);
      }
    },

    async createSupplier(supplier: Omit<Supplier, 'id'>) {
      try {
        const res = await fetch(`${API_BASE}/suppliers`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(supplier),
        });
        if (!res.ok) throw new Error('Error al registrar proveedor');
        const data = await res.json();
        this.suppliers.push(data);
        return data;
      } catch (err: any) {
        this.error = err.message;
        throw err;
      }
    },

    async deleteSupplier(id: number) {
      try {
        const res = await fetch(`${API_BASE}/suppliers/${id}`, {
          method: 'DELETE',
        });
        if (!res.ok) throw new Error('Error al eliminar proveedor');
        this.suppliers = this.suppliers.filter(s => s.id !== id);
      } catch (err: any) {
        this.error = err.message;
        throw err;
      }
    }
  }
});
