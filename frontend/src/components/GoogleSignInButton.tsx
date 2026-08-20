import { useEffect, useRef } from 'react'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: { client_id: string; callback: (response: { credential: string }) => void }) => void
          renderButton: (element: HTMLElement, options: Record<string, string | number>) => void
        }
      }
    }
  }
}

interface Props {
  onCredential: (credential: string) => void
}

export default function GoogleSignInButton({ onCredential }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

  useEffect(() => {
    if (!clientId || !containerRef.current) return

    const initialize = () => {
      if (!window.google || !containerRef.current) return
      containerRef.current.innerHTML = ''
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: ({ credential }) => onCredential(credential),
      })
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        shape: 'pill',
        text: 'continue_with',
        width: 320,
      })
    }

    if (window.google) {
      initialize()
      return
    }

    const existing = document.querySelector<HTMLScriptElement>('script[data-weam-google]')
    if (existing) {
      existing.addEventListener('load', initialize)
      return () => existing.removeEventListener('load', initialize)
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.dataset.weamGoogle = 'true'
    script.addEventListener('load', initialize)
    document.head.appendChild(script)
    return () => script.removeEventListener('load', initialize)
  }, [clientId, onCredential])

  if (!clientId) {
    return <p className="google-note">Google Sign-In يظهر بعد إضافة VITE_GOOGLE_CLIENT_ID.</p>
  }

  return <div className="google-button" ref={containerRef} />
}
