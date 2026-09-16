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
        <router-link to="/local" class="nav-link" :class="{ active: route.path === '/local' }">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
          <span>自由播放</span>
        </router-link>
        <router-link to="/admin" class="nav-link icon-link" :class="{ active: route.path === '/admin' }" aria-label="后台管理" title="后台管理">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        </router-link>
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
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

.nav-link.icon-link {
  padding: 0;
  width: 40px;
  height: 40px;
  justify-content: center;
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
