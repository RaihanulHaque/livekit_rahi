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

interface SIPTrunk {
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
  const [trunks, setTrunks] = useState<SIPTrunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    local_number: '',
    system_prompt: '',
    stt: 'deepgram',
    llm: 'openai',
    tts: 'elevenlabs',
  });

  const fetchTrunks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const headers: Record<string, string> = {};
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const res = await fetch('/api/sip', { headers });
      if (!res.ok) throw new Error('Failed to fetch trunks');
      const data = await res.json();
      setTrunks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [jwtToken]);

  useEffect(() => {
    fetchTrunks();
  }, [fetchTrunks]);

  const handleAddTrunk = async (e: React.FormEvent) => {
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

      const res = await fetch('/api/sip', {
        method: 'POST',
        headers,
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err);
      }

      setFormData({
        local_number: '',
        system_prompt: '',
        stt: 'deepgram',
        llm: 'openai',
        tts: 'elevenlabs',
      });
      setShowAddForm(false);
      await fetchTrunks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add trunk');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTrunk = async (localNumber: string) => {
    if (!confirm(`Delete phone number ${localNumber}?`)) return;

    setLoading(true);
    setError('');

    try {
      const headers: Record<string, string> = {};
      if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
      }

      const res = await fetch(`/api/sip/${localNumber}`, {
        method: 'DELETE',
        headers,
      });

      if (!res.ok) throw new Error('Failed to delete trunk');
      await fetchTrunks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete trunk');
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
            onSubmit={handleAddTrunk}
            className="bg-muted border-border mb-6 rounded-lg border p-4"
          >
            <h3 className="text-foreground mb-4 font-semibold">Add New Phone Number</h3>

            <div className="space-y-4">
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
                  {loading ? 'Adding...' : 'Add Phone Number'}
                </Button>
              </div>
            </div>
          </form>
        )}

        {/* Trunks List */}
        <div className="space-y-3">
          {trunks.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center">No phone numbers added yet</p>
          ) : (
            trunks.map((trunk) => (
              <div
                key={trunk.local_number}
                className="border-border bg-muted/30 flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex-1">
                  <div className="mb-2 flex items-center gap-4">
                    <div>
                      <p className="text-foreground font-semibold">{trunk.local_number}</p>
                      <p className="text-muted-foreground text-sm">SIP: {trunk.sip_number}</p>
                    </div>
                    <div className="text-sm">
                      <span className="inline-block rounded bg-green-100 px-2 py-1 text-green-800">
                        {trunk.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-muted-foreground text-xs">ID: {trunk.trunk_id}</p>
                </div>

                <button
                  onClick={() => handleDeleteTrunk(trunk.local_number)}
                  disabled={loading}
                  className="rounded-lg p-2 transition-colors hover:bg-red-50"
                  title="Delete phone number"
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
