// Cloudflare Worker - 두레이 프록시
// 고정 URL: your-worker.workers.dev/slash
// 현재 터널 URL을 KV에서 읽어서 프록시

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // 현재 터널 URL (KV 또는 환경변수에서)
  // 수동으로 업데이트하거나 별도 엔드포인트로 업데이트
  const TUNNEL_URL = CURRENT_TUNNEL_URL || 'https://048fb10c7717d8.lhr.life'

  const url = new URL(request.url)
  const targetUrl = TUNNEL_URL + url.pathname

  // 요청 프록시
  const response = await fetch(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.method !== 'GET' ? await request.text() : null
  })

  return response
}
