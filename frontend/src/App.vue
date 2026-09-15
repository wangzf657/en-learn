<script setup>
import { useRoute, RouterView } from 'vue-router'

const route = useRoute()
</script>

<template>
  <header class="app-bar">
    <div class="app-bar-inner">
      <router-link to="/" class="brand" aria-label="返回首页">
        <span class="brand-mark">✦</span>
        <span class="brand-name">EnLearn</span>
      </router-link>
      <nav class="app-nav">
        <router-link to="/admin" class="nav-link" :class="{ active: route.path === '/admin' }">后台</router-link>
      </nav>
    </div>
  </header>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.app-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(245, 245, 247, 0.86);
  backdrop-filter: saturate(180%) blur(16px);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid rgba(229, 229, 234, 0.6);
}

.app-bar-inner {
  width: 1120px;
  max-width: 100%;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 20px;
  color: var(--ink);
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--blue);
  color: #fff;
  font-size: 14px;
  box-shadow: var(--shadow-blue);
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-link {
  padding: 8px 16px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  transition: background var(--transition), color var(--transition);
}

.nav-link:hover,
.nav-link.active {
  background: var(--blue-bg);
  color: var(--blue);
}

@media (max-width: 768px) {
  .app-bar-inner {
    padding: 10px 16px;
  }
  .brand-name {
    font-size: 18px;
  }
}
</style>
