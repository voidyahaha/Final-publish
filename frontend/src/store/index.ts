import { create } from 'zustand'
import { Job, User } from '../types'

interface AppState {
  user: User | null
  jobs: Job[]
  activeJobId: string | null
  sidebarCollapsed: boolean
  currentPage: string

  setUser: (user: User | null) => void
  setJobs: (jobs: Job[]) => void
  addJob: (job: Job) => void
  updateJob: (jobId: string, updates: Partial<Job>) => void
  removeJob: (jobId: string) => void
  setActiveJobId: (id: string | null) => void
  toggleSidebar: () => void
  setCurrentPage: (page: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  jobs: [],
  activeJobId: null,
  sidebarCollapsed: false,
  currentPage: 'dashboard',

  setUser: (user) => set({ user }),
  setJobs: (jobs) => set({ jobs }),
  addJob: (job) => set((state) => ({ jobs: [job, ...state.jobs] })),
  updateJob: (jobId, updates) =>
    set((state) => ({
      jobs: state.jobs.map((j) => (j.id === jobId ? { ...j, ...updates } : j)),
    })),
  removeJob: (jobId) =>
    set((state) => ({ jobs: state.jobs.filter((j) => j.id !== jobId) })),
  setActiveJobId: (id) => set({ activeJobId: id }),
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setCurrentPage: (page) => set({ currentPage: page }),
}))
