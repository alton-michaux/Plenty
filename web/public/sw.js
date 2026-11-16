// Receives Android share-sheet posts (see share_target in manifest.webmanifest).
// Only POST /share-target is handled; every other request goes to the network untouched.
//
// Why here and not on the server: the share arrives as a POST navigation, and whether the
// SameSite=Lax session cookie rides along on one isn't something to bet on. So the worker
// parks the shared text and images in Cache Storage and redirects to /share, which reads
// them same-origin, signed in. (The server also answers POST /share-target, for the rare
// launch before the worker is active, with a redirect to /share?missed=1.)

const INBOX = 'share-inbox'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method === 'POST' && url.pathname === '/share-target') {
    event.respondWith(receiveShare(event.request))
  }
})

async function receiveShare(request) {
  try {
    const form = await request.formData()
    const cache = await caches.open(INBOX)
    for (const key of await cache.keys()) await cache.delete(key) // one share at a time
    const files = form.getAll('images').filter((f) => typeof f !== 'string')
    const meta = {
      title: form.get('title') || '',
      text: form.get('text') || '',
      url: form.get('url') || '',
      files: [],
      received_at: new Date().toISOString(),
    }
    for (const [i, file] of files.entries()) {
      const key = `/share-inbox/file-${i}`
      await cache.put(key, new Response(file, { headers: { 'Content-Type': file.type || 'application/octet-stream' } }))
      meta.files.push({ key, name: file.name, type: file.type, size: file.size })
    }
    await cache.put('/share-inbox/meta', new Response(JSON.stringify(meta), { headers: { 'Content-Type': 'application/json' } }))
    return Response.redirect('/share', 303)
  } catch {
    return Response.redirect('/share?error=1', 303)
  }
}
