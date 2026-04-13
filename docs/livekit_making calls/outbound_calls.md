LiveKit docs › Making calls › Outbound calls

---

# Make outbound calls

> Create a LiveKit SIP participant to make outbound calls.

## Overview

Make outbound calls from LiveKit rooms to phone numbers by creating SIP participants. When you create a SIP participant with an outbound trunk, LiveKit initiates a call to the specified phone number and connects the callee to the room as a SIP participant. Once connected, the callee can interact with other participants in the room, including AI agents and regular participants.

To make outbound calls, you need at least one [outbound trunk](https://docs.livekit.io/telephony/making-calls/outbound-trunk.md) configured. You can customize outbound calls with features like custom caller ID, DTMF tones for extension codes, and dial tone playback while the call connects.

To create an AI agent to make outbound calls on your behalf, see the [Voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md).

## Creating a SIP participant

To make outbound calls with SIP Service, create a SIP participant with the [`CreateSIPParticipant`](https://docs.livekit.io/reference/telephony/sip-api.md#createsipparticipant) API. It returns an `SIPParticipantInfo` object that describes the participant.

Outbound calling requires at least one [Outbound Trunk](https://docs.livekit.io/telephony/making-calls/outbound-trunk.md).

**LiveKit CLI**:

1. Create a `sip-participant.json` file with the following participant details:

```json
{
  "sip_trunk_id": "<your-trunk-id>",
  "sip_call_to": "<phone-number-to-dial>",
  "room_name": "my-sip-room",
  "participant_identity": "sip-test",
  "participant_name": "Test Caller",
  "krisp_enabled": true,
  "wait_until_answered": true
}

```
2. Create the SIP Participant using the CLI. After you run this command, the participant makes a call to the `sip_call_to` number configured in your outbound trunk. When you set `wait_until_answered` to `true`, the command waits until the callee picks up the call before returning. You can also monitor the call status using the [SIP participant attributes](https://docs.livekit.io/reference/telephony/sip-participant.md#sip-attributes). When the callee picks up the call, the `sip.callStatus` attribute is `active`.

```shell
lk sip participant create sip-participant.json

```

---

**Node.js**:

```typescript
import { SipClient, TwirpError } from 'livekit-server-sdk';

const sipClient = new SipClient(process.env.LIVEKIT_URL,
                                process.env.LIVEKIT_API_KEY,
                                process.env.LIVEKIT_API_SECRET);

// Outbound trunk to use for the call
const trunkId = '<your-trunk-id>';

// Phone number to dial
const phoneNumber = '<phone-number-to-dial>';

// Name of the room to attach the call to
const roomName = 'my-sip-room';

const sipParticipantOptions = {
  participantIdentity: 'sip-test',
  participantName: 'Test Caller',
  krispEnabled: true,
  waitUntilAnswered: true
};

async function main() {
  try {
    const participant = await sipClient.createSipParticipant(
      trunkId,
      phoneNumber,
      roomName,
      sipParticipantOptions
    );

    console.log('Participant created:', participant);
  } catch (error) {
    console.error('Error creating SIP participant:', error);
    if (error instanceof TwirpError) {
      console.error("SIP error code: ", error.metadata?.['sip_status_code']);
      console.error("SIP error message: ", error.metadata?.['sip_status']);
    }
  }
}

main();

```

---

**Python**:

```python
import asyncio

from livekit import api 
from livekit.protocol.sip import CreateSIPParticipantRequest, SIPParticipantInfo

async def main():
    livekit_api = api.LiveKitAPI()

    request = CreateSIPParticipantRequest(
        sip_trunk_id = "<trunk_id>",
        sip_call_to = "<phone_number>",
        room_name = "my-sip-room",
        participant_identity = "sip-test",
        participant_name = "Test Caller",
        krisp_enabled = True,
        wait_until_answered = True
    )
    
    try:
        participant = await livekit_api.sip.create_sip_participant(request)
        print(f"Successfully created {participant}")
    except Exception as e:
        print(f"Error creating SIP participant: {e}")
        # sip_status_code contains the status code from upstream carrier
        print(f"SIP error code: {e.metadata.get('sip_status_code')}")
        # sip_status contains the status message from upstream carrier
        print(f"SIP error message: {e.metadata.get('sip_status')}")
    finally:
        await livekit_api.aclose()

asyncio.run(main())

```

---

**Ruby**:

```ruby
require 'livekit'

trunk_id = "<trunk_id>";
number = "<phone_number>";
room_name = "my-sip-room";
participant_identity = "sip-test";
participant_name = "Test Caller";

sip_service = LiveKit::SIPServiceClient.new(
  ENV['LIVEKIT_URL'],
  api_key: ENV['LIVEKIT_API_KEY'],
  api_secret: ENV['LIVEKIT_API_SECRET']
)

resp = sip_service.create_sip_participant(
    trunk_id,
    number,
    room_name,
    participant_identity: participant_identity,
    participant_name: participant_name
)

puts resp.data

```

---

**Go**:

```go
package main

import (
  "context"
  "fmt"
  "os"

  lksdk "github.com/livekit/server-sdk-go/v2"
  "github.com/livekit/protocol/livekit"
)

func main() {
  trunkId := "<trunk_id>";
  phoneNumber := "<phone_number>";
  roomName := "my-sip-room";
  participantIdentity := "sip-test";
  participantName := "Test Caller";

  request := &livekit.CreateSIPParticipantRequest {
    SipTrunkId: trunkId,
    SipCallTo: phoneNumber,
    RoomName: roomName,
    ParticipantIdentity: participantIdentity,
    ParticipantName: participantName,
    KrispEnabled: true,
    WaitUntilAnswered: true,
  }

  sipClient := lksdk.NewSIPClient(os.Getenv("LIVEKIT_URL"),
                                  os.Getenv("LIVEKIT_API_KEY"),
                                  os.Getenv("LIVEKIT_API_SECRET"))

  // Create trunk
  participant, err := sipClient.CreateSIPParticipant(context.Background(), request)

  if err != nil {
    fmt.Println(err)
  } else {
    fmt.Println(participant)
  }
}

```

---

**Kotlin**:

```kotlin
import io.livekit.server.CreateSipParticipantOptions
import io.livekit.server.SipServiceClient

val sipClient = SipServiceClient.createClient(
    System.getenv("LIVEKIT_URL") ?: "",
    System.getenv("LIVEKIT_API_KEY") ?: "",
    System.getenv("LIVEKIT_API_SECRET") ?: ""
)

val trunkId = "<trunk_id>"
val phoneNumber = "<phone_number>"
val roomName = "my-sip-room"

val options = CreateSipParticipantOptions(
    participantIdentity = "sip-test",
    participantName = "Test Caller",
    waitUntilAnswered = true
)

var participant: LivekitSip.SIPParticipantInfo? = null
try {
    val response = sipClient.createSipParticipant(
        trunkId,
        phoneNumber,
        roomName,
        options ).execute()
    if (response.isSuccessful) {
        participant = response.body()
    }
} catch (e: Exception) {
    println("Error creating SIP participant: ${e.message}")
}

```

Once the user picks up, they are connected to `my-sip-room`.

### Agent initiated outbound calls

To have your agent make an outbound call, dispatch the agent and then create a SIP participant. This section describes how to modify the [voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md) for outbound calling. Alternatively, see the following complete example on GitHub:

- **[Outbound caller example](https://github.com/livekit-examples/outbound-caller-python)**: Complete example of an outbound calling agent.

#### Dialing a number

Add the following code to the agent code from the [voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md). Your agent reads the phone number passed in the `metadata` field of the agent dispatch request and places an outbound call by creating a SIP participant.

You should also remove the initial greeting or place it behind an `if` statement to ensure the agent waits for the user to speak first when placing an outbound call.

> ℹ️ **SIP trunk ID**
> 
> You must add a valid [outbound trunk](https://docs.livekit.io/telephony/making-calls/outbound-trunk.md) ID to successfully make a phone call. To see a list of your outbound trunks use the LiveKit CLI: `lk sip outbound list`.

**Python**:

Add the following code to the `agent.py` file from the Voice AI quickstart:

```python
# add these imports at the top of your file
from livekit import agents, api
import json

# ... AgentServer, Assistant class, and AgentSession config from the voice AI quickstart ...

@server.rtc_session(agent_name="my-telephony-agent")
async def my_agent(ctx: agents.JobContext):
    # If a phone number was provided, then place an outbound call
    # By having a condition like this, you can use the same agent for inbound/outbound telephony as well as web/mobile/etc.
    dial_info = json.loads(ctx.job.metadata)
    phone_number = dial_info.get("phone_number")

    # The participant's identity can be anything you want, but this example uses the phone number itself
    sip_participant_identity = phone_number
    if phone_number is not None:
        # The outbound call will be placed after this method is executed
        try:
            await ctx.api.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                # This ensures the participant joins the correct room
                room_name=ctx.room.name,

                # This is the outbound trunk ID to use
                # You can get this from LiveKit CLI with `lk sip outbound list`
                sip_trunk_id='ST_xxxx',

                # The outbound phone number to dial and identity to use
                sip_call_to=phone_number,
                participant_identity=sip_participant_identity,

                # This waits until the call is answered before returning
                wait_until_answered=True,
            ))

            print("call picked up successfully")
        except api.TwirpError as e:
            print(f"error creating SIP participant: {e.message}, "
                  f"SIP status: {e.metadata.get('sip_status_code')} "
                  f"{e.metadata.get('sip_status')}")
            ctx.shutdown()
            return

    # Wait for the SIP participant to fully join the room before starting the session
    participant = await ctx.wait_for_participant(identity=sip_participant_identity)

    # Create and start your AgentSession
    # session = AgentSession(...)
    # await session.start(room=ctx.room, participant=participant, agent=Assistant(), ...)

    # When placing an outbound call, let the callee speak first.
    if phone_number is None:
        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )

```

---

**Node.js**:

Install `livekit-server-sdk`:

```
pnpm add livekit-server-sdk

```

Then, edit the `main.ts` file from the [voice AI quickstart](https://docs.livekit.io/agents/start/voice-ai.md). Add the outbound dial logic at the top of `entry`, before creating the session. Make sure to use a valid ID for the `outboundTrunkId`. Run `lk sip outbound list` to get a list of outbound trunks.

```typescript
import { SipClient } from 'livekit-server-sdk';
// ... any existing code / imports ...

const outboundTrunkId = '<outbound-trunk-id>';
const sipRoom = 'new-room';

export default defineAgent({
  prewarm: async (proc: JobProcess) => {
    proc.userData.vad = await silero.VAD.load();
  },
  entry: async (ctx: JobContext) => {
    // If a phone number was provided, place an outbound call.
    const dialInfo = JSON.parse(ctx.job.metadata || '{}');
    const phoneNumber = dialInfo.phone_number;

    if (phoneNumber) {
      const sipClient = new SipClient(
        process.env.LIVEKIT_URL,
        process.env.LIVEKIT_API_KEY,
        process.env.LIVEKIT_API_SECRET,
      );
      try {
        await sipClient.createSipParticipant(
          outboundTrunkId,
          phoneNumber,
          sipRoom,
          {
            participantIdentity: phoneNumber,
            participantName: 'Test callee',
            waitUntilAnswered: true,
          },
        );
        console.log('Call picked up successfully');
      } catch (error) {
        console.error('Error creating SIP participant:', error);
        ctx.shutdown();
        return;
      }
    }

    // Wait for the SIP participant to fully join the room before starting the session
    const participant = await ctx.waitForParticipant({ identity: phoneNumber });

    // Create and start your AgentSession (use your existing STT, LLM, TTS config from the quickstart)

    // Only greet first on inbound; on outbound, the recipient speaks first and the agent responds after their turn.
    if (!phoneNumber) {
      session.generateReply({
        instructions: 'Greet the user and offer your assistance.',
      });
    }
  },
});

// Update the agentName from the quickstart to "my-telephony-agent"
cli.runApp(new ServerOptions({ agent: fileURLToPath(import.meta.url), agentName: 'my-telephony-agent' }));

```

Start the agent and follow the instructions in the next section to call your agent.

#### Make a call with your agent

Use either the LiveKit CLI or the Python API to instruct your agent to place an outbound phone call.

In this example, the job's metadata includes the phone number to call. You can extend this to include more information if needed for your use case.

The agent name must match the name you assigned to your agent. If you set it earlier in the [agent dispatch](#agent-dispatch) section, this is `my-telephony-agent`.

> ❗ **Verify values to dispatch agents**
> 
> Make sure to verify or update the values in the following examples:
> 
> - Room name: The examples use `new-room`.
> - Agent name: Must match the name you assigned to your agent.
> - Phone number: Provide a valid phone number to dial.

**LiveKit CLI**:

The following command creates a new room and dispatches your agent to it with the phone number to call.

```shell
lk dispatch create \
    --new-room \
    --agent-name my-telephony-agent \
    --metadata '{"phone_number": "+15105550123"}' # insert your own phone number here

```

---

**Python**:

```python
await lkapi.agent_dispatch.create_dispatch(
    api.CreateAgentDispatchRequest(
        # Use the agent name you set in the rtc_session decorator
        agent_name="my-telephony-agent", 

        # The room name to use.
        room="new-room",

        # Here we use JSON to pass the phone number, and could add more information if needed.
        metadata='{"phone_number": "+15105550123"}'
    )
)

```

---

**Node.js**:

```ts
import { AgentDispatchClient } from 'livekit-server-sdk';

const agentDispatchClient = new AgentDispatchClient(
  process.env.LIVEKIT_URL!,
  process.env.LIVEKIT_API_KEY!,
  process.env.LIVEKIT_API_SECRET!,
);

// Use the agent name you set in ServerOptions.agentName. Room must match the name used for CreateSIPParticipant (e.g. new-room).
await agentDispatchClient.createDispatch(
  'new-room', // must match the room name used when creating the SIP participant
  'my-telephony-agent',
  { metadata: '{"phone_number": "+15105550123"}' },
);

```

#### Voicemail detection

Your agent might encounter an automated system such as an answering machine or voicemail. You can give your LLM the ability to detect a likely voicemail system via tool call, and then perform special actions such as leaving a message and [hanging up](#hangup).

**Python**:

```python
import asyncio # add this import at the top of your file

class Assistant(Agent):
    ## ... existing init code ...
        
    @function_tool
    async def detected_answering_machine(self):
        """Call this tool if you have detected a voicemail system, AFTER hearing the voicemail greeting"""
        await self.session.generate_reply(
            instructions="Leave a voicemail message letting the user know you'll call back later."
        )
        await asyncio.sleep(0.5) # Add a natural gap to the end of the voicemail message
        await hangup_call()

```

---

**Node.js**:

```typescript
class VoicemailAgent extends voice.Agent {
  constructor() {
      super({
          // ... existing init code ...
          tools: {
            leaveVoicemail: llm.tool({
                description: 'Call this tool if you detect a voicemail system, AFTER you hear the voicemail greeting',
                execute: async (_, { ctx }: llm.ToolOptions) => {
                  const handle = ctx.session.generateReply({
                    instructions:
                      "Leave a brief voicemail message for the user telling them you are sorry you missed them, but you will call back later. You don't need to mention you're going to leave a voicemail, just say the message",
                  });
      
                  handle.addDoneCallback(() => {
                    setTimeout(async () => {
                      await hangUpCall();
                    }, 500);
                  });
                },
            }),  
          }
      })
  }
}

```

## Handling call outcomes

A successful call outcome means either the callee is speaking with your agent or an automated system (like voicemail) answered. A failure occurs when the callee doesn't answer or rejects the call. This section covers how to handle each scenario.

Use `wait_until_answered` to catch failures early. After the call connects, confirm the SIP participant joined using `JobContext.wait_for_participant`. For details, see [Catching call failures](#catch-failures).

To handle mid-call disconnections, listen for the `participant_disconnected` event. For details, see [Handling mid-call disconnections](#mid-call-disconnections).

The following table describes possible call outcomes and how to identify them:

| Outcome | SIP codes | Behavior | Indicators |
| Call answered | `200 OK` | `wait_until_answered` returns successfully. | `sip.callStatus = active` |
| Call rejected | `486 Busy Here`, `603 Decline` | `wait_until_answered` raises `TwirpError`. | `USER_REJECTED` in `disconnect_reason` |
| No answer / timeout | `408 Request Timeout`, `480 Temporarily Unavailable` | `wait_until_answered` raises `TwirpError`. | `USER_UNAVAILABLE` in `disconnect_reason` |
| SIP protocol failure | `5xx` Server Failure Responses | `wait_until_answered` raises `TwirpError`. | `SIP_TRUNK_FAILURE` in `disconnect_reason` |
| Voicemail | `200 OK` | Call answered | `sip.callStatus = active`, agent speaks to voicemail |

> 🔥 **Voicemail is not a failure**
> 
> Voicemail systems answer the call at the SIP layer with a `200 OK`, so `wait_until_answered` returns successfully and no `TwirpError` is raised. To handle voicemail, use [voicemail detection](#voicemail-detection) instead of error handling.

### Catching call failures

To catch failures early, use the `CreateSIPParticipant` API with the `wait_until_answered` option. When a failure occurs, a `TwirpError` is raised containing metadata with the SIP status code from the upstream carrier. Use this information to determine the cause and handle it accordingly (for example, retry the call or notify the user).

After the call is answered, confirm the SIP participant has joined the room using `JobContext.wait_for_participant`.

The following example demonstrates how to catch call failures using both methods.

**Python**:

Update the `sip_trunk_id` and `sip_call_to` fields before running the following example:

```python
from livekit import api

try:
    await ctx.api.sip.create_sip_participant(api.CreateSIPParticipantRequest(
        room_name=ctx.room.name,
        sip_trunk_id='ST_xxxx',
        sip_call_to=phone_number,
        # Use the phone number as the participant identity
        participant_identity=sip_call_to,
        wait_until_answered=True,
    ))
except api.TwirpError as e:
    sip_code = e.metadata.get('sip_status_code')
    # 486 = Busy Here, 603 = Decline — user actively rejected the call
    # 408/480 = no answer or unavailable
    # 5xx = SIP trunk/protocol failure
    print(f"Call failed: {e.message} (SIP {sip_code})")
    ctx.shutdown()
    return

# Wait for the SIP participant to fully join the room
participant = await ctx.wait_for_participant(identity=sip_call_to)

```

---

**Node.js**:

Install `livekit-server-sdk` if you haven't already:

```
pnpm add livekit-server-sdk

```

Update the `trunkId` and `phoneNumber` variables before running the following example:

```typescript
import { SipClient, TwirpError } from 'livekit-server-sdk';

try {
  await sipClient.createSipParticipant(
    trunkId, phoneNumber, ctx.room.name,
    { participantIdentity: phoneNumber, waitUntilAnswered: true },
  );
} catch (error) {
  if (error instanceof TwirpError) {
    const sipCode = error.metadata?.['sip_status_code'];
    // 486 = Busy Here, 603 = Decline — user actively rejected the call
    // 408/480 = no answer or unavailable
    // 5xx = SIP trunk/protocol failure
    console.error(`Call failed: ${error.message} (SIP ${sipCode})`);
  }
  ctx.shutdown();
  return;
}

// Wait for the SIP participant to fully join the room
const participant = await ctx.waitForParticipant({ identity: phoneNumber });

```

### Handling mid-call disconnections

After a call connects, the callee might hang up or the connection might drop. Listen for the `participant_disconnected` event and inspect `disconnect_reason` to determine what happened:

**Python**:

```python
from livekit import rtc

@ctx.room.on("participant_disconnected")
def on_participant_disconnected(participant: rtc.RemoteParticipant):
    if participant.identity != sip_participant_identity:
        return
    reason = participant.disconnect_reason
    if reason == rtc.DisconnectReason.USER_REJECTED:
        print("Callee rejected the call")
    elif reason == rtc.DisconnectReason.USER_UNAVAILABLE:
        print("Callee was unavailable")
    elif reason == rtc.DisconnectReason.SIP_TRUNK_FAILURE:
        print("SIP trunk or protocol failure")
    else:
        print(f"Callee disconnected: {rtc.DisconnectReason.Name(reason)}")

```

---

**Node.js**:

Install `@livekit/rtc-node` to get access to disconnect reasons:

```bash
pnpm add '@livekit/rtc-node'

```

Add a listener for the `participant_disconnected` event and inspect the `disconnectReason` property:

```typescript
import { DisconnectReason } from '@livekit/rtc-node';

ctx.room.on('participantDisconnected', (participant) => {
  if (participant.identity !== phoneNumber) return;

  switch (participant.disconnectReason) {
    case DisconnectReason.USER_REJECTED:
      console.log('Callee rejected the call');
      break;
    case DisconnectReason.USER_UNAVAILABLE:
      console.log('Callee was unavailable');
      break;
    case DisconnectReason.SIP_TRUNK_FAILURE:
      console.log('SIP trunk or protocol failure');
      break;
    default:
      console.log(`Callee disconnected: ${DisconnectReason[participant.disconnectReason]}`);
  }
});

```

For more information on disconnect reasons, see [SIP participant attributes](https://docs.livekit.io/reference/telephony/sip-participant.md#sip-attributes).

## Custom caller ID

You can set a custom caller ID for outbound calls using the `display_name` field in the `CreateSIPParticipant` request. By default, if this field isn't included in the request, the phone number is used as the display name. If this field is set to an empty string, most SIP trunking providers issue a Caller ID Name (CNAM) lookup and use the result as the display name.

> ℹ️ **SIP provider support**
> 
> Your SIP provider must support custom caller ID for the `display_name` value to be used. Confirm with your specific provider to verify support.

**LiveKit CLI**:

```json
{
  "sip_trunk_id": "<your-trunk-id>",
  "sip_call_to": "<phone-number-to-dial>",
  "room_name": "my-sip-room",
  "participant_identity": "sip-test",
  "participant_name": "Test Caller",
  "display_name": "My Custom Display Name"
}

```

---

**Node.js**:

```typescript
const sipParticipantOptions = {
  participantIdentity: 'sip-test',
  participantName: 'Test Caller',
  displayName: 'My Custom Display Name'
};

```

---

**Python**:

```python
  request = CreateSIPParticipantRequest(
    sip_trunk_id = "<trunk_id>",
    sip_call_to = "<phone_number>",
    room_name = "my-sip-room",
    participant_identity = "sip-test",
    participant_name = "Test Caller",
    display_name = "My Custom Display Name"
  )

```

---

**Ruby**:

Custom display name is not yet supported in Ruby.

---

**Go**:

```go
displayName := "My Custom Display Name"

request := &livekit.CreateSIPParticipantRequest {
  SipTrunkId: trunkId,
  SipCallTo: phoneNumber,
  RoomName: roomName,
  ParticipantIdentity: participantIdentity,
  ParticipantName: participantName,
  KrispEnabled: true,
  WaitUntilAnswered: true,
  DisplayName: &displayName,
}

```

---

**Kotlin**:

Custom display name is not yet supported in Kotlin.

## Making a call with extension codes (DTMF)

To make outbound calls with fixed extension codes (DTMF tones), set `dtmf` field in `CreateSIPParticipant` request:

**LiveKit CLI**:

```json
{
  "sip_trunk_id": "<your-trunk-id>",
  "sip_call_to": "<phone-number-to-dial>",
  "dtmf": "*123#ww456",
  "room_name": "my-sip-room",
  "participant_identity": "sip-test",
  "participant_name": "Test Caller"
}

```

---

**Node.js**:

```typescript
const sipParticipantOptions = {
  participantIdentity: 'sip-test',
  participantName: 'Test Caller',
  dtmf: '*123#ww456'
};

```

---

**Python**:

```python
  request = CreateSIPParticipantRequest(
    sip_trunk_id = "<trunk_id>",
    sip_call_to = "<phone_number>",
    room_name = "my-sip-room",
    participant_identity = "sip-test",
    participant_name = "Test Caller",
    dtmf = "*123#ww456"
  )

```

---

**Ruby**:

```ruby
resp = sip_service.create_sip_participant(
    trunk_id,
    number,
    room_name,
    participant_identity: participant_identity,
    participant_name: participant_name,
    dtmf: "*123#ww456"
)

```

---

**Go**:

```go
  request := &livekit.CreateSIPParticipantRequest{
    SipTrunkId: trunkId,
    SipCallTo: phoneNumber,
    RoomName: roomName,
    ParticipantIdentity: participantIdentity,
    ParticipantName: participantName,
    Dtmf: "*123#ww456",
  }

```

---

**Kotlin**:

```kotlin
val options = CreateSipParticipantOptions(
    participantIdentity = "sip-test",
    participantName = "Test Caller",
    dtmf = "*123#ww456"
)

sipClient.createSipParticipant(trunkId, phoneNumber, roomName, options).execute()

```

> 💡 **Tip**
> 
> Character `w` can be used to delay DTMF by 0.5 sec.

This example dials a specified number and sends the following DTMF tones:

- `*123#`
- Wait 1 sec
- `456`

## Playing dial tone while the call is dialing

SIP participants emit no audio by default while the call connects. This can be changed by setting `play_dialtone` field in `CreateSIPParticipant` request:

**LiveKit CLI**:

```json
{
  "sip_trunk_id": "<your-trunk-id>",
  "sip_call_to": "<phone-number-to-dial>",
  "room_name": "my-sip-room",
  "participant_identity": "sip-test",
  "participant_name": "Test Caller",
  "play_dialtone": true
}

```

---

**Node.js**:

```typescript
const sipParticipantOptions = {
  participantIdentity: 'sip-test',
  participantName: 'Test Caller',
  playDialtone: true
};

```

---

**Python**:

```python
  request = CreateSIPParticipantRequest(
    sip_trunk_id = "<trunk_id>",
    sip_call_to = "<phone_number>",
    room_name = "my-sip-room",
    participant_identity = "sip-test",
    participant_name = "Test Caller",
    play_dialtone = True
  )

```

---

**Ruby**:

```ruby
resp = sip_service.create_sip_participant(
    trunk_id,
    number,
    room_name,
    participant_identity: participant_identity,
    participant_name: participant_name,
    play_dialtone: true
)

```

---

**Go**:

```go
  request := &livekit.CreateSIPParticipantRequest{
    SipTrunkId: trunkId,
    SipCallTo: phoneNumber,
    RoomName: roomName,
    ParticipantIdentity: participantIdentity,
    ParticipantName: participantName,
    PlayDialtone: true,
  }

```

---

**Kotlin**:

```kotlin
val options = CreateSipParticipantOptions(
    participantIdentity = "sip-test",
    participantName = "Test Caller",
    playDialtone = true
)

```

If `play_dialtone` is enabled, the SIP Participant plays a dial tone to the room until the phone is picked up.

## Hang up

To let your agent end the call for all participants, add the prebuilt [EndCallTool](https://docs.livekit.io/agents/prebuilt/tools/end-call-tool.md) to your agent's tools (Python only). The tool shuts down the session and can delete the room to disconnect everyone. If the agent session ends but the room is not deleted, the user continues to hear silence until they hang up.

For a custom implementation or Node.js, use the `delete_room` API. The following example implements a basic `hangup_call` function you can use as a starting point:

**Python**:

```python
# Add these imports at the top of your file
from livekit import api, rtc
from livekit.agents import get_job_context

# Add this function definition anywhere
async def hangup_call():
    ctx = get_job_context()
    if ctx is None:
        # Not running in a job context
        return
    
    await ctx.api.room.delete_room(
        api.DeleteRoomRequest(
            room=ctx.room.name,
        )
    )

class MyAgent(Agent):
    ...

    # to hang up the call as part of a function call
    @function_tool
    async def end_call(self, ctx: RunContext):
        """Called when the user wants to end the call"""
        await ctx.wait_for_playout() # let the agent finish speaking

        await hangup_call()

```

---

**Node.js**:

```typescript
import { RoomServiceClient } from 'livekit-server-sdk';
import { getJobContext } from '@livekit/agents';

const hangUpCall = async () => {
  const jobContext = getJobContext();
  if (!jobContext) {
    return;
  }

  const roomServiceClient = new RoomServiceClient(process.env.LIVEKIT_URL!,
                                                  process.env.LIVEKIT_API_KEY!,
                                                  process.env.LIVEKIT_API_SECRET!);

  if (jobContext.room.name) {
    await roomServiceClient.deleteRoom(
      jobContext.room.name,
    );
  }
}

class MyAgent extends voice.Agent {
  constructor() {
    super({
        instructions: 'You are a helpful voice AI assistant.',
        // ... existing code ...
        tools: {
          hangUpCall: llm.tool({
            description: 'Call this tool if the user wants to hang up the call.',
            execute: async (_, { ctx }: llm.ToolOptions<UserData>) => {
              await hangUpCall();
              return "Hung up the call";
            },
          }),
        },
    });
 }
}

```

---

This document was rendered at 2026-04-13T11:30:59.088Z.
For the latest version of this document, see [https://docs.livekit.io/telephony/making-calls/outbound-calls.md](https://docs.livekit.io/telephony/making-calls/outbound-calls.md).

To explore all LiveKit documentation, see [llms.txt](https://docs.livekit.io/llms.txt).