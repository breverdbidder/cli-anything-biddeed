'use client';

export const AGENT_ID = 'agent_5301kzeg7pj8ezrbaarvkyyfgyd9';

const SIGNED_URL_ENDPOINT =
  'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/elevenlabs-signed-url';

// WebSocket event names verified against:
// https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets
const EL_TYPE_PING = 'ping';
const EL_TYPE_PONG = 'pong';
const EL_TYPE_AGENT_RESPONSE = 'agent_response';
const EL_TYPE_USER_INPUT = 'user_input';
const EL_TYPE_CONVERSATION_INIT = 'conversation_initiation_client_data';

import { useCallback, useEffect, useRef, useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

type ConnState = 'idle' | 'connecting' | 'open' | 'error' | 'closed';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [connState, setConnState] = useState<ConnState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const retryCountRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const connect = useCallback(async () => {
    if (!mountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    setConnState('connecting');
    setError(null);

    let signedUrl: string;
    try {
      const res = await fetch(SIGNED_URL_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: AGENT_ID }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Signed-URL fetch failed (${res.status}): ${text}`);
      }
      const data = await res.json();
      signedUrl = data.signed_url;
    } catch (err) {
      if (!mountedRef.current) return;
      setConnState('error');
      setError(`Could not reach agent: ${(err as Error).message}`);
      return;
    }

    if (!mountedRef.current) return;

    const ws = new WebSocket(signedUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnState('open');
      setError(null);
      retryCountRef.current = 0;
      setRetryCount(0);
      ws.send(JSON.stringify({ type: EL_TYPE_CONVERSATION_INIT }));
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        return;
      }

      const type = msg['type'] as string;

      if (type === EL_TYPE_PING) {
        const pingEvent = msg['ping_event'] as { event_id?: number } | undefined;
        ws.send(JSON.stringify({ type: EL_TYPE_PONG, event_id: pingEvent?.event_id ?? 0 }));
        return;
      }

      if (type === EL_TYPE_AGENT_RESPONSE) {
        const agentEvent = msg['agent_response_event'] as { agent_response?: string } | undefined;
        const text = agentEvent?.agent_response;
        if (text) {
          setMessages((prev) => [...prev, { role: 'assistant', content: text }]);
        }
        return;
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setConnState('error');
      setError('Connection error. Reconnecting…');
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      if (retryCountRef.current < MAX_RECONNECT_ATTEMPTS) {
        retryCountRef.current += 1;
        setRetryCount(retryCountRef.current);
        setConnState('closed');
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      } else {
        setConnState('error');
        setError('Connection lost. Click Reconnect to try again.');
      }
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || connState !== 'open' || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: EL_TYPE_USER_INPUT, user_input: text }));
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') sendMessage();
  };

  const handleReconnect = () => {
    retryCountRef.current = 0;
    setRetryCount(0);
    connect();
  };

  const statusLabel: Record<ConnState, string> = {
    idle: 'Initializing…',
    connecting: 'Connecting…',
    open: 'Connected',
    closed: `Reconnecting (${retryCount}/${MAX_RECONNECT_ATTEMPTS})…`,
    error: 'Disconnected',
  };

  const statusColor: Record<ConnState, string> = {
    idle: '#64748b',
    connecting: '#F59E0B',
    open: '#22c55e',
    closed: '#F59E0B',
    error: '#ef4444',
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: '#020617',
        fontFamily: 'Inter, sans-serif',
        color: '#e2e8f0',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          background: 'rgba(2,6,23,0.95)',
          borderBottom: '1px solid #1E3A5F',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #F59E0B, #f97316)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              fontSize: 18,
              color: 'white',
            }}
          >
            BD
          </div>
          <div>
            <div style={{ fontSize: 17, fontWeight: 600, color: 'white' }}>BidDeed.AI</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>Foreclosure Intelligence</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: statusColor[connState],
              display: 'inline-block',
            }}
          />
          <span style={{ fontSize: 13, color: statusColor[connState] }}>
            {statusLabel[connState]}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 20px',
        }}
      >
        {messages.length === 0 && connState === 'open' && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 16,
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'linear-gradient(135deg, #F59E0B, #f97316)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 900,
                fontSize: 24,
                color: 'white',
              }}
            >
              BD
            </div>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: 'white' }}>
              Foreclosure Intelligence
            </h2>
            <p style={{ margin: 0, color: '#94a3b8', maxWidth: 360 }}>
              Ask about upcoming auctions, max bid calculations, lien priority, and more.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: 10,
              marginBottom: 16,
              flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 14,
                background:
                  m.role === 'assistant'
                    ? 'linear-gradient(135deg, #F59E0B, #f97316)'
                    : '#334155',
              }}
            >
              {m.role === 'assistant' ? '🤖' : '👤'}
            </div>
            <div
              style={{
                maxWidth: '80%',
                padding: '12px 16px',
                borderRadius: 16,
                fontSize: 15,
                lineHeight: 1.6,
                background:
                  m.role === 'assistant' ? 'rgba(255,255,255,0.05)' : '#334155',
                border: m.role === 'assistant' ? '1px solid #1E3A5F' : 'none',
                color: m.role === 'assistant' ? '#e2e8f0' : '#f1f5f9',
              }}
            >
              {m.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Error / retry banner */}
      {error && (
        <div
          style={{
            padding: '10px 20px',
            background: 'rgba(239,68,68,0.1)',
            borderTop: '1px solid rgba(239,68,68,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <span style={{ color: '#f87171', fontSize: 13 }}>{error}</span>
          <button
            onClick={handleReconnect}
            style={{
              background: '#1E3A5F',
              border: '1px solid #F59E0B',
              color: '#F59E0B',
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Reconnect
          </button>
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: '16px 20px',
          background: 'rgba(2,6,23,0.95)',
          borderTop: '1px solid #1E3A5F',
          display: 'flex',
          gap: 10,
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            connState === 'open'
              ? 'Ask about properties, auctions, or liens…'
              : 'Connecting to agent…'
          }
          disabled={connState !== 'open'}
          style={{
            flex: 1,
            background: '#111827',
            border: '1px solid #1E3A5F',
            borderRadius: 12,
            padding: '14px 16px',
            color: 'white',
            fontSize: 15,
            outline: 'none',
            opacity: connState !== 'open' ? 0.5 : 1,
          }}
        />
        <button
          onClick={sendMessage}
          disabled={connState !== 'open' || !input.trim()}
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #F59E0B, #f97316)',
            border: 'none',
            cursor: connState === 'open' && input.trim() ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            opacity: connState !== 'open' || !input.trim() ? 0.4 : 1,
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
            <path d="M2 21l21-9L2 3v7l15 2-15 2v7z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
