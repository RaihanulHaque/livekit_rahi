'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/livekit/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/livekit/select';
import {
  WarningCircle,
  Trash,
  Plus,
  Phone,
} from '@phosphor-icons/react';

interface SIPTrunk {
  local_number: string;
  sip_number: string;
  trunk_id: string;
  status: string;
  created_at: number;
}

interface SIPTrunkDetail extends SIPTrunk {
  dispatch_rule_id: string;
  system_prompt: string;
  stt: string;
  llm: string;
  tts: string;
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

  const fetchTrunks = async () => {
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
  };

  useEffect(() => {
    fetchTrunks();
  }, []);

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
    <div ref={ref} className="w-full max-w-2xl mx-auto p-6" {...props}>
      <div className="bg-background rounded-lg border border-border p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Phone className="w-6 h-6 text-primary" />
            <h2 className="text-2xl font-bold text-foreground">SIP Phone Numbers</h2>
          </div>
          {!showAddForm && (
            <Button
              onClick={() => setShowAddForm(true)}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Number
            </Button>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <WarningCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Add Form */}
        {showAddForm && (
          <form onSubmit={handleAddTrunk} className="mb-6 p-4 bg-muted rounded-lg border border-border">
            <h3 className="font-semibold text-foreground mb-4">Add New Phone Number</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Local Phone Number
                </label>
                <input
                  type="text"
                  placeholder="e.g., 09643234042"
                  value={formData.local_number}
                  onChange={(e) =>
                    setFormData({ ...formData, local_number: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  System Prompt
                </label>
                <textarea
                  placeholder="You are a professional support agent..."
                  value={formData.system_prompt}
                  onChange={(e) =>
                    setFormData({ ...formData, system_prompt: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary h-24"
                  required
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    STT
                  </label>
                  <Select value={formData.stt} onValueChange={(v) =>
                    setFormData({ ...formData, stt: v })
                  }>
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
                  <label className="block text-sm font-medium text-foreground mb-2">
                    LLM
                  </label>
                  <Select value={formData.llm} onValueChange={(v) =>
                    setFormData({ ...formData, llm: v })
                  }>
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
                  <label className="block text-sm font-medium text-foreground mb-2">
                    TTS
                  </label>
                  <Select value={formData.tts} onValueChange={(v) =>
                    setFormData({ ...formData, tts: v })
                  }>
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

              <div className="flex gap-2 justify-end">
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
            <p className="text-center text-muted-foreground py-8">
              No phone numbers added yet
            </p>
          ) : (
            trunks.map((trunk) => (
              <div
                key={trunk.local_number}
                className="flex items-center justify-between p-4 border border-border rounded-lg bg-muted/30"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-4 mb-2">
                    <div>
                      <p className="font-semibold text-foreground">
                        {trunk.local_number}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        SIP: {trunk.sip_number}
                      </p>
                    </div>
                    <div className="text-sm">
                      <span className="inline-block px-2 py-1 bg-green-100 text-green-800 rounded">
                        {trunk.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    ID: {trunk.trunk_id}
                  </p>
                </div>

                <button
                  onClick={() => handleDeleteTrunk(trunk.local_number)}
                  disabled={loading}
                  className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                  title="Delete phone number"
                >
                  <Trash className="w-5 h-5 text-red-600" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="mt-4 text-center">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        )}
      </div>
    </div>
  );
};
