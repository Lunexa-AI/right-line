# WhatsApp Integration Testing Guide

## Quick Start for Testing

### Step 1: Get WhatsApp Test Credentials

1. Go to [Meta for Developers](https://developers.facebook.com)
2. Create a new app (select "Business" type)
3. Add WhatsApp product
4. In WhatsApp > Getting Started, you'll find:
   - **Test phone number** (provided by Meta for free)
   - **Phone number ID** (copy this)
   - **Temporary access token** (valid for 24 hours)
   - You can add up to 5 test recipient numbers

### Step 2: Set Environment Variables

Create a `.env.whatsapp` file:

```bash
# Required WhatsApp settings
export RIGHTLINE_WHATSAPP_TOKEN="YOUR_ACCESS_TOKEN_HERE"
export RIGHTLINE_WHATSAPP_PHONE_ID="YOUR_PHONE_NUMBER_ID_HERE"
export RIGHTLINE_WHATSAPP_VERIFY_TOKEN="any_random_string_you_create"

# Other required settings
export RIGHTLINE_SECRET_KEY="test_secret_key_that_is_at_least_32_characters_long"
export RIGHTLINE_DATABASE_URL="postgresql://test"
export RIGHTLINE_REDIS_URL="redis://test"
```

### Step 3: Install and Setup Ngrok

```bash
# Install ngrok (macOS)
brew install ngrok

# Or download from https://ngrok.com/download
```

### Step 4: Start the Server

```bash
# Terminal 1: Start RightLine
source .env.whatsapp
source venv/bin/activate
python3 -m services.api.main
```

### Step 5: Expose Local Server

```bash
# Terminal 2: Start ngrok
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Step 6: Configure Webhook in Meta

1. Go to WhatsApp > Configuration > Webhooks
2. Click "Edit" on Callback URL
3. Enter:
   - **Callback URL**: `https://your-ngrok-url.ngrok.io/webhook`
   - **Verify Token**: Same value as `RIGHTLINE_WHATSAPP_VERIFY_TOKEN`
4. Click "Verify and Save"
5. Subscribe to `messages` webhook field

### Step 7: Test the Integration

1. Add your personal WhatsApp number to test numbers in Meta console
2. Send a message to the test business number
3. Try these test messages:
   - "What is the minimum wage?"
   - "HELP"
   - "How much leave am I entitled to?"

## Testing Without Real WhatsApp (Local Only)

You can test the webhook endpoints directly:

### Test Webhook Verification
```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test_challenge"
```

### Test Message Processing
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "ACCOUNT_ID",
      "changes": [{
        "field": "messages",
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {
            "display_phone_number": "15551234567",
            "phone_number_id": "PHONE_ID"
          },
          "messages": [{
            "from": "263771234567",
            "id": "MESSAGE_ID",
            "timestamp": "1234567890",
            "type": "text",
            "text": {"body": "What is the minimum wage?"}
          }]
        }
      }]
    }]
  }'
```

## Common Issues and Solutions

### Issue: Webhook verification fails
- **Solution**: Ensure `RIGHTLINE_WHATSAPP_VERIFY_TOKEN` matches what you entered in Meta console

### Issue: Messages not received
- **Solution**: 
  - Check ngrok is running and URL is correct
  - Ensure webhook is subscribed to `messages` field
  - Check server logs for errors

### Issue: Can't send replies
- **Solution**: 
  - Verify access token is valid (regenerate if expired)
  - Check phone number ID is correct
  - Ensure test number is added in Meta console

## Security Notes for Production

⚠️ **For production deployment:**
- Never commit tokens to git
- Use environment variables or secrets manager
- Implement rate limiting
- Use permanent access tokens (not test tokens)
- Set up proper SSL certificates (not ngrok)
- Implement webhook signature verification

## Useful Links

- [WhatsApp Cloud API Docs](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Webhook Setup Guide](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks)
- [Message Templates](https://developers.facebook.com/docs/whatsapp/api/messages)
- [Ngrok Documentation](https://ngrok.com/docs)

## Testing Checklist

- [ ] Meta Developer account created
- [ ] WhatsApp product added to app
- [ ] Test phone number obtained
- [ ] Access token generated
- [ ] Environment variables set
- [ ] Server running locally
- [ ] Ngrok tunnel established
- [ ] Webhook configured in Meta
- [ ] Webhook verified successfully
- [ ] Test message sent and received
- [ ] Response received in WhatsApp

---

*Note: Test tokens expire after 24 hours. For extended testing, you'll need to regenerate them or set up permanent tokens.*
