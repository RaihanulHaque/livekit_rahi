LiveKit docs › Telephony › SIP participant

---

# SIP participant

> Mapping a caller to a SIP participant.

> ℹ️ **Note**
> 
> To create a SIP participant to make outbound calls, see [Make outbound calls](https://docs.livekit.io/telephony/making-calls/outbound-calls.md).

Each user in a LiveKit telephony app is a [LiveKit participant](https://docs.livekit.io/intro/basics/rooms-participants-tracks.md). This includes end users who call in using your inbound trunk, the participant you use to make outbound calls, and if you're using an agent, the AI voice agent that interacts with callers.

SIP participants are managed like any other participant using the [participant management commands](https://docs.livekit.io/intro/basics/rooms-participants-tracks/participants.md).

## SIP participant attributes

SIP participants can be identified using the `kind` field for participants, which identifies the [type of participant](https://docs.livekit.io/intro/basics/rooms-participants-tracks/participants.md#types-of-participants) in a LiveKit room (i.e. session). For SIP participants, this is `Participant.Kind == SIP`.

The participant `attributes` field contains SIP-specific attributes that identify the caller and call details. You can use SIP participant attributes to create different workflows based on the caller. For example, look up customer information in a database to identify the caller.

### SIP attributes

All SIP participants have the following attributes:

| Attribute | Description |
| `sip.callID` | LiveKit's SIP call ID. A unique ID used as a SIP call tag to identify a conversation (i.e. match requests and responses). To learn how to cross-reference call IDs for debugging, see [Cross-referencing calls with Call IDs](https://docs.livekit.io/reference/telephony/troubleshooting.md#call-ids). |
| `sip.callIDFull` | Trunk provider SIP call ID. A globally unique ID to identify a specific SIP call. |
| `sip.callStatus` | Current call status for the SIP call associated with this participant. Valid values are:- `active`: Participant is connected and the call is active.
- `automation`: For outbound calls using Dual-Tone Multi-Frequency (DTMF), this status indicates the call has successfully connected, but is still dialing DTMF numbers. After all the numbers are dialed, the status changes to `active`.
- `dialing`: Call is dialing and waiting to be picked up.
- `hangup`: Call has been ended by a participant. See [disconnect reasons](#disconnect-reasons) for the specific reason.
- `ringing`: Inbound call is ringing for the caller. Status changes to `active` when the SIP participant subscribes to any remote audio tracks. |
| `sip.phoneNumber` | User's phone number. For inbound trunks, this is the phone number the call originates from. For outbound SIP, this is the number dialed by the SIP participant.

> ℹ️ **Note**
> 
> This attribute isn't available if `HidePhoneNumber` is set in the dispatch rule. |
| `sip.ruleID` | SIP `DispatchRule` ID used for the inbound call. This field is empty for outbound calls. |
| `sip.trunkID` | The inbound or outbound SIP trunk ID used for the call. |
| `sip.trunkPhoneNumber` | Phone number associated with SIP trunk. For inbound trunks, this is the number dialed in to by an end user. For outbound trunks, this is the number a call originates from. |

### Twilio attributes

If you're using Twilio SIP trunks, the following additional attributes are included:

| Attribute | Description |
| `sip.twilio.accountSid` | Twilio account SID. |
| `sip.twilio.callSid` | Twilio call SID. |

### Custom attributes

You can add custom SIP participant attributes in one of two ways:

- Adding attributes to the dispatch rule. To learn more, see [Setting custom attributes on inbound SIP participants](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule.md#setting-custom-attributes-on-inbound-sip-participants).
- Using SIP headers: For any `X-*` SIP headers, you can configure your trunk with `headers_to_attributes` and a key/value pair mapping.

For example:

**Twilio**:

```json
{
  "trunk": {
    "name": "Demo inbound trunk",
    "numbers": ["+15105550100"],
    "headers_to_attributes": {
      "X-<custom_key_value>": "<custom_attribute_name>",
    }
  }
}

```

> 🔥 **Caution**
> 
> Note that Twilio numbers must start with a leading `+`.

---

**Telnyx**:

```json
{
  "trunk": {
    "name": "Demo inbound trunk",
    "numbers": ["+15105550100"],
    "headers_to_attributes": {
      "X-<custom_key_value>": "<custom_attribute_name>",
    }
  }
}

```

> 🔥 **Caution**
> 
> Note the leading `+` assumes the `Destination Number Format` is set to `+E.164` for your Telnyx number.

## Examples

The following examples use SIP participant attributes.

### Basic example

**Python**:

This example logs the phone number for a specific caller.

```python
# Check if the participant is a SIP participant
if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
    # Do something here based on SIP participant attributes
    # For example, look up customer information using their phone number

    # If this caller is calling from a specific phone number, do something
    if participant.attributes['sip.phoneNumber'] == '+15105550100':
        logger.info("Caller phone number is +1-510-555-0100")

```

---

**Node.js**:

This example logs the Twilio call SID if the user is a SIP participant.

```typescript
if (participant.kind == ParticipantKind.SIP) {
  console.log(participant.attributes['sip.twilio.callSid']);
};

```

### Modify voice AI agent based on caller attributes

Follow the [Voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md) to create an agent that responds to incoming calls. Then modify the agent to use SIP participant attributes.

**Python**:

Before starting your `AgentSession`, select the best Deepgram STT model for the participant. Add this code to your entrypoint function:

```python
# Add this import to the top of your file
from livekit import rtc

participant = await ctx.wait_for_participant()
stt_model = "deepgram/nova-2-general"

# Check if the participant is a SIP participant
if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
    # Use a Deepgram model better suited for phone calls
    stt_model = "deepgram/nova-2-phonecall"

    if participant.attributes['sip.phoneNumber'] == '+15105550100':
        logger.info("Caller phone number is +1-510-555-0100")
        # Add other logic here to modify the agent based on the caller's phone number
 

session = AgentSession(
    stt=stt_model,
    # ... llm, vad, tts, etc.
)

# ... rest of your entrypoint, including `await session.start(...)`

```

---

**Node.js**:

The following example is based on the [Voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md).

Modify the example to identify SIP participants and greet them based on their phone number.

1. Install the LiveKit SDK for Node.js:

```shell
pnpm install '@livekit/rtc-node'

```
2. Import the package in `src/agent.ts`:

```typescript
import { ParticipantKind } from '@livekit/rtc-node';

```
3. Replace the `assistant` in `agent.ts` with this updated version:

```typescript
const assistant = new voice.Agent({
  instructions: 'You are a helpful voice AI assistant.',
  tools: {
    weather: llm.tool({
      description: 'Get the weather in a location',
      parameters: z.object({
      location: z.string().describe('The location to get the weather for'),
      }),
      execute: async ({ location: string }) => {
        const response = await fetch(`https://wttr.in/${location}?format=%C+%t`);
        if (!response.ok) {
          throw new Error(`Weather API returned status: ${response.status}`);
        }
        const weather = await response.text();
        return `The weather in ${location} right now is ${weather}.`;
      },
    }),
  },
});

// ... Add this after the await ctx.connect()

const participant = await ctx.waitForParticipant();
let initialChatText = 'Say "How can I help you today?"';

if (participant.kind === ParticipantKind.SIP) {
  // Add a custom message based on caller's phone number
  initialChatText =
    'Find the location for the area code from phone number ' +
    participant.attributes['sip.phoneNumber'] +
    ' and say "Hi, I see you're calling from area code," ' +
    'my area code. Pause, then tell me the general weather for the area.';

  const chatCtx = session.chatCtx.copy();
  chatCtx.addMessage({
    role: 'assistant',
    content: initialChatText,
  });
  assistant.updateChatCtx(chatCtx);
}

// ... rest of your entrypoint function

```

## Disconnect reasons

When a SIP participant disconnects, the `disconnect_reason` field on the participant indicates why. These values are useful for handling call failures and mid-call disconnections in your agent code:

| Disconnect reason | Description |
| `USER_REJECTED` | Callee actively rejected the call (SIP 486 Busy Here or 603 Decline). |
| `USER_UNAVAILABLE` | Callee didn't answer or was unavailable (SIP 408 or 480). |
| `SIP_TRUNK_FAILURE` | SIP trunk or protocol failure (SIP 5xx or other errors). |

For outbound calls, these values map to the `TwirpError` raised when `wait_until_answered` is `true`. For handling these outcomes in your agent code, see [Handling call outcomes](https://docs.livekit.io/telephony/making-calls/outbound-calls.md#call-outcomes).

## Creating a SIP participant to make outbound calls

To make outbound calls, create a SIP participant. To learn more, see [Make outbound calls](https://docs.livekit.io/telephony/making-calls/outbound-calls.md).

---

This document was rendered at 2026-04-13T12:51:28.071Z.
For the latest version of this document, see [https://docs.livekit.io/reference/telephony/sip-participant.md](https://docs.livekit.io/reference/telephony/sip-participant.md).

To explore all LiveKit documentation, see [llms.txt](https://docs.livekit.io/llms.txt).