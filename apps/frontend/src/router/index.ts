import { createRouter, createWebHistory } from 'vue-router';
import DashboardView from '../views/DashboardView.vue';
import FrictionView from '../views/FrictionView.vue';
import SuppliersView from '../views/SuppliersView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView,
    },
    {
      path: '/friction',
      name: 'friction',
      component: FrictionView,
    },
    {
      path: '/suppliers',
      name: 'suppliers',
      component: SuppliersView,
    },
  ],
});

export default router;
