/**
 * Proxy API for SIP agent management
 * Forwards requests to livekit_agent:8089/sip/agents
 *
 * Handles all SIP API paths:
 * - GET/POST  /api/sip/agents        → /sip/agents
 * - GET/PATCH /api/sip/agents/hvac   → /sip/agents/hvac
 * - DELETE    /api/sip/agents/hvac   → /sip/agents/hvac
 */
import { NextRequest, NextResponse } from 'next/server';

const SIP_API_BASE =
  process.env.SIP_API_BASE ||
  (process.env.NODE_ENV === 'production' ? 'http://sip_api:8089' : 'http://localhost:8089');

function getSIPPath(pathname: string): string {
  // Extract path after /api/sip/
  const match = pathname.match(/^\/api\/sip(.*)$/);
  if (!match) return '/agents';

  const pathPart = match[1];
  if (!pathPart || pathPart === '') return '/agents';

  // Paths should already include /agents or agent_id
  // /api/sip/agents → /agents
  // /api/sip/agents/hvac → /agents/hvac
  return pathPart;
}

async function handleRequest(request: NextRequest, method: string) {
  try {
    const authHeader = request.headers.get('authorization');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const url = new URL(request.url);
    const sipPath = getSIPPath(url.pathname);
    const targetUrl = `${SIP_API_BASE}/sip${sipPath}${url.search}`;

    console.log(`[SIP API] ${method} ${url.pathname} → ${targetUrl}`);

    const options: RequestInit = {
      method,
      headers,
    };

    if (['POST', 'PATCH'].includes(method)) {
      try {
        const body = await request.json();
        options.body = JSON.stringify(body);
      } catch {
        // No body
      }
    }

    const response = await fetch(targetUrl, options);
    const contentType = response.headers.get('content-type');

    let data;
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[SIP API] Error:', error);
    return NextResponse.json(
      {
        error: 'Failed to reach SIP API',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 503 }
    );
  }
}

export async function GET(request: NextRequest) {
  return handleRequest(request, 'GET');
}

export async function POST(request: NextRequest) {
  return handleRequest(request, 'POST');
}

export async function PATCH(request: NextRequest) {
  return handleRequest(request, 'PATCH');
}

export async function DELETE(request: NextRequest) {
  return handleRequest(request, 'DELETE');
}
