import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'

const routes = [
  { path: '/', component: { template: '<div>home</div>' } },
  { path: '/play/:date', component: { template: '<div>play</div>' }, props: true },
  { path: '/admin', component: { template: '<div>admin</div>' } },
]

export function createTestRouter(initial = '/') {
  const router = createRouter({ history: createWebHistory(), routes })
  router.push(initial)
  return router
}

export async function mountWithRouter(component, options = {}, initial = '/') {
  const router = createTestRouter(initial)
  const wrapper = mount(component, {
    ...options,
    global: { plugins: [router], ...(options.global || {}) },
  })
  await router.isReady()
  await flushPromises()
  return { wrapper, router }
}

let fetchBackup

export function mockFetch(handler) {
  fetchBackup = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    const res = handler(String(url), options)
    if (res instanceof Response) return res
    return new Response(JSON.stringify(res.body), { status: res.status || 200, headers: { 'Content-Type': 'application/json' } })
  }
}

export function restoreFetch() {
  globalThis.fetch = fetchBackup
}

export async function dispatchTimeUpdate(video, time) {
  Object.defineProperty(video, 'currentTime', { value: time, writable: true, configurable: true })
  Object.defineProperty(video, 'duration', { value: 20, writable: true, configurable: true })
  video.dispatchEvent(new Event('timeupdate'))
  await nextTick()
}
