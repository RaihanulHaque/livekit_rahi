LiveKit docs › Telephony › SIP handshake

---

# SIP handshake

> Understanding the SIP handshake process.

The SIP handshake is the sequence of messages exchanged between endpoints to establish a call. This process negotiates capabilities, authenticates endpoints, and sets up the media channels for the call.

To learn more, see the full SIP specification at [RFC 3261](https://datatracker.ietf.org/doc/html/rfc3261).

## SIP handshake flow

The following sections refer to caller **A** who is dialing callee **B**.

### Step 1. Caller sends an INVITE

The `INVITE` request initiates the call. This is when the call is **started**.

**A** → **B**: Sends an `INVITE` request.

The `INVITE` request typically includes the following headers:

- `From`: identifies the logical initiator of the call and includes a tag that helps uniquely identify the dialog.
- `To`: identifies the intended recipient of the call. The callee adds a tag in responses to complete dialog identification.
- `Call-ID`: A globally unique identifier for the call, shared by all messages within the same dialog.
- `Via`: Records the transport path taken by the request and ensures responses are routed back to the sender.
- `Contact`: Provides a direct SIP URI where the caller can be reached for future requests within the dialog.
- Optional headers:

- `Authorization` (if credentials are already known)
- Custom headers

The [Session Description Protocol (SDP) offer](https://docs.livekit.io/reference/telephony/codecs-negotiation.md#sdp-offer) is typically included in the message body of the `INVITE` request. It's used to negotiate media capabilities between the caller and callee. The offer includes all audio codecs the caller supports, in order of preference, and other media capabilities. To learn more, see [Codec negotiation](https://docs.livekit.io/reference/telephony/codecs-negotiation.md).

> 💡 **Call is started**
> 
> This is when the call is "Started".

#### Optional authentication challenge

If authentication is required, the callee returns a response that requires the caller to send a second `INVITE` request with an `Authorization` header:

1. **A** → **B**: Sends an `INVITE` request.
2. **B** → **A**: Sends a `401 Unauthorized` or `407 Proxy Authentication Required` response.
3. **A** → **B**: Resends the `INVITE` request with an `Authorization` header.

This is the normal flow for a digest authentication challenge and is _not_ a failure. The second `INVITE` request uses the same `Call-ID` with an `Authorization` header.

### Step 2. Callee sends provisional responses

After the callee receives a valid `INVITE` request, they send a provisional response to indicate the call is being processed.

#### Step 2.1 Immediate processing acknowledgment

**B** → **A**: Sends `100 Trying` response.

- Indicates the INVITE was received and is being processed.
- Prevents retransmissions over UDP.
- Optional response, but very common.

#### Step 2.2 Alerting / early media

The following responses indicate the INVITE has been received and the call is being processed.

**B** → **A**: Sends a `180 Ringing` or `183 Session Progress` response.

- `180 Ringing`: Alerting callee by ringing phone. No media is flowing yet and no SDP is needed.
- `183 Session Progress`: Phone is ringing and establishes early media before the call is answered. Often includes SDP.
- No ACK is sent.

> 💡 **Custom audio**
> 
> A `183 Session Progress` response is typically used to play custom audio instead of the default ringing sound.

### Step 3. Callee accepts the call

The callee accepts the call by sending a final response.

**B** → **A**: Sends a `200 OK` response.

This is the final response to the `INVITE` that contains the [SDP answer](https://docs.livekit.io/reference/telephony/codecs-negotiation.md#sdp-answer).

> 💡 **Call is connected**
> 
> This is when the call is "Connected".

### Step 4. Caller acknowledges the final response

The caller must acknowledge the final response to complete the call.

**A** → **B**: Sends an `ACK` request.

- `ACK` request is mandatory.
- Completes the `INVITE` transaction.
- Media can now flow between the caller and callee.

### Step 5. Ending the call

Either party can end the call by sending a `BYE` request. This stops all media streams and releases call resources such as RTP ports, codecs, and more.

**A** → **B**: Sends a `BYE` request to end the call.

A `BYE` request must meet the following criteria:

- Include the same `Call-ID`, `From` tag, and `To` tag used in the dialog.
- Be acknowledged by the recipient with a `200 OK` response.

> 💡 **Call is ended**
> 
> This is when the call is "Ended".

## Additional resources

The following resources provide additional details about the topics covered in this guide.

- **[SIP primer](https://docs.livekit.io/reference/telephony/sip-primer.md)**: Learn how SIP integrates with LiveKit to enable seamless call routing between telephony systems and LiveKit rooms.

- **[Audio codecs negotiation](https://docs.livekit.io/reference/telephony/codecs-negotiation.md)**: Learn how audio codecs are negotiated during SIP calls and which codecs LiveKit supports.

---

This document was rendered at 2026-04-13T12:51:42.714Z.
For the latest version of this document, see [https://docs.livekit.io/reference/telephony/sip-handshake.md](https://docs.livekit.io/reference/telephony/sip-handshake.md).

To explore all LiveKit documentation, see [llms.txt](https://docs.livekit.io/llms.txt).