import { defineStore } from 'pinia'
import { api, clearToken, getToken, setToken } from './api'

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
      if (getToken()) {
        try { this.user = await api('/auth/me') } catch { this.clear() }
      }
      this.loaded = true
    },
    async authenticate(path, data) {
      await this.accept(await api('/auth/' + path, { method: 'POST', data }))
    },
    async accept(response) {
      setToken(response.access_token)
      this.user = response.user
      this.loaded = true
    },
    clear() {
      clearToken()
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
