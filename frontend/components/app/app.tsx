'use client';

import { useMemo, useState } from 'react';
import { TokenSource } from 'livekit-client';
import {
  RoomAudioRenderer,
  SessionProvider,
  StartAudio,
  useSession,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT });
  useAgentErrors();

  return null;
}

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  const [stt, setStt] = useState('deepgram');
  const [llm, setLlm] = useState('langchain');
  const [tts, setTts] = useState('elevenlabs');

  const tokenSource = useMemo(() => {
    return TokenSource.custom(async () => {
      const isSandbox = typeof process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT === 'string';
      const endpoint = isSandbox
        ? new URL(process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT!, window.location.origin).toString()
        : '/api/connection-details';

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (isSandbox && appConfig.sandboxId) {
        headers['X-Sandbox-Id'] = appConfig.sandboxId;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          stt,
          llm,
          tts,
          room_config: appConfig.agentName
            ? { agents: [{ agent_name: appConfig.agentName }] }
            : undefined,
        }),
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(`Failed to fetch connection details: ${message}`);
      }
      return await res.json();
    });
  }, [appConfig, stt, llm, tts]);

  const session = useSession(tokenSource);

  return (
    <SessionProvider session={session}>
      <AppSetup />
      <main className="grid h-svh grid-cols-1 place-content-center">
        <ViewController
          appConfig={appConfig}
          stt={stt}
          setStt={setStt}
          llm={llm}
          setLlm={setLlm}
          tts={tts}
          setTts={setTts}
        />
      </main>
      <StartAudio label="Start Audio" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}
