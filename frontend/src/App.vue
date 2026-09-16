<script setup>
import { useRoute, RouterView } from 'vue-router'

const route = useRoute()
</script>

<template>
  <header class="app-bar">
    <div class="app-bar-inner">
      <router-link to="/" class="brand" aria-label="返回首页">
        <span class="brand-mark" aria-hidden="true">✦</span>
        <span class="brand-name">EnLearn</span>
      </router-link>
      <nav class="app-nav">
        <router-link to="/local" class="nav-link" :class="{ active: route.path === '/local' }">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
  <main class="app-main">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </main>
</template>

<style scoped>
.app-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: saturate(180%) blur(18px);
  -webkit-backdrop-filter: saturate(180%) blur(18px);
}

/* 彩虹描边:纯装饰 */
.app-bar::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 4px;
  background: linear-gradient(
    90deg,
    var(--yellow),
    var(--pink),
    var(--purple),
    var(--cyan),
    var(--green)
  );
}

.app-bar-inner {
  width: var(--layout-width);
  max-width: var(--layout-max);
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
  gap: 10px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 24px;
  color: var(--ink);
  transition: transform var(--transition);
}

.brand:hover {
  transform: rotate(-2deg) scale(1.03);
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(140deg, var(--yellow), var(--pink) 55%, var(--purple));
  color: #fff;
  font-size: 18px;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
  animation: wiggle 4s ease-in-out infinite;
}

.brand-name {
  background: linear-gradient(180deg, var(--ink) 55%, var(--purple));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  min-height: 46px;
  border-radius: var(--radius-pill);
  font-size: 15px;
  font-weight: 700;
  color: var(--muted);
  border: 2px solid transparent;
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition);
}

.nav-link:hover {
  background: var(--blue-bg);
  color: var(--blue);
  transform: translateY(-1px);
}

.nav-link.active {
  background: var(--grad-blue);
  color: #fff;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.nav-link.icon-link {
  padding: 0;
  width: 46px;
  height: 46px;
  justify-content: center;
}

@media (max-width: 768px) {
  .app-bar-inner {
    padding: 10px 16px;
  }
  .brand {
    font-size: 20px;
  }
  .brand-mark {
    width: 34px;
    height: 34px;
    font-size: 15px;
  }
  .nav-link {
    padding: 8px 14px;
    font-size: 14px;
  }
}
</style>
