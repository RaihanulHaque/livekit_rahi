'use client';

import { useCallback, useEffect, useState } from 'react';
import { Phone, PhoneCall, Plus, Trash, WarningCircle } from '@phosphor-icons/react';
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

interface OutboundCallResult {
  agent_id: string;
  room_name: string;
  dispatch_id: string;
  dispatch_state: string;
  agent_name: string;
  phone_number: string;
  outbound_trunk_id: string;
  participant_identity: string;
  call_direction: string;
}

export const SipManagementView = ({
  ref,
  jwtToken,
  ...props
}: React.ComponentProps<'div'> & { jwtToken?: string }) => {
  const [agents, setAgents] = useState<SIPAgent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [isAddingAgent, setIsAddingAgent] = useState(false);
  const [isStartingOutbound, setIsStartingOutbound] = useState(false);
  const [error, setError] = useState('');
  const [outboundResult, setOutboundResult] = useState<OutboundCallResult | null>(null);
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
  const [outboundForm, setOutboundForm] = useState({
    agent_id: '',
    phone_number: '',
    outbound_trunk_id: '',
    display_name: '',
  });

  const fetchAgents = useCallback(async () => {
    setLoadingAgents(true);
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
      setLoadingAgents(false);
    }
  }, [jwtToken]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    if (agents.length > 0 && !outboundForm.agent_id) {
      setOutboundForm((current) => ({
        ...current,
        agent_id: agents[0]?.agent_id ?? '',
      }));
    }
  }, [agents, outboundForm.agent_id]);

  const handleAddAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAddingAgent(true);
    setError('');
    setOutboundResult(null);

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
      setIsAddingAgent(false);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(`Delete agent ${agentId}?`)) return;

    setIsAddingAgent(true);
    setError('');
    setOutboundResult(null);

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
      setIsAddingAgent(false);
    }
  };

  const handleStartOutboundCall = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsStartingOutbound(true);
    setError('');
    setOutboundResult(null);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const payload = {
        agent_id: outboundForm.agent_id,
        phone_number: outboundForm.phone_number,
        outbound_trunk_id: outboundForm.outbound_trunk_id || undefined,
        display_name: outboundForm.display_name || undefined,
      };

      const res = await fetch('/api/sip/outbound/call', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          typeof data?.detail === 'string'
            ? data.detail
            : typeof data === 'string'
              ? data
              : 'Failed to start outbound call';
        throw new Error(detail);
      }

      setOutboundResult(data as OutboundCallResult);
      setOutboundForm((current) => ({
        ...current,
        phone_number: '',
        display_name: '',
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start outbound call');
    } finally {
      setIsStartingOutbound(false);
    }
  };

  return (
    <div ref={ref} className="mx-auto w-full max-w-2xl p-6" {...props}>
      <div className="bg-background border-border rounded-lg border p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Phone className="text-primary h-6 w-6" />
            <h2 className="text-foreground text-2xl font-bold">SIP Management</h2>
          </div>
          {!showAddForm && (
            <Button
              onClick={() => setShowAddForm(true)}
              disabled={loadingAgents || isAddingAgent || isStartingOutbound}
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

        {/* Outbound Result */}
        {outboundResult && (
          <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <PhoneCall className="h-5 w-5 text-green-700" />
              <p className="text-sm font-semibold text-green-900">Outbound call dispatched</p>
            </div>
            <div className="space-y-1 text-sm text-green-800">
              <p>Agent: {outboundResult.agent_id}</p>
              <p>Dialing: {outboundResult.phone_number}</p>
              <p>Outbound trunk: {outboundResult.outbound_trunk_id}</p>
              <p>Room: {outboundResult.room_name}</p>
              <p>Dispatch ID: {outboundResult.dispatch_id}</p>
            </div>
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
                  disabled={isAddingAgent}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isAddingAgent}>
                  {isAddingAgent ? 'Adding...' : 'Add Agent'}
                </Button>
              </div>
            </div>
          </form>
        )}

        {/* Outbound Call Form */}
        <form
          onSubmit={handleStartOutboundCall}
          className="bg-muted border-border mb-6 rounded-lg border p-4"
        >
          <div className="mb-4 flex items-center gap-2">
            <PhoneCall className="text-primary h-5 w-5" />
            <div>
              <h3 className="text-foreground font-semibold">Start Outbound Call</h3>
              <p className="text-muted-foreground text-sm">
                Reuse an existing agent profile to place a SIP outbound call.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-foreground mb-2 block text-sm font-medium">Agent</label>
              <Select
                value={outboundForm.agent_id}
                onValueChange={(v) => setOutboundForm({ ...outboundForm, agent_id: v })}
                disabled={agents.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.agent_id} value={agent.agent_id}>
                      {agent.agent_id} ({agent.local_number})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">
                  Destination Number
                </label>
                <input
                  type="text"
                  placeholder="e.g., +15105550123"
                  value={outboundForm.phone_number}
                  onChange={(e) =>
                    setOutboundForm({ ...outboundForm, phone_number: e.target.value })
                  }
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="text-foreground mb-2 block text-sm font-medium">
                  Caller Display Name
                </label>
                <input
                  type="text"
                  placeholder="Optional"
                  value={outboundForm.display_name}
                  onChange={(e) =>
                    setOutboundForm({ ...outboundForm, display_name: e.target.value })
                  }
                  className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="text-foreground mb-2 block text-sm font-medium">
                Outbound Trunk ID
              </label>
              <input
                type="text"
                placeholder="Optional if DEFAULT_OUTBOUND_TRUNK_ID is configured on the server"
                value={outboundForm.outbound_trunk_id}
                onChange={(e) =>
                  setOutboundForm({ ...outboundForm, outbound_trunk_id: e.target.value })
                }
                className="border-border bg-background text-foreground placeholder-muted-foreground focus:ring-primary w-full rounded-md border px-3 py-2 focus:ring-2 focus:outline-none"
              />
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                variant="primary"
                disabled={agents.length === 0 || isStartingOutbound}
              >
                {isStartingOutbound ? 'Dialing...' : 'Start Outbound Call'}
              </Button>
            </div>
          </div>
        </form>

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
                  disabled={isAddingAgent || isStartingOutbound}
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
        {loadingAgents && (
          <div className="mt-4 text-center">
            <p className="text-muted-foreground text-sm">Loading...</p>
          </div>
        )}
      </div>
    </div>
  );
};
