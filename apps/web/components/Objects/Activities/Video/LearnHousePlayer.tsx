'use client'

import React, { useEffect, useRef, useState } from 'react'
import 'video.js/dist/video-js.css'
import './player-controls.css'
import { shouldSendHlsCredentials, type CaptionTrack } from './videoSource'

const SEEK_SECONDS = 15
const MOBILE_SEEK_SECONDS = 10
const DOUBLE_TAP_MS = 300

/**
 * Double-tap-to-seek zones over the left/right thirds of the video, the
 * touch-control pattern shared by YouTube/Vidstack/Plyr: a single tap
 * toggles play/pause (same as a desktop click), a second tap within
 * DOUBLE_TAP_MS in the SAME zone seeks ±10s and flashes an icon. Touch-only
 * (`pointer: coarse`) — desktop mouse users keep Video.js's own native
 * click/hover handling untouched. Returns a cleanup function.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function attachMobileSeekZones(player: any, container: HTMLElement): () => void {
  if (typeof window === 'undefined') return () => {}
  let isCoarsePointer = false
  try {
    isCoarsePointer = window.matchMedia('(pointer: coarse)').matches
  } catch {
    isCoarsePointer = false
  }
  if (!isCoarsePointer) return () => {}

  const ARROW_PATHS: Record<'left' | 'right', string> = {
    left: "<path d='M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8'/><path d='M3 3v5h5'/>",
    right: "<path d='M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8'/><path d='M21 3v5h-5'/>",
  }

  const cleanupFns: Array<() => void> = []

  ;(['left', 'right'] as const).forEach((side) => {
    const zone = document.createElement('div')
    zone.className = `lh-seek-zone lh-seek-zone-${side}`

    const flash = document.createElement('div')
    flash.className = `lh-seek-flash lh-seek-flash-${side}`
    flash.innerHTML =
      `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" ` +
      `stroke-linecap="round" stroke-linejoin="round">${ARROW_PATHS[side]}</svg>` +
      `<span>${MOBILE_SEEK_SECONDS}</span>`

    container.appendChild(zone)
    container.appendChild(flash)

    let lastTapAt = 0
    let singleTapTimer: ReturnType<typeof setTimeout> | null = null
    let flashHideTimer: ReturnType<typeof setTimeout> | null = null
    const delta = side === 'left' ? -MOBILE_SEEK_SECONDS : MOBILE_SEEK_SECONDS

    const showFlash = () => {
      flash.classList.add('lh-flash-visible')
      if (flashHideTimer) clearTimeout(flashHideTimer)
      flashHideTimer = setTimeout(() => flash.classList.remove('lh-flash-visible'), 500)
    }

    const onTap = (e: Event) => {
      e.preventDefault()
      const now = Date.now()
      if (now - lastTapAt < DOUBLE_TAP_MS) {
        lastTapAt = 0
        if (singleTapTimer) {
          clearTimeout(singleTapTimer)
          singleTapTimer = null
        }
        const cur = player.currentTime() ?? 0
        const dur = player.duration() || Infinity
        player.currentTime(Math.max(0, Math.min(dur, cur + delta)))
        showFlash()
      } else {
        lastTapAt = now
        if (singleTapTimer) clearTimeout(singleTapTimer)
        singleTapTimer = setTimeout(() => {
          singleTapTimer = null
          if (player.paused()) player.play()
          else player.pause()
        }, DOUBLE_TAP_MS)
      }
    }

    zone.addEventListener('pointerup', onTap)
    cleanupFns.push(() => {
      zone.removeEventListener('pointerup', onTap)
      if (singleTapTimer) clearTimeout(singleTapTimer)
      if (flashHideTimer) clearTimeout(flashHideTimer)
      zone.remove()
      flash.remove()
    })
  })

  return () => cleanupFns.forEach((fn) => fn())
}

/* Register ±15s seek-button components once (Video.js Button API — no plugin). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function registerSeekButtons(videojs: any) {
  const Button = videojs.getComponent('Button')
  const make = (name: string, cls: string, label: string, delta: number) => {
    if (videojs.getComponent(name)) return
    class SeekButton extends Button {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      constructor(player: any, options: any) {
        super(player, options)
        this.controlText(label)
        this.addClass(cls)
      }
      handleClick() {
        const cur = this.player().currentTime() ?? 0
        const dur = this.player().duration() || Infinity
        this.player().currentTime(Math.max(0, Math.min(dur, cur + delta)))
      }
    }
    videojs.registerComponent(name, SeekButton)
  }
  make('LhSeekBack', 'vjs-seek-back-15', `Rewind ${SEEK_SECONDS} seconds`, -SEEK_SECONDS)
  make('LhSeekForward', 'vjs-seek-forward-15', `Forward ${SEEK_SECONDS} seconds`, SEEK_SECONDS)
}

/* A compact touch-only overflow menu keeps the mobile control bar usable. */
function registerMobileMoreButton(videojs: any) {
  const Button = videojs.getComponent('Button')
  if (videojs.getComponent('LhMobileMore')) return

  class MobileMoreButton extends Button {
    constructor(player: any, options: any) {
      super(player, options)
      this.controlText('More video options')
      this.addClass('lh-mobile-more')
    }

    handleClick() {
      const player = this.player()
      const root = player.el() as HTMLElement
      let menu = root.querySelector('.lh-mobile-more-menu') as HTMLElement | null

      if (menu) {
        menu.remove()
        return
      }

      menu = document.createElement('div')
      menu.className = 'lh-mobile-more-menu'
      menu.setAttribute('role', 'menu')
      menu.setAttribute('aria-label', 'More video options')

      const title = document.createElement('div')
      title.className = 'lh-mobile-more-title'
      title.textContent = 'Opciones'
      menu.appendChild(title)

      const addSection = (label: string, values: string[], onSelect: (value: string) => void) => {
        const section = document.createElement('div')
        section.className = 'lh-mobile-more-section'
        const heading = document.createElement('div')
        heading.className = 'lh-mobile-more-label'
        heading.textContent = label
        section.appendChild(heading)
        values.forEach((value) => {
          const option = document.createElement('button')
          option.type = 'button'
          option.className = 'lh-mobile-more-option'
          option.textContent = value
          option.addEventListener('click', () => {
            onSelect(value)
            menu?.remove()
          })
          section.appendChild(option)
        })
        menu?.appendChild(section)
      }

      const tracks = player.textTracks?.()
      if (tracks && tracks.length) {
        const captions = ['Subtítulos: apagados']
        for (let index = 0; index < tracks.length; index += 1) {
          if (tracks[index].kind === 'subtitles') captions.push(tracks[index].label || tracks[index].language)
        }
        addSection('Subtítulos', captions, (value) => {
          for (let index = 0; index < tracks.length; index += 1) {
            tracks[index].mode = value === 'Subtítulos: apagados' ? 'disabled' : tracks[index].label === value ? 'showing' : 'disabled'
          }
        })
      }

      root.appendChild(menu)
    }
  }

  videojs.registerComponent('LhMobileMore', MobileMoreButton)
}

interface VideoDetails {
  startTime?: number
  endTime?: number | null
  autoplay?: boolean
  muted?: boolean
}

export interface ThumbnailsConfig {
  /** Absolute URL of the sprite sheet. */
  url: string
  interval: number
  width: number
  height: number
  columns: number
  rows: number
}

interface LearnHousePlayerProps {
  src: string
  /** When true, `src` is an HLS master playlist (.m3u8). */
  isHls?: boolean
  /** Progressive MP4 URL to fall back to if the HLS source errors. */
  fallbackSrc?: string
  details?: VideoDetails
  onReady?: () => void
  poster?: string
  /** Hover-scrub preview sprite config (HLS only). */
  thumbnails?: ThumbnailsConfig | null
  /** Ready WebVTT caption tracks to attach (subtitles/CC menu). */
  captions?: CaptionTrack[]
}

/**
 * Video.js player with adaptive HLS, quality selection and mobile controls.
 *
 * Video.js and its plugins are imported dynamically inside an effect so nothing
 * touches `window`/`document` during SSR.
 */
const LearnHousePlayer: React.FC<LearnHousePlayerProps> = ({
  src,
  isHls = false,
  fallbackSrc,
  details,
  onReady,
  poster,
  thumbnails,
  captions,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<any>(null)
  const detachSeekZonesRef = useRef<(() => void) | null>(null)
  const fellBackRef = useRef(false)
  const captionBlobUrls = useRef<string[]>([])
  const retriedRef = useRef(false)
  const [loadError, setLoadError] = useState(false)
  const [reloadNonce, setReloadNonce] = useState(0)

  useEffect(() => {
    let disposed = false
    let removeFullscreenHandler: (() => void) | null = null
    fellBackRef.current = false
    retriedRef.current = false
    setLoadError(false)

    ;(async () => {
      const { default: videojs } = await import('video.js')
      await import('videojs-sprite-thumbnails')
      if (disposed || !containerRef.current) return

      registerSeekButtons(videojs)
      registerMobileMoreButton(videojs)


      // Send the auth cookie only to our API playlist endpoint (RBAC); presigned
      // R2 segment requests must stay uncredentialed (R2 CORS).
       
      const Vhs = (videojs as any).Vhs
      if (Vhs && !Vhs.__lhBeforeRequestSet) {
         
        Vhs.xhr.beforeRequest = (options: any) => {
          if (options?.uri && shouldSendHlsCredentials(options.uri)) {
            options.withCredentials = true
          }
          return options
        }
        Vhs.__lhBeforeRequestSet = true
      }

      const videoEl = document.createElement('video-js')
      videoEl.classList.add('vjs-big-play-centered')
      videoEl.setAttribute('playsinline', '')
      containerRef.current.appendChild(videoEl)

      const player = videojs(videoEl, {
        controls: true,
        // fill (not fluid) so the player always fills its aspect-video parent and
        // the control bar is visible IMMEDIATELY — even before video metadata
        // loads or if the source errors. `fluid` sized from metadata, so a slow/
        // broken source left the player collapsed with no visible controls.
        fill: true,
        preload: 'metadata',
        poster: poster || undefined,
        autoplay: !!details?.autoplay,
        muted: !!details?.muted,
        sources: [{ src, type: isHls ? 'application/x-mpegURL' : 'video/mp4' }],
        html5: {
          vhs: { overrideNative: true },
          nativeAudioTracks: false,
          nativeVideoTracks: false,
        },
      }, () => {
        onReady?.()
      })
      playerRef.current = player

      // Mobile browsers may enter fullscreen while the device remains in
      // portrait. Lock the video to landscape when supported and release the
      // lock as soon as fullscreen ends. The CSS fallback handles browsers
      // that do not expose Screen Orientation Lock.
      const lockLandscapeOnFullscreen = async () => {
        const isTouch = window.matchMedia?.('(pointer: coarse)').matches
        if (!isTouch) return
        try {
          const video = player.el().querySelector('video') as HTMLVideoElement | null
          const isLandscapeVideo = !video || !video.videoWidth || video.videoWidth >= video.videoHeight
          if (player.isFullscreen() && isLandscapeVideo) {
            await screen.orientation?.lock?.('landscape')
          } else {
            screen.orientation?.unlock?.()
          }
        } catch {
          // iOS Safari does not expose orientation locking; CSS handles it.
        }
      }
      player.on('fullscreenchange', lockLandscapeOnFullscreen)
      removeFullscreenHandler = () => player.off('fullscreenchange', lockLandscapeOnFullscreen)

      // Durable, layered recovery so the user is NEVER left with a dead player:
      //   1. HLS source errors/stalls -> switch to the progressive MP4
      //   2. still fails               -> one silent reload of the current source
      //   3. still fails               -> clean "couldn't load" + Retry overlay
      // A watchdog also covers sources that HANG without firing 'error' (e.g. an
      // HLS master that loads but whose segments never arrive).
      const LOAD_WATCHDOG_MS = 15000
      let metaLoaded = false
      let watchdog: ReturnType<typeof setTimeout> | null = null
      const clearWatchdog = () => {
        if (watchdog) clearTimeout(watchdog)
        watchdog = null
      }
      const armWatchdog = () => {
        clearWatchdog()
        watchdog = setTimeout(() => {
          if (!metaLoaded && !disposed) recover()
        }, LOAD_WATCHDOG_MS)
      }
      const reloadCurrent = (nextSrc?: { src: string; type: string }) => {
        const resume = player.currentTime?.() ?? 0
        metaLoaded = false
        try {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ;(player as any).error(null) // clear the error overlay before retrying
          if (nextSrc) player.src(nextSrc)
          player.load()
          player.one('loadedmetadata', () => {
            try { if (resume > 0) player.currentTime(resume) } catch { /* noop */ }
          })
          player.play?.()
          armWatchdog()
        } catch {
          /* best-effort */
        }
      }
      const recover = () => {
        if (disposed) return
        clearWatchdog()
        if (isHls && fallbackSrc && !fellBackRef.current) {
          fellBackRef.current = true
          reloadCurrent({ src: fallbackSrc, type: 'video/mp4' })
          return
        }
        if (!retriedRef.current) {
          retriedRef.current = true
          reloadCurrent()
          return
        }
        setLoadError(true)
      }
      player.on('error', recover)
      player.one('loadedmetadata', () => {
        metaLoaded = true
        clearWatchdog()
      })
      player.on('dispose', clearWatchdog)
      armWatchdog()

      // Insert the ±15s seek buttons right after the play button.
      try {
        const bar = player.getChild('ControlBar')
        if (bar && !bar.getChild('LhSeekBack')) {
          bar.addChild('LhSeekBack', {}, 1)
          bar.addChild('LhSeekForward', {}, 2)
        }
        if (bar && captions?.length && !bar.getChild('LhMobileMore')) {
          bar.addChild('LhMobileMore', {}, bar.children().length)
        }
      } catch {
        /* seek buttons are best-effort */
      }

      // Touch-only double-tap-to-seek zones (see attachMobileSeekZones).
      try {
        detachSeekZonesRef.current = attachMobileSeekZones(player, player.el() as HTMLElement)
      } catch {
        /* best-effort */
      }

      // Casual-download deterrents (cosmetic — not real protection; the segments
      // are AES-128 encrypted server-side and the raw MP4 is locked once HLS is
      // ready — see stream.py — for the actual bar-raising). Picture-in-picture
      // is intentionally LEFT ENABLED (users asked for it).
      try {
        const techEl = player.el().querySelector('video') as HTMLVideoElement | null
        if (techEl) {
          techEl.setAttribute('controlsList', 'nodownload')
          // Stops the "drag the <video> element onto the desktop to save it"
          // affordance some browsers expose even with controlsList=nodownload.
          techEl.addEventListener('dragstart', (e: Event) => e.preventDefault())
        }
        player.el().addEventListener('contextmenu', (e: Event) => e.preventDefault())
      } catch {
        /* best-effort */
      }

      // Hover-scrub preview thumbnails.
      if (thumbnails?.url) {
        try {
           
          ;(player as any).spriteThumbnails?.({
            url: thumbnails.url,
            width: thumbnails.width,
            height: thumbnails.height,
            columns: thumbnails.columns,
            rows: thumbnails.rows,
            interval: thumbnails.interval,
            // downlink:0 disables the plugin's bandwidth gate, which otherwise
            // SILENTLY hides thumbnails whenever the browser reports
            // connection.downlink < 1.5 Mbps (its default).
            downlink: 0,
          })
        } catch {
          /* thumbnails are best-effort */
        }
      }

      // Captions: fetch each ready VTT with credentials (RBAC) and attach it as a
      // subtitles text track. Fetching to a blob (instead of a <track src>) avoids
      // cross-origin credential limitations on private courses.
      if (captions && captions.length) {
        captions.forEach(async (track) => {
          try {
            const res = await fetch(track.url, { credentials: 'include' })
            if (!res.ok || disposed) return
            const vtt = await res.text()
            const blobUrl = URL.createObjectURL(new Blob([vtt], { type: 'text/vtt' }))
            captionBlobUrls.current.push(blobUrl)
            if (disposed) {
              URL.revokeObjectURL(blobUrl)
              return
            }
            player.addRemoteTextTrack(
              { kind: 'subtitles', src: blobUrl, srclang: track.code, label: track.label },
              false
            )
          } catch {
            /* captions are best-effort */
          }
        })
      }

      // Honor per-video start/stop bounds. video.js's currentTime() getter is
      // typed number | undefined, so coalesce before comparing.
      const startTime = details?.startTime
      if (startTime) {
        player.one('loadedmetadata', () => player.currentTime(startTime))
      }
      const endTime = details?.endTime
      if (endTime) {
        player.on('timeupdate', () => {
          if ((player.currentTime() ?? 0) >= endTime) player.pause()
        })
      }
    })()

    return () => {
      disposed = true
      if (detachSeekZonesRef.current) {
        detachSeekZonesRef.current()
        detachSeekZonesRef.current = null
      }
      if (playerRef.current) {
        try {
          removeFullscreenHandler?.()
          screen.orientation?.unlock?.()
        } catch {
          /* orientation lock is best-effort */
        }
        playerRef.current.dispose()
        playerRef.current = null
      }
      captionBlobUrls.current.forEach((u) => URL.revokeObjectURL(u))
      captionBlobUrls.current = []
    }
    // Rebuild when the source changes, or when the user hits Retry (reloadNonce).
  }, [src, isHls, fallbackSrc, reloadNonce])

  return (
    // h-full chain is required for the player's `fill` mode to size to the
    // aspect-video parent (otherwise the video collapses to zero height).
    <div className="learnhouse-player relative w-full h-full" data-vjs-player>
      <div ref={containerRef} className="w-full h-full" />
      {loadError && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-black/80 p-4 text-center text-white">
          <p className="text-sm opacity-90">This video couldn’t be loaded.</p>
          <button
            type="button"
            onClick={() => {
              setLoadError(false)
              setReloadNonce((n) => n + 1)
            }}
            className="rounded-md bg-white/15 px-4 py-1.5 text-sm font-medium transition-colors hover:bg-white/25"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}

export default LearnHousePlayer
