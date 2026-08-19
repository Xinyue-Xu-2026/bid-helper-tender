import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/HomeView.vue') },
  { path: '/projects/:id', component: () => import('../views/ProjectDetail.vue') },
  { path: '/assets', component: () => import('../views/AssetsView.vue') },
  { path: '/settings', component: () => import('../views/SettingsView.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
