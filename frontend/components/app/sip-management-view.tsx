'use client';

import { useCallback, useEffect, useState } from 'react';
import { Phone, PhoneOutgoing, Plus, Trash, WarningCircle } from '@phosphor-icons/react';
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

interface OutboundTrunk {
  trunk_id: string;
  name: string;
  address: string;
  numbers: string[];
  auth_username: string;
  created_at: number;
}

type ActiveTab = 'inbound' | 'outbound';

export const SipManagementView = ({
  ref,
  jwtToken,
  ...props
}: React.ComponentProps<'div'> & { jwtToken?: string }) => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('inbound');

  // ── Inbound state ──────────────────────────────────────────────────────
  const [agents, setAgents] = useState<SIPAgent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState('');
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [agentForm, setAgentForm] = useState({
    agent_id: '',
    local_number: '',
    sip_number: '',
    system_prompt: '',
    stt: 'deepgram',
    llm: 'openai',
    tts: 'elevenlabs',
  });

  // ── Outbound state ─────────────────────────────────────────────────────
  const [trunks, setTrunks] = useState<OutboundTrunk[]>([]);
  const [trunksLoading, setTrunksLoading] = useState(false);
  const [trunksError, setTrunksError] = useState('');
  const [showAddTrunk, setShowAddTrunk] = useState(false);
  const [trunkForm, setTrunkForm] = useState({
    name: '',
    address: '',
    auth_username: '',
    auth_password: '',
    numbers: '',
  });

  // Make Call state
  const [showCallForm, setShowCallForm] = useState(false);
  const [callLoading, setCallLoading] = useState(false);
  const [callError, setCallError] = useState('');
  const [callSuccess, setCallSuccess] = useState('');
  const [callForm, setCallForm] = useState({
    agent_id: '',
    phone_number: '',
    outbound_trunk_id: '',
    display_name: '',
  });

  const authHeaders = useCallback((): Record<string, string> => {
    return jwtToken ? { Authorization: `Bearer ${jwtToken}` } : {};
  }, [jwtToken]);

  // ── Inbound: fetch agents ──────────────────────────────────────────────
  const fetchAgents = useCallback(async () => {
    setAgentsLoading(true);
    setAgentsError('');
    try {
      const res = await fetch('/api/sip/agents', { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed to fetch agents');
      setAgents(await res.json());
    } catch (err) {
      setAgentsError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setAgentsLoading(false);
    }
  }, [authHeaders]);

  // ── Outbound: fetch trunks ─────────────────────────────────────────────
  const fetchTrunks = useCallback(async () => {
    setTrunksLoading(true);
    setTrunksError('');
    try {
      const res = await fetch('/api/sip/outbound-trunks', { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed to fetch outbound trunks');
      setTrunks(await res.json());
    } catch (err) {
      setTrunksError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setTrunksLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => {
    fetchAgents();
    fetchTrunks();
  }, [fetchAgents, fetchTrunks]);

  // ── Inbound: add agent ─────────────────────────────────────────────────
  const handleAddAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    setAgentsLoading(true);
    setAgentsError('');
    try {
      const res = await fetch('/api/sip/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(agentForm),
      });
      if (!res.ok) throw new Error(await res.text());
      setAgentForm({ agent_id: '', local_number: '', sip_number: '', system_prompt: '', stt: 'deepgram', llm: 'openai', tts: 'elevenlabs' });
      setShowAddAgent(false);
      await fetchAgents();
    } catch (err) {
      setAgentsError(err instanceof Error ? err.message : 'Failed to add agent');
    } finally {
      setAgentsLoading(false);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(`Delete agent ${agentId}?`)) return;
    setAgentsLoading(true);
    try {
      const res = await fetch(`/api/sip/agents/${agentId}`, { method: 'DELETE', headers: authHeaders() });
      if (!res.ok) throw new Error('Failed to delete agent');
      await fetchAgents();
    } catch (err) {
      setAgentsError(err instanceof Error ? err.message : 'Failed to delete agent');
    } finally {
      setAgentsLoading(false);
    }
  };

  // ── Outbound: add trunk ────────────────────────────────────────────────
  const handleAddTrunk = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrunksLoading(true);
    setTrunksError('');
    try {
      const numbers = trunkForm.numbers.split(',').map((n) => n.trim()).filter(Boolean);
      const res = await fetch('/api/sip/outbound-trunks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ ...trunkForm, numbers }),
      });
      if (!res.ok) throw new Error(await res.text());
      setTrunkForm({ name: '', address: '', auth_username: '', auth_password: '', numbers: '' });
      setShowAddTrunk(false);
      await fetchTrunks();
    } catch (err) {
      setTrunksError(err instanceof Error ? err.message : 'Failed to add trunk');
    } finally {
      setTrunksLoading(false);
    }
  };

  const handleDeleteTrunk = async (trunkId: string) => {
    if (!confirm(`Delete outbound trunk ${trunkId}?`)) return;
    setTrunksLoading(true);
    try {
      const res = await fetch(`/api/sip/outbound-trunks/${trunkId}`, { method: 'DELETE', headers: authHeaders() });
      if (!res.ok) throw new Error('Failed to delete trunk');
      await fetchTrunks();
    } catch (err) {
      setTrunksError(err instanceof Error ? err.message : 'Failed to delete trunk');
    } finally {
      setTrunksLoading(false);
    }
  };

  // ── Outbound: make call ────────────────────────────────────────────────
  const handleMakeCall = async (e: React.FormEvent) => {
    e.preventDefault();
    setCallLoading(true);
    setCallError('');
    setCallSuccess('');
    try {
      const res = await fetch('/api/sip/outbound/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(callForm),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setCallSuccess(`Call initiated! Room: ${data.room_name}`);
      setCallForm({ agent_id: '', phone_number: '', outbound_trunk_id: '', display_name: '' });
      setShowCallForm(false);
    } catch (err) {
      setCallError(err instanceof Error ? err.message : 'Failed to initiate call');
    } finally {
      setCallLoading(false);
    }
  };

  return (
    <div ref={ref} className="mx-auto w-full max-w-2xl p-6" {...props}>
      <div className="bg-background border-border rounded-lg border p-6">

        {/* Tab Header */}
        <div className="mb-6 flex gap-2 border-b border-border pb-4">
          <button
            onClick={() => setActiveTab('inbound')}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'inbound'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Phone className="h-4 w-4" />
            Inbound Agents
          </button>
          <button
            onClick={() => setActiveTab('outbound')}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'outbound'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <PhoneOutgoing className="h-4 w-4" />
            Outbound Calls
          </button>
        </div>

        {/* ── INBOUND TAB ────────────────────────────────────────────── */}
        {activeTab === 'inbound' && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-foreground text-xl font-bold">Inbound Agents</h2>
              {!showAddAgent && (
                <Button onClick={() => setShowAddAgent(true)} disabled={agentsLoading} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Add Agent
                </Button>
              )}
            </div>

            {agentsError && (
              <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
                <WarningCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
                <p className="text-sm text-red-800">{agentsError}</p>
              </div>
            )}

            {showAddAgent && (
              <form onSubmit={handleAddAgent} className="bg-muted border-border mb-6 rounded-lg border p-4">
                <h3 className="text-foreground mb-4 font-semibold">Add Inbound Agent</h3>
                <div className="space-y-3">
                  {[
                    { label: 'Agent ID', key: 'agent_id', placeholder: 'e.g., hvac_support' },
                    { label: 'Local Number', key: 'local_number', placeholder: 'e.g., 09643234042' },
                    { label: 'SIP Number', key: 'sip_number', placeholder: 'e.g., 12707768622' },
                  ].map(({ label, key, placeholder }) => (
                    <div key={key}>
                      <label className="text-foreground mb-1 block text-sm font-medium">{label}</label>
                      <input
                        type="text"
                        placeholder={placeholder}
                        value={agentForm[key as keyof typeof agentForm]}
                        onChange={(e) => setAgentForm({ ...agentForm, [key]: e.target.value })}
                        className="border-border bg-background text-foreground placeholder-muted-foreground w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        required
                      />
                    </div>
                  ))}
                  <div>
                    <label className="text-foreground mb-1 block text-sm font-medium">System Prompt</label>
                    <textarea
                      placeholder="You are a professional support agent..."
                      value={agentForm.system_prompt}
                      onChange={(e) => setAgentForm({ ...agentForm, system_prompt: e.target.value })}
                      className="border-border bg-background text-foreground placeholder-muted-foreground h-20 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {(['stt', 'llm', 'tts'] as const).map((field) => (
                      <div key={field}>
                        <label className="text-foreground mb-1 block text-sm font-medium uppercase">{field}</label>
                        <Select value={agentForm[field]} onValueChange={(v) => setAgentForm({ ...agentForm, [field]: v })}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {field === 'stt' && <><SelectItem value="deepgram">Deepgram</SelectItem><SelectItem value="whisper">Whisper</SelectItem></>}
                            {field === 'llm' && <><SelectItem value="openai">OpenAI</SelectItem><SelectItem value="google">Google</SelectItem><SelectItem value="groq">Groq</SelectItem><SelectItem value="langchain">LangChain</SelectItem></>}
                            {field === 'tts' && <><SelectItem value="elevenlabs">ElevenLabs</SelectItem><SelectItem value="openai">OpenAI</SelectItem><SelectItem value="kokoro">Kokoro</SelectItem></>}
                          </SelectContent>
                        </Select>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="outline" onClick={() => setShowAddAgent(false)} disabled={agentsLoading}>Cancel</Button>
                    <Button type="submit" disabled={agentsLoading}>{agentsLoading ? 'Adding...' : 'Add Agent'}</Button>
                  </div>
                </div>
              </form>
            )}

            <div className="space-y-3">
              {agents.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center">No inbound agents added yet</p>
              ) : (
                agents.map((agent) => (
                  <div key={agent.agent_id} className="border-border bg-muted/30 flex items-center justify-between rounded-lg border p-4">
                    <div>
                      <p className="text-foreground font-semibold">{agent.agent_id}</p>
                      <p className="text-muted-foreground text-sm">Local: {agent.local_number} → SIP: {agent.sip_number}</p>
                      <span className="mt-1 inline-block rounded bg-green-100 px-2 py-0.5 text-xs text-green-800">{agent.status}</span>
                    </div>
                    <button onClick={() => handleDeleteAgent(agent.agent_id)} disabled={agentsLoading} className="rounded-lg p-2 hover:bg-red-50">
                      <Trash className="h-5 w-5 text-red-600" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {/* ── OUTBOUND TAB ───────────────────────────────────────────── */}
        {activeTab === 'outbound' && (
          <>
            {/* Outbound Trunks Section */}
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-foreground text-xl font-bold">Outbound Trunks</h2>
                {!showAddTrunk && (
                  <Button onClick={() => setShowAddTrunk(true)} disabled={trunksLoading} className="flex items-center gap-2">
                    <Plus className="h-4 w-4" />
                    Add Trunk
                  </Button>
                )}
              </div>

              {trunksError && (
                <div className="mb-3 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
                  <WarningCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
                  <p className="text-sm text-red-800">{trunksError}</p>
                </div>
              )}

              {showAddTrunk && (
                <form onSubmit={handleAddTrunk} className="bg-muted border-border mb-4 rounded-lg border p-4">
                  <h3 className="text-foreground mb-3 font-semibold">Add Outbound Trunk</h3>
                  <div className="space-y-3">
                    {[
                      { label: 'Name', key: 'name', placeholder: 'My outbound trunk', type: 'text' },
                      { label: 'SIP Address', key: 'address', placeholder: 'sip.telnyx.com or trunk.twilio.com', type: 'text' },
                      { label: 'Auth Username', key: 'auth_username', placeholder: 'SIP username', type: 'text' },
                      { label: 'Auth Password', key: 'auth_password', placeholder: 'SIP password', type: 'password' },
                      { label: 'Numbers (comma-separated)', key: 'numbers', placeholder: '+15105550100, +15105550101', type: 'text' },
                    ].map(({ label, key, placeholder, type }) => (
                      <div key={key}>
                        <label className="text-foreground mb-1 block text-sm font-medium">{label}</label>
                        <input
                          type={type}
                          placeholder={placeholder}
                          value={trunkForm[key as keyof typeof trunkForm]}
                          onChange={(e) => setTrunkForm({ ...trunkForm, [key]: e.target.value })}
                          className="border-border bg-background text-foreground placeholder-muted-foreground w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                          required
                        />
                      </div>
                    ))}
                    <div className="flex justify-end gap-2 pt-2">
                      <Button type="button" variant="outline" onClick={() => setShowAddTrunk(false)} disabled={trunksLoading}>Cancel</Button>
                      <Button type="submit" disabled={trunksLoading}>{trunksLoading ? 'Adding...' : 'Add Trunk'}</Button>
                    </div>
                  </div>
                </form>
              )}

              <div className="space-y-2">
                {trunks.length === 0 ? (
                  <p className="text-muted-foreground py-4 text-center text-sm">No outbound trunks configured</p>
                ) : (
                  trunks.map((trunk) => (
                    <div key={trunk.trunk_id} className="border-border bg-muted/30 flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <p className="text-foreground font-semibold">{trunk.name}</p>
                        <p className="text-muted-foreground text-xs">{trunk.address} · {trunk.numbers.join(', ')}</p>
                        <p className="text-muted-foreground text-xs font-mono">{trunk.trunk_id}</p>
                      </div>
                      <button onClick={() => handleDeleteTrunk(trunk.trunk_id)} disabled={trunksLoading} className="rounded-lg p-2 hover:bg-red-50">
                        <Trash className="h-5 w-5 text-red-600" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Divider */}
            <div className="border-border mb-6 border-t" />

            {/* Make Call Section */}
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-foreground text-xl font-bold">Make a Call</h2>
                {!showCallForm && (
                  <Button
                    onClick={() => setShowCallForm(true)}
                    disabled={trunks.length === 0 || agents.length === 0}
                    className="flex items-center gap-2"
                  >
                    <PhoneOutgoing className="h-4 w-4" />
                    Call
                  </Button>
                )}
              </div>

              {(trunks.length === 0 || agents.length === 0) && !showCallForm && (
                <p className="text-muted-foreground text-sm">
                  {trunks.length === 0 ? 'Add an outbound trunk first.' : 'Add an inbound agent first (its config will be used for the call).'}
                </p>
              )}

              {callSuccess && (
                <div className="mb-3 rounded-lg border border-green-200 bg-green-50 p-4">
                  <p className="text-sm text-green-800">{callSuccess}</p>
                </div>
              )}

              {callError && (
                <div className="mb-3 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
                  <WarningCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
                  <p className="text-sm text-red-800">{callError}</p>
                </div>
              )}

              {showCallForm && (
                <form onSubmit={handleMakeCall} className="bg-muted border-border rounded-lg border p-4">
                  <div className="space-y-3">
                    <div>
                      <label className="text-foreground mb-1 block text-sm font-medium">Agent (system prompt + providers)</label>
                      <Select value={callForm.agent_id} onValueChange={(v) => setCallForm({ ...callForm, agent_id: v })}>
                        <SelectTrigger><SelectValue placeholder="Select agent..." /></SelectTrigger>
                        <SelectContent>
                          {agents.map((a) => <SelectItem key={a.agent_id} value={a.agent_id}>{a.agent_id}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="text-foreground mb-1 block text-sm font-medium">Outbound Trunk</label>
                      <Select value={callForm.outbound_trunk_id} onValueChange={(v) => setCallForm({ ...callForm, outbound_trunk_id: v })}>
                        <SelectTrigger><SelectValue placeholder="Select trunk..." /></SelectTrigger>
                        <SelectContent>
                          {trunks.map((t) => <SelectItem key={t.trunk_id} value={t.trunk_id}>{t.name} ({t.numbers[0]})</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="text-foreground mb-1 block text-sm font-medium">Phone Number to Dial</label>
                      <input
                        type="text"
                        placeholder="+15105550123"
                        value={callForm.phone_number}
                        onChange={(e) => setCallForm({ ...callForm, phone_number: e.target.value })}
                        className="border-border bg-background text-foreground placeholder-muted-foreground w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-foreground mb-1 block text-sm font-medium">Display Name (optional)</label>
                      <input
                        type="text"
                        placeholder="Caller name shown to recipient"
                        value={callForm.display_name}
                        onChange={(e) => setCallForm({ ...callForm, display_name: e.target.value })}
                        className="border-border bg-background text-foreground placeholder-muted-foreground w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <Button type="button" variant="outline" onClick={() => setShowCallForm(false)} disabled={callLoading}>Cancel</Button>
                      <Button type="submit" disabled={callLoading || !callForm.agent_id || !callForm.outbound_trunk_id}>
                        {callLoading ? 'Dialing...' : 'Place Call'}
                      </Button>
                    </div>
                  </div>
                </form>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
