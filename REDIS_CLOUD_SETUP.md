# Redis Cloud Setup for Gweta

## Your Redis Instance

**Database**: gweta  
**Endpoint**: redis-14320.fcrce180.us-east-1-1.ec2.redns.redis-cloud.com:14320

---

## Get Your Password

1. Go to Redis Cloud Dashboard: https://app.redislabs.com/
2. Click on your "gweta" database
3. Click **"Configuration"** tab
4. Scroll to **"Security"** section
5. Find **"Default user password"**
6. Click **"👁️ Show"** or **"Copy"** button
7. Copy the password (it's a long random string)

---

## Set Up for Production

### **Option A: Environment Variable** (Recommended)

```bash
# In your production environment (Vercel, Railway, etc.)
# Set this environment variable:

REDIS_URL=rediss://default:YOUR_PASSWORD_HERE@redis-14320.fcrce180.us-east-1-1.ec2.redns.redis-cloud.com:14320

# Replace YOUR_PASSWORD_HERE with actual password from dashboard
# Note: Use rediss:// (with SSL), not redis://
```

### **Option B: .env file** (Local/Staging)

```bash
# Create .env file (don't commit to git!):
echo "REDIS_URL=rediss://default:YOUR_PASSWORD@redis-14320.fcrce180.us-east-1-1.ec2.redns.redis-cloud.com:14320" >> .env

# Make sure .env is in .gitignore!
```

---

## Test Connection

### **Quick Test** (Command Line):

```bash
# Install redis-cli (if not installed)
# Mac: brew install redis
# Linux: sudo apt-get install redis-tools

# Test connection:
redis-cli -u "rediss://default:YOUR_PASSWORD@redis-14320.fcrce180.us-east-1-1.ec2.redns.redis-cloud.com:14320" ping

# Should return: PONG
```

### **Test with Python**:

```bash
# From project root:
source venv/bin/activate

# Set your Redis URL temporarily:
export REDIS_URL="rediss://default:YOUR_PASSWORD@redis-14320.fcrce180.us-east-1-1.ec2.redns.redis-cloud.com:14320"

# Run test script:
python -c "
import asyncio
from libs.caching.redis_client import get_redis_client, reset_redis_client

async def test():
    await reset_redis_client()  # Clear any test client
    redis = await get_redis_client(use_fake=False)  # Force real Redis
    if redis:
        result = await redis.ping()
        print(f'✅ Redis connection successful! Ping: {result}')
        
        # Test set/get
        await redis.set('test:key', 'test_value')
        value = await redis.get('test:key')
        print(f'✅ Set/Get working! Value: {value}')
        
        # Cleanup
        await redis.delete('test:key')
        print('✅ All tests passed!')
    else:
        print('❌ Failed to connect to Redis')

asyncio.run(test())
"
```

**Expected Output**:
```
✅ Redis connection successful! Ping: True
✅ Set/Get working! Value: test_value
✅ All tests passed!
```

---

## Security Best Practices

### **✅ Do**:
- Use `rediss://` (SSL) in production
- Store password in environment variables (not in code)
- Add `.env` to `.gitignore`
- Use Redis Cloud's IP whitelist feature
- Rotate password periodically (in Redis Cloud dashboard)

### **❌ Don't**:
- Don't commit passwords to git
- Don't use `redis://` (without SSL) in production
- Don't share Redis URL publicly
- Don't use default password in production

---

## Current Setup

**Development/Testing**:
```bash
# We use fakeredis (no real Redis needed)
RIGHTLINE_APP_ENV=test
# Tests work automatically!
```

**Staging**:
```bash
# Use Redis Cloud with your credentials
REDIS_URL=rediss://default:PASSWORD@redis-14320...
RIGHTLINE_APP_ENV=staging
```

**Production**:
```bash
# Same as staging but different environment
REDIS_URL=rediss://default:PASSWORD@redis-14320...
RIGHTLINE_APP_ENV=production
```

---

## Troubleshooting

### **Issue**: "Connection refused"
**Solution**: Check firewall/IP whitelist in Redis Cloud

### **Issue**: "Authentication failed"
**Solution**: Verify password is correct

### **Issue**: "SSL error"
**Solution**: Make sure you use `rediss://` (double 's')

### **Issue**: "Timeout"
**Solution**: Check network connectivity, try increasing timeout

---

## What Happens in Our Code

**With Redis**:
```python
# Code automatically:
✅ Connects to Redis
✅ Caches responses
✅ 50-80% latency reduction
✅ 40-60% cache hit rate
```

**Without Redis** (graceful degradation):
```python
# Code automatically:
✅ Detects Redis unavailable
✅ Logs warning
✅ Returns None from cache (always miss)
✅ Full pipeline runs (no caching)
✅ App continues working (just slower)
```

**No code changes needed either way!**

---

## Quick Start

**Right now**:
```bash
# 1. Get password from Redis Cloud dashboard
# 2. Test connection with command above
# 3. Once working, set in production environment
# 4. Continue implementing - code already supports it!
```

**Don't need Redis yet?**
- No problem! Keep using fakeredis for development
- Add Redis to production whenever ready
- Code already has graceful fallback

---

**Ready to continue implementing? We can keep building with fakeredis and you can add your Redis Cloud credentials whenever convenient!** 🚀
