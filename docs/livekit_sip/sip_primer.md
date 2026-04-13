LiveKit docs › Telephony › SIP primer

---

# SIP primer

> Learn how SIP calls flow in LiveKit to connect traditional telephony with realtime communications.

## Overview

[Session Initiation Protocol](https://datatracker.ietf.org/doc/html/rfc3261) (SIP) is a signaling protocol for starting, managing, and ending realtime voice and video calls over IP networks. LiveKit uses SIP to connect traditional telephony systems—like desk phones, softphones, and PSTN networks—to WebRTC-based applications. With LiveKit Telephony, you can route SIP calls into or out of LiveKit rooms for realtime communication.

SIP handles call setup and control, negotiating media capabilities and establishing the connection between caller and callee. After the connection is established, audio flows over Real-time Transport Protocol (RTP).

The following sections describe the step-by-step flow for how SIP integrates with LiveKit to enable seamless call routing between telephony systems and LiveKit rooms.

## How calls connect

The following diagram describes how calls are connected to LiveKit for both [inbound](#how-inbound-calls-connect) and [outbound](#how-outbound-calls-connect) calls.

```mermaid
flowchart TD
%% Inbound flow
subgraph SG1 [Inbound Call]
direction LR
I1[User dials phone number]
I2[Call enters PSTN]
I3[SIP Provider]
I4[LiveKit SIP Endpoint]
I5[Agent picks up call]
end%% Outbound flow
subgraph SG2 [Outbound Call]
direction LR
O1[Initiate call in LiveKit]
O2[LiveKit SIP → SIP Provider]
O3[Call enters PSTN]
O4[User picks up call]
end%% Shared steps
S1[SIP Handshake Complete]
S2[Media Transfer starts]
S3[LiveKit Agent receives audio and responds]I1 ~~~ O2%% Inbound wiring
I1 --> I2I2 -->|Standard trunking| I3
I3 -->|SIP INVITE| I4I2 -->|LiveKit Phone Numbers| I4
I4 --> I5
I5 --> S1%% Outbound wiring
O1 --> O2
O2 --> O3
O3 -->|PSTN routes call to user's phone| O4
O4 --> S1%% Shared flow
S1 --> S2
S2 --> S3
```

### How inbound calls connect

The following sections outline the initial setup for an inbound connection.

#### User dials a phone number

This could be from a mobile phone, desk phone, or softphone.

#### Call enters the PSTN

The [Public Switched Telephone Network](https://en.wikipedia.org/wiki/Public_switched_telephone_network) (PSTN) is the global phone network. The PSTN routes the call to the SIP trunk (Twilio, Telnyx, and others) associated with the destination number.

> 💡 **LiveKit Phone Numbers**
> 
> With [LiveKit Phone Numbers](https://docs.livekit.io/telephony/start/phone-numbers.md), the call skips all trunking and goes straight to LiveKit.

#### SIP provider → LiveKit SIP endpoint

The SIP provider receives the PSTN call and sees you've configured a LiveKit SIP endpoint as the Origination URI. The SIP provider initiates a SIP call to LiveKit by sending an `INVITE` request.

> ℹ️ **SIP provider configuration**
> 
> Your SIP trunking provider must be configured to use the LiveKit SIP endpoint. To learn more, see [SIP trunk setup](https://docs.livekit.io/telephony/start/sip-trunk-setup.md).

#### Agent picks up the call

The agent picks up the call by joining the room, but audio is not exchanged until the SIP handshake is complete.

> ℹ️ **Agent setup**
> 
> Your agent must be configured to join the room when a call is received. To learn more, see [Agent dispatch](https://docs.livekit.io/agents/server/agent-dispatch.md).

The final steps to complete an inbound call connection are shared with the outbound call connection. See [Completing the call connection](#completing-the-call-connection) for details.

### How outbound calls connect

The following sections outline the initial setup for an outbound connection.

#### Initiate a call from LiveKit

Use the SIP API to initiate a call. LiveKit validates the request.

> ℹ️ **How to initiate a call**
> 
> You can make a call from LiveKit using the SIP API or the CLI. To learn more, see [Making outbound calls](https://docs.livekit.io/telephony/making-calls.md).

#### LiveKit SIP → SIP provider

LiveKit initiates a SIP session based on the request.

> ℹ️ **SIP provider configuration**
> 
> You must have an [outbound trunk](https://docs.livekit.io/telephony/making-calls/outbound-trunk.md) and [configure your SIP trunking provider](https://docs.livekit.io/telephony/start/sip-trunk-setup.md) to use the LiveKit SIP endpoint.

#### Call enters the PSTN

The SIP trunking provider routes the call to the PSTN, which routes it to the user's phone.

#### User picks up the call

When the user picks up the call, a `200 OK` response is sent back to LiveKit. Depending on the device, the initial response might be different:

- If the user's device is a softphone or desk phone, a `200 OK` response is sent.
- If it's a mobile phone, the equivalent of a `200 OK`—Answer Message (ANM)—is sent using Signaling System 7 (SS7) protocol to the cellphone provider. This signal is later converted to a `200 OK` and sent to LiveKit.

The final steps in completing an outbound call connection are shared with the inbound call connection. See [Completing the call connection](#completing-the-call-connection) for details.

### Completing the call connection

Once the initial path is established (via either inbound or outbound flow), the following steps finalize the connection.

#### Provider and LiveKit complete the SIP handshake

A [SIP handshake](#sip-handshake) is the sequence of request-response messages exchanged between endpoints to establish a call. The handshake negotiates capabilities (for example, which codecs to use when exchanging media), authenticates endpoints (if required), and sets up the media connection for the call.

#### Media transfer

Once the SIP handshake is complete, the caller and callee exchange audio data via RTP or Secure RTP (SRTP) packets. Media is bridged between the caller and LiveKit's internal media pipeline.

> ⚠️ **Media timeout**
> 
> If the first RTP packet isn't received within 30 seconds (or, if at least one RTP packet has already been received, 15 seconds), the call is disconnected with a `media timeout` error.

#### Agent receives audio and responds

Audio flows from the caller to the agent via RTP. Agent-generated audio flows back to the caller via RTP.

> ℹ️ **Agent setup**
> 
> Your agent must be running and dispatched to the LiveKit room the caller or callee is in. Alternatively, for outbound calls, the agent can initiate the phone call. To learn more, see [Agents telephony integration](https://docs.livekit.io/frontends/telephony/agents.md).

### SIP handshake and audio codecs negotiation

The SIP handshake is a series of messages exchanged between caller and callee that negotiates capabilities and establishes the connection. The capabilities negotiation is done using Session Description Protocol (SDP) as part of the SIP handshake.

An audio codec is part of the negotiated capabilities during the SIP handshake. It defines how voice audio is compressed, encoded, transmitted, and decoded during a call. In SIP calls, codecs determine the audio quality, bandwidth usage, and compatibility between endpoints. Choosing the right codec matters because both sides must support the same codec to exchange audio. To learn more, see [Additional resources](#additional-resources).

## Additional resources

The following resources provide additional details about the topics covered in this guide.

- **[SIP Handshake](https://docs.livekit.io/reference/telephony/sip-handshake.md)**: Detailed steps in the SIP handshake process.

- **[Audio codecs negotiation](https://docs.livekit.io/reference/telephony/codecs-negotiation.md)**: Learn how audio codecs are negotiated during SIP calls and which codecs LiveKit supports.

## Next steps

Learn more about how to set up inbound and outbound calls with LiveKit.

- **[Accepting inbound calls](https://docs.livekit.io/telephony/accepting-calls.md)**: Learn how to set up inbound calls with LiveKit.

- **[Making outbound calls](https://docs.livekit.io/telephony/making-calls.md)**: Learn how to set up outbound calls with LiveKit.

- **[LiveKit Phone Numbers](https://docs.livekit.io/telephony/start/phone-numbers.md)**: Purchase a phone number through LiveKit Phone Numbers for inbound calls.

- **[Agents telephony integration](https://docs.livekit.io/agents/start/telephony.md)**: Learn how to receive and make calls with a voice AI agent

---

This document was rendered at 2026-04-13T12:51:05.893Z.
For the latest version of this document, see [https://docs.livekit.io/reference/telephony/sip-primer.md](https://docs.livekit.io/reference/telephony/sip-primer.md).

To explore all LiveKit documentation, see [llms.txt](https://docs.livekit.io/llms.txt).