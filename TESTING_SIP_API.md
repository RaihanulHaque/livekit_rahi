# Testing the SIP API Implementation

## Quick Start

### 1. Start Services
```bash
docker compose up --build
```

Wait for all services to be healthy:
- Frontend: http://localhost:3033 ✓
- LiveKit: ws://localhost:7880 ✓
- Agent API: http://localhost:8089/sip/trunks ✓
- Redis: localhost:6379 ✓

### 2. Test via Frontend UI
1. Open http://localhost:3033
2. Click the settings icon (⚙️) in top-right
3. Click "Add Phone Number"
4. Fill form:
   - Local Number: `09643234042`
   - System Prompt: `You are a helpful HVAC support agent. Help callers with heating and cooling issues.`
   - STT: `deepgram`
   - LLM: `openai`
   - TTS: `elevenlabs`
5. Click "Add Phone Number"
6. Should see new phone in list

### 3. Test via API (curl)

**Get JWT token first:**
```bash
# The frontend generates a JWT; you can extract it from browser DevTools Network tab
# Or use a dummy token for testing with default_user
export JWT_TOKEN="your-jwt-token-here"
```

**Register a phone number:**
```bash
curl -X POST http://localhost:8089/sip/trunks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "local_number": "09643234043",
    "system_prompt": "You are a sales assistant helping customers. Be friendly and professional.",
    "stt": "deepgram",
    "llm": "openai",
    "tts": "elevenlabs"
  }'
```

Expected response (201):
```json
{
  "local_number": "09643234043",
  "sip_number": "+15551234568",
  "trunk_id": "ST_xxxxxxxxxxxxx",
  "dispatch_rule_id": "SDR_xxxxxxxxxxxxx",
  "system_prompt": "You are a sales assistant...",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

**List all phone numbers:**
```bash
curl -X GET http://localhost:8089/sip/trunks \
  -H "Authorization: Bearer $JWT_TOKEN"
```

Expected response (200):
```json
[
  {
    "local_number": "09643234042",
    "sip_number": "+15551234567",
    "trunk_id": "ST_xxx",
    "status": "active",
    "created_at": 1712973600
  },
  {
    "local_number": "09643234043",
    "sip_number": "+15551234568",
    "trunk_id": "ST_yyy",
    "status": "active",
    "created_at": 1712973601
  }
]
```

**Get specific phone number:**
```bash
curl -X GET http://localhost:8089/sip/trunks/09643234042 \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Update phone configuration:**
```bash
curl -X PATCH http://localhost:8089/sip/trunks/09643234042 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "system_prompt": "Updated: You are now a premium HVAC support specialist with 10+ years experience.",
    "tts": "openai"
  }'
```

**Delete a phone number:**
```bash
curl -X DELETE http://localhost:8089/sip/trunks/09643234042 \
  -H "Authorization: Bearer $JWT_TOKEN"
```

Expected response (200):
```json
{
  "deleted": true,
  "local_number": "09643234042",
  "sip_number": "+15551234567",
  "trunk_id": "ST_xxx"
}
```

---

## Verification Checklist

### Backend
- [ ] `livekit_agent:8089` is accessible
- [ ] SIP API endpoints respond to requests
- [ ] Redis stores trunk configs with correct keys
- [ ] User isolation works (different users see different trunks)
- [ ] Number mapping preserved (local ↔ SIP)
- [ ] JWT auth validates requests

### Frontend
- [ ] Settings icon visible in welcome view
- [ ] SIP Management panel loads
- [ ] Can add phone number via form
- [ ] Phone appears in list after add
- [ ] Can delete phone with confirmation
- [ ] Can navigate back to welcome

### Integration
- [ ] Frontend API proxy (`/api/sip`) works
- [ ] Phone list shows after refresh
- [ ] Multiple concurrent adds work

---

## Debugging

### Check if API is running
```bash
# Should return 401 (auth required) or 200 with error
curl http://localhost:8089/sip/trunks
```

### Check Redis storage
```bash
# Connect to Redis container
docker compose exec redis redis-cli

# List all SIP trunk keys
KEYS "sip:*"

# View specific trunk
GET "sip:default_user:09643234042"
```

### Check agent logs
```bash
# View agent container logs
docker compose logs -f livekit_agent

# Look for "Starting SIP API server on port 8089..."
```

### Check LiveKit API
```bash
# List trunks in LiveKit
docker compose exec livekit_agent python

# Then in Python console:
from livekit import api
import asyncio

async def list_trunks():
    lkapi = api.LiveKitAPI(
        url="ws://livekit:7880",
        api_key="devkey",
        api_secret="secret"
    )
    trunks = await lkapi.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    for t in trunks.items:
        print(f"Trunk {t.sip_trunk_id}: numbers={t.numbers}")
    await lkapi.aclose()

asyncio.run(list_trunks())
```

---

## Common Issues

### "Failed to reach SIP API"
- Check if livekit_agent is running: `docker compose ps`
- Check port 8089 is exposed: `docker compose ps | grep 8089`
- Check container logs: `docker compose logs livekit_agent`

### "Trunk already exists"
- The phone number is already registered
- Use a different local_number or delete first

### "Authorization failed"
- Ensure you're sending a valid JWT token
- For testing, the demo uses "default_user" if no JWT

### Trunks not appearing in list
- Verify Redis is running: `docker compose ps redis`
- Check Redis keys: `docker compose exec redis redis-cli KEYS "sip:*"`

---

## Load Testing (Optional)

Test concurrent phone additions:
```bash
# Add 10 phone numbers concurrently
for i in {1..10}; do
  curl -X POST http://localhost:8089/sip/trunks \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
      \"local_number\": \"0964323404$i\",
      \"system_prompt\": \"You are agent $i\",
      \"stt\": \"deepgram\",
      \"llm\": \"openai\",
      \"tts\": \"elevenlabs\"
    }" &
done
wait

# List all (should show 10+)
curl -X GET http://localhost:8089/sip/trunks \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '. | length'
```

---

## Next Steps

After verification:

1. **Copy to production frontend**:
   - Copy `sip-management-view.tsx` to your Unisense frontend
   - Copy API proxy route to your backend (if separate)

2. **Add database persistence**:
   - Sync Redis to PostgreSQL for durability
   - Add soft delete for audit trail

3. **Enhance security**:
   - Validate JWT properly (decode with shared secret)
   - Add rate limiting to API endpoints
   - Add CORS configuration

4. **Production features**:
   - Phone number pool management
   - Bulk import/export
   - Analytics dashboard
   - Call recordings

---

## Contact & Support

If you encounter issues:
1. Check the logs: `docker compose logs -f livekit_agent`
2. Verify port 8089 is accessible
3. Check Redis connectivity
4. Review CLAUDE.md for API reference
