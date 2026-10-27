/// <reference types="vite/client" />

declare module 'firebase/app' {
  export function initializeApp(config: any): any
}
declare module 'firebase/auth' {
  export const auth: any
  export class GoogleAuthProvider {
    setCustomParameters(params: any): void
  }
  export function getAuth(app?: any): any
  export function signInWithEmailAndPassword(auth: any, email: string, password: string): Promise<any>
  export function createUserWithEmailAndPassword(auth: any, email: string, password: string): Promise<any>
  export function signInWithPopup(auth: any, provider: any): Promise<any>
  export function signOut(auth: any): Promise<void>
  export function onAuthStateChanged(auth: any, callback: (user: any) => void): () => void
  export function updateProfile(user: any, profile: any): Promise<void>
  export function sendPasswordResetEmail(auth: any, email: string): Promise<void>
  export type User = any
}
declare module 'firebase/firestore' {
  export function getFirestore(app?: any): any
  export function doc(db: any, collection: string, id: string): any
  export function setDoc(ref: any, data: any): Promise<void>
  export function getDoc(ref: any): Promise<any>
  export function addDoc(ref: any, data: any): Promise<any>
  export function collection(db: any, path: string): any
  export function serverTimestamp(): any
  export function query(...args: any[]): any
  export function where(field: string, op: string, value: any): any
  export function orderBy(field: string, dir?: string): any
  export function onSnapshot(query: any, onNext: (snapshot: any) => void, onError?: (err: any) => void): () => void
}
declare module 'firebase/storage' {
  export function getStorage(app?: any): any
  export function ref(storage: any, path: string): any
  export function uploadBytesResumable(ref: any, file: any, metadata?: any): any
  export function getDownloadURL(ref: any): Promise<string>
  export type UploadTask = any
}

