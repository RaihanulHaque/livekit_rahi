'use client';

import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionView } from '@/components/app/session-view';
import { WelcomeView } from '@/components/app/welcome-view';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(SessionView);

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
  onBeforeStart?: () => void;
}

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
  onBeforeStart,
}: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const handleStart = () => {
    onBeforeStart?.();
    start();
  };

  return (
    <AnimatePresence mode="wait">
      {/* Welcome view */}
      {!isConnected && (
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
        />
      )}
      {/* Session view */}
      {isConnected && (
        <MotionSessionView key="session-view" {...VIEW_MOTION_PROPS} appConfig={appConfig} />
      )}
    </AnimatePresence>
  );
}
