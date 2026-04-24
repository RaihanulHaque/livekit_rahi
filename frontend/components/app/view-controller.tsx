'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import { Gear } from '@phosphor-icons/react';
import type { AppConfig } from '@/app-config';
import { SessionView } from '@/components/app/session-view';
import { SipManagementView } from '@/components/app/sip-management-view';
import { WelcomeView } from '@/components/app/welcome-view';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(SessionView);
const MotionSipManagementView = motion.create(SipManagementView);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

interface ViewControllerProps {
  appConfig: AppConfig;
  stt: string;
  setStt: (v: string) => void;
  llm: string;
  setLlm: (v: string) => void;
  tts: string;
  setTts: (v: string) => void;
  systemPrompt: string;
  setSystemPrompt: (v: string) => void;
  promptMode: 'custom' | 'agent_id';
  setPromptMode: (v: 'custom' | 'agent_id') => void;
  agentId: string;
  setAgentId: (v: string) => void;
  onBeforeStart?: () => void;
}

type ViewMode = 'welcome' | 'session' | 'sip';

export function ViewController({
  appConfig,
  stt,
  setStt,
  llm,
  setLlm,
  tts,
  setTts,
  systemPrompt,
  setSystemPrompt,
  promptMode,
  setPromptMode,
  agentId,
  setAgentId,
  onBeforeStart,
}: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const [viewMode, setViewMode] = useState<ViewMode>('welcome');
  const [jwtToken, setJwtToken] = useState<string>();

  // Get JWT token from session context if available
  useEffect(() => {
    // Try to extract JWT from connection details
    const getToken = async () => {
      try {
        const res = await fetch('/api/connection-details', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            stt,
            llm,
            tts,
            system_prompt: systemPrompt || null,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.participantToken) {
            setJwtToken(data.participantToken);
          }
        }
      } catch {
        // Silently fail - JWT is optional for demo
      }
    };
    getToken();
  }, [stt, llm, tts, systemPrompt]);

  const handleStart = () => {
    onBeforeStart?.();
    start();
    setViewMode('session');
  };

  return (
    <div className="relative">
      {/* SIP Management Tab Button */}
      {!isConnected && viewMode !== 'sip' && (
        <button
          onClick={() => setViewMode('sip')}
          className="hover:bg-muted absolute top-4 right-4 z-50 rounded-lg p-2 transition-colors"
          title="SIP Phone Management"
        >
          <Gear className="text-muted-foreground hover:text-foreground h-5 w-5" />
        </button>
      )}

      {/* Back from SIP Button */}
      {viewMode === 'sip' && (
        <button
          onClick={() => setViewMode('welcome')}
          className="bg-muted hover:bg-muted-foreground/20 absolute top-4 right-4 z-50 rounded-lg px-3 py-1 text-sm transition-colors"
        >
          Back
        </button>
      )}

      <AnimatePresence mode="wait">
        {/* Welcome view */}
        {!isConnected && viewMode === 'welcome' && (
          <MotionWelcomeView
            key="welcome"
            {...VIEW_MOTION_PROPS}
            startButtonText={appConfig.startButtonText}
            onStartCall={handleStart}
            stt={stt}
            setStt={setStt}
            llm={llm}
            setLlm={setLlm}
            tts={tts}
            setTts={setTts}
            systemPrompt={systemPrompt}
            setSystemPrompt={setSystemPrompt}
            promptMode={promptMode}
            setPromptMode={setPromptMode}
            agentId={agentId}
            setAgentId={setAgentId}
          />
        )}

        {/* SIP Management view */}
        {!isConnected && viewMode === 'sip' && (
          <MotionSipManagementView
            key="sip-management"
            {...VIEW_MOTION_PROPS}
            jwtToken={jwtToken}
          />
        )}

        {/* Session view */}
        {isConnected && (
          <MotionSessionView key="session-view" {...VIEW_MOTION_PROPS} appConfig={appConfig} />
        )}
      </AnimatePresence>
    </div>
  );
}
