import { defineStore } from 'pinia'
import { api } from './api'

export const useSession = defineStore('session', {
  state: () => ({ user: null, loaded: false, notice: '', noticeType: 'success', filters: {} }),
  getters: {
    home: state => state.user?.role === 'admin' ? '/analytics' : state.user?.role === 'master' ? '/my-day' : '/my-cabinet',
    staff: state => ['admin', 'master'].includes(state.user?.role),
    admin: state => state.user?.role === 'admin',
  },
  actions: {
    async restore() {
      if (this.loaded) return
      if (sessionStorage.getItem('techdesk-token')) {
        try { this.user = await api('/auth/me') } catch { this.clear() }
      }
      this.loaded = true
    },
    async authenticate(path, data) {
      const response = await api('/auth/' + path, { method: 'POST', data })
      sessionStorage.setItem('techdesk-token', response.access_token)
      this.user = response.user
      this.loaded = true
    },
    clear() {
      sessionStorage.removeItem('techdesk-token')
      this.user = null
      this.filters = {}
    },
    notify(message, type = 'success') {
      this.notice = message
      this.noticeType = type
      clearTimeout(this.noticeTimer)
      this.noticeTimer = setTimeout(() => { this.notice = '' }, 5000)
    },
  },
})
