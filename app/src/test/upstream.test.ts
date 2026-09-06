// @vitest-environment node
/**
 * The proxy's forwarder — what it sends upstream, and how it reports failure.
 *
 * Node environment (no DOM here), and `fetch` is stubbed: this pins the contract, not the
 * network. It was written after the same assertions were run once against a live
 * `mva-viz-api` on loopback (methodology 080), which is what confirmed the shape is right.
 *
 * The failure mapping is the part worth pinning. `src/api/client.ts` treats 502 and 504 as
 * "unreachable" and falls back to the committed fixtures, so a backend that is down degrades
 * the hosted dashboard to offline data instead of breaking every page — and an upstream 401
 * must never reach the browser as a 401, because that is the status the password gate uses.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { forward, isBareIpHost } from '../../server/upstream';

const ENV = {
  MVA_VIZ_API_URL: 'https://viz.example.org',
  MVA_VIZ_API_TOKEN: 'a-token',
};

function request(method = 'GET', body?: string): Request {
  return new Request('https://dash.example/api/overview', {
    method,
    body,
    headers: { accept: 'application/json' },
  });
}

function upstreamReply(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('forward', () => {
  it('sends the path, the query and the token to the configured backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(upstreamReply(200, { data: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await forward(request(), ENV, '/api/panel/genes', '?gene=BUB1B');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://viz.example.org/api/panel/genes?gene=BUB1B');
    expect((init.headers as Record<string, string>)['X-API-Key']).toBe('a-token');
  });

  it('does not double the slash when the configured URL has a trailing one', async () => {
    const fetchMock = vi.fn().mockResolvedValue(upstreamReply(200, { data: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await forward(request(), { ...ENV, MVA_VIZ_API_URL: 'https://viz.example.org//' }, '/health');

    expect(fetchMock.mock.calls[0][0]).toBe('https://viz.example.org/health');
  });

  it('never forwards the browser cookie upstream', async () => {
    const fetchMock = vi.fn().mockResolvedValue(upstreamReply(200, { data: [] }));
    vi.stubGlobal('fetch', fetchMock);
    const withCookie = new Request('https://dash.example/api/overview', {
      headers: { accept: 'application/json', cookie: 'mva_dash=secret' },
    });

    await forward(withCookie, ENV, '/api/overview');

    const sent = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(Object.keys(sent).map((k) => k.toLowerCase())).not.toContain('cookie');
  });

  it('buffers a POST body rather than streaming it', async () => {
    const fetchMock = vi.fn().mockResolvedValue(upstreamReply(200, { data: {} }));
    vi.stubGlobal('fetch', fetchMock);

    await forward(request('POST', '{"lane":1}'), ENV, '/api/probe/scan');

    expect(fetchMock.mock.calls[0][1].body).toBe('{"lane":1}');
  });

  it('forces no-store on every reply, whatever upstream said', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          upstreamReply(200, { data: [] }, { 'cache-control': 'public, max-age=3600' }),
        ),
    );

    const reply = await forward(request(), ENV, '/api/panel/locus');

    expect(reply.headers.get('cache-control')).toBe('no-store, private');
  });

  it('drops a Set-Cookie the upstream tried to send', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(upstreamReply(200, { data: [] }, { 'set-cookie': 'a=b' })),
    );

    expect((await forward(request(), ENV, '/api/overview')).headers.get('set-cookie')).toBeNull();
  });

  it('turns an upstream 401 into a 502 that names the misconfiguration', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(upstreamReply(401, { detail: 'missing or wrong X-API-Key' })),
    );

    const reply = await forward(request(), ENV, '/api/overview');

    // Never 401: that is the status the password gate uses, and the browser would show a
    // login page for what is actually a wrong token in the project settings.
    expect(reply.status).toBe(502);
    expect(await reply.json()).toEqual({
      detail: 'the viz API rejected this deployment: MVA_VIZ_API_TOKEN is wrong',
    });
  });

  it('reports an unreachable backend as 502', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')));

    expect((await forward(request(), ENV, '/api/overview')).status).toBe(502);
  });

  it('reports a timeout as 504, distinct from unreachable', async () => {
    const timeout = Object.assign(new Error('timed out'), { name: 'TimeoutError' });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(timeout));

    expect((await forward(request(), ENV, '/api/overview')).status).toBe(504);
  });

  it('answers 503 naming the variable when the backend URL is not configured', async () => {
    const reply = await forward(request(), {}, '/api/overview');

    expect(reply.status).toBe(503);
    expect(((await reply.json()) as { detail: string }).detail).toContain('MVA_VIZ_API_URL');
  });

  it('passes the upstream status and its own error body through', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(upstreamReply(404, { detail: 'unknown gene BRCA9' })),
    );

    const reply = await forward(request(), ENV, '/api/panel/genes');

    expect(reply.status).toBe(404);
    expect(await reply.json()).toEqual({ detail: 'unknown gene BRCA9' });
  });
});

describe('isBareIpHost', () => {
  it('spots the shape the Edge runtime refuses to fetch', () => {
    expect(isBareIpHost('http://38.242.217.131:8900')).toBe(true);
    expect(isBareIpHost('https://10.0.0.1')).toBe(true);
    expect(isBareIpHost('http://[2001:db8::1]:8900')).toBe(true);
  });

  it('leaves a hostname alone, including one that merely contains digits', () => {
    expect(isBareIpHost('http://vmi2938918.contaboserver.net:8900')).toBe(false);
    expect(isBareIpHost('https://viz.example.org')).toBe(false);
    expect(isBareIpHost('http://localhost:8900')).toBe(false);
  });

  it('does not throw on a value that is not a URL', () => {
    expect(isBareIpHost('not a url')).toBe(false);
    expect(isBareIpHost('')).toBe(false);
  });

  it('is refused before the fetch, with a reply that says what to change', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const reply = await forward(request(), { MVA_VIZ_API_URL: 'http://1.2.3.4:8900' }, '/api/x');

    expect(reply.status).toBe(503);
    expect(((await reply.json()) as { detail: string }).detail).toContain('bare IP');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
