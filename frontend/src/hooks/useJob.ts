import { useState, useEffect, useCallback, useRef } from 'react'
import {
  collection,
  query,
  where,
  onSnapshot,
  addDoc,
  serverTimestamp,
} from 'firebase/firestore'
import { db } from '../firebase'
import { Job, JobStatus } from '../types'
import { useAppStore } from '../store'
import { api } from '../services/api'

export function useJobs(userId: string | undefined) {
  const { setJobs, updateJob } = useAppStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!userId) {
      setJobs([])
      setLoading(false)
      return
    }

    const q = query(
      collection(db, 'jobs'),
      where('userId', '==', userId),
      // Sorting client-side avoids requiring a composite Firestore index.
    )

    const unsubscribe = onSnapshot(
      q,
      (snap: any) => {
        const jobs: Job[] = snap.docs.map((d: any) => {
          const data = d.data()
          return {
            id: d.id,
            ...data,
            createdAt: data.createdAt?.toDate() || new Date(),
            updatedAt: data.updatedAt?.toDate() || new Date(),
            completedAt: data.completedAt?.toDate(),
          } as Job
        })
        jobs.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())
        setJobs(jobs)
        setLoading(false)
      },
      () => {
        setLoading(false)
      }
    )

    return unsubscribe
  }, [userId, setJobs])

  return { loading }
}

export function useJobPolling(jobId: string | null) {
  const { updateJob } = useAppStore()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [pollingError, setPollingError] = useState<string | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (id: string) => {
      stopPolling()

      const poll = async () => {
        try {
          const data = await api.getJobStatus(id)
          if (data.job) {
            updateJob(id, {
              status: data.job.status as JobStatus,
              progress: data.job.progress || 0,
              statusMessage: data.job.statusMessage || data.job.status_message || '',
              stems: data.job.stems || [],
              mixedTrackUrl: data.job.mixedTrackUrl || data.job.mixed_track_url,
              bpm: data.job.bpm,
              error: data.job.error,
            })

            if (
              data.job.status === 'completed' ||
              data.job.status === 'failed'
            ) {
              stopPolling()
            }
          }
        } catch (e: any) {
          setPollingError(e.message)
        }
      }

      poll()
      intervalRef.current = setInterval(poll, 5000)
    },
    [stopPolling, updateJob]
  )

  useEffect(() => {
    if (jobId) startPolling(jobId)
    return stopPolling
  }, [jobId, startPolling, stopPolling])

  return { startPolling, stopPolling, pollingError }
}

export function useCreateJob() {
  const { addJob } = useAppStore()

  const createJob = useCallback(
    async (userId: string, type: Job['type'], originalFileName: string, originalStoragePath: string) => {
      const jobRef = await addDoc(collection(db, 'jobs'), {
        userId,
        type,
        status: 'queued',
        progress: 0,
        statusMessage: 'Job queued',
        originalFileName,
        originalStoragePath,
        stems: [],
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
      })

      const newJob: Job = {
        id: jobRef.id,
        userId,
        type,
        status: 'queued',
        progress: 0,
        statusMessage: 'Job queued',
        originalFileName,
        originalStoragePath,
        stems: [],
        createdAt: new Date(),
        updatedAt: new Date(),
      }

      addJob(newJob)
      return jobRef.id
    },
    [addJob]
  )

  return { createJob }
}
