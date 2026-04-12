'use client';

import { useCallback, useEffect, useState } from 'react';
import { Phone, Plus, Trash, WarningCircle } from '@phosphor-icons/react';
import { Button } from '@/components/livekit/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/livekit/select';

interface SIPAgent {
  agent_id: string;
  local_number: string;
  sip_number: string;
  trunk_id: string;
  status: string;
  created_at: number;
}

export const SipManagementView = ({
  ref,
  jwtToken,
  ...props
}: React.ComponentProps<'div'> & { jwtToken?: string }) => {
  const [agents, setAgents] = useState<SIPAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    agent_id: '',
    local_number: '',
    sip_number: '',
    system_prompt: '',
    stt: 'deepgram',
    llm: 'openai',
    tts: 'elevenlabs',
  });

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const headers: Record<string, string> = {};
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const res = await fetch('/api/sip/agents', { headers });
      if (!res.ok) throw new Error('Failed to fetch agents');
      const data = await res.json();
      setAgents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [jwtToken]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const handleAddAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const res = await fetch('/api/sip/agents', {
        method: 'POST',
        headers,
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err);
      }

      setFormData({
        agent_id: '',
        local_number: '',
        sip_number: '',
        system_prompt: '',
        stt: 'deepgram',
        llm: 'openai',
        tts: 'elevenlabs',
      });
      setShowAddForm(false);
      await fetchAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add agent');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(`Delete agent ${agentId}?`)) return;

    setLoading(true);
    setError('');

    try {
      const headers: Record<string, string> = {};
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const res = await fetch(`/api/sip/agents/${agentId}`, {
        method: 'DELETE',
        headers,
      });

      if (!res.ok) throw new Error('Failed to delete agent');
      await fetchAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete agent');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div ref={ref} className="mx-auto w-full max-w-2xl p-6" {...props}>
      <div className="bg-background border-border rounded-lg border p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Phone className="text-primary h-6 w-6" />
            <h2 className="text-foreground text-2xl font-bold">SIP Phone Numbers</h2>
          </div>
          {!showAddForm && (
            <Button
              onClick={() => setShowAddForm(true)}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Add Number
            </Button>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <WarningCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Add Form */}
        {showAddForm && (
          <form
            onSubmit={handleAddAgent}
            className="bg-muted border-border mb-6 rounded-lg border p-4"
          >
            <h3 className="text-foreground mb-4 font-semibold">Add New Agent</h3>

            <div className="space-y-4">
              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">Agent ID</label>
                <input
                  type="text"
                  placeholder="e.g., hvac_support"
                  value={formData.agent_id}
                  onChange={(e) => setFormData({ ...formData, agent_id: e.target.value })}
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">
                  Local Phone Number
                </label>
                <input
                  type="text"
                  placeholder="e.g., 09643234042"
                  value={formData.local_number}
                  onChange={(e) => setFormData({ ...formData, local_number: e.target.value })}
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">SIP Number</label>
                <input
                  type="text"
                  placeholder="e.g., 12707768622"
                  value={formData.sip_number}
                  onChange={(e) => setFormData({ ...formData, sip_number: e.target.value })}
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">
                  System Prompt
                </label>
                <textarea
                  placeholder="You are a professional support agent..."
                  value={formData.system_prompt}
                  onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary h-24 w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-foreground mb-2 block text-sm font-medium">STT</label>
                  <Select
                    value={formData.stt}
                    onValueChange={(v) => setFormData({ ...formData, stt: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="deepgram">Deepgram</SelectItem>
                      <SelectItem value="whisper">Whisper</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-foreground mb-2 block text-sm font-medium">LLM</label>
                  <Select
                    value={formData.llm}
                    onValueChange={(v) => setFormData({ ...formData, llm: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="google">Google</SelectItem>
                      <SelectItem value="groq">Groq</SelectItem>
                      <SelectItem value="langchain">LangChain</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-foreground mb-2 block text-sm font-medium">TTS</label>
                  <Select
                    value={formData.tts}
                    onValueChange={(v) => setFormData({ ...formData, tts: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="elevenlabs">ElevenLabs</SelectItem>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="kokoro">Kokoro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading ? 'Adding...' : 'Add Agent'}
                </Button>
              </div>
            </div>
          </form>
        )}

        {/* Agents List */}
        <div className="space-y-3">
          {agents.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center">No agents added yet</p>
          ) : (
            agents.map((agent) => (
              <div
                key={agent.agent_id}
                className="border-border bg-muted/30 flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex-1">
                  <div className="mb-2 flex items-center gap-4">
                    <div>
                      <p className="text-foreground font-semibold">{agent.agent_id}</p>
                      <p className="text-muted-foreground text-sm">
                        Local: {agent.local_number} → SIP: {agent.sip_number}
                      </p>
                    </div>
                    <div className="text-sm">
                      <span className="inline-block rounded bg-green-100 px-2 py-1 text-green-800">
                        {agent.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-muted-foreground text-xs">Trunk ID: {agent.trunk_id}</p>
                </div>

                <button
                  onClick={() => handleDeleteAgent(agent.agent_id)}
                  disabled={loading}
                  className="rounded-lg p-2 transition-colors hover:bg-red-50"
                  title="Delete agent"
                >
                  <Trash className="h-5 w-5 text-red-600" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="mt-4 text-center">
            <p className="text-muted-foreground text-sm">Loading...</p>
          </div>
        )}
      </div>
    </div>
  );
};
