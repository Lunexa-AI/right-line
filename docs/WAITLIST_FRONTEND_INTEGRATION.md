# Waitlist API - Frontend Integration Guide

> **📋 Complete integration guide for frontend developers**

## 🎯 Overview

The waitlist API allows users to sign up for early access without authentication. It includes bot protection, rate limiting, and comprehensive analytics.

**Base URL**: `https://your-domain.com/api` (or `http://localhost:8000/api` for development)

---

## 📡 API Endpoint

### `POST /v1/waitlist`

Add an email to the pre-launch waitlist.

#### Request Headers
```
Content-Type: application/json
```

#### Request Body
```json
{
  "email": "user@example.com",     // Required: Valid email address
  "source": "web"                  // Optional: Tracking source (defaults to "web")
}
```

#### Request Validation
- **Email**: Must be valid email format, max 254 characters
- **Source**: Optional, max 50 characters, alphanumeric/dash/underscore only
- **Request Size**: Max 1KB total

---

## ✅ Success Responses

### New Signup (201 Created)
```json
{
  "success": true,
  "message": "Successfully added to waitlist!",
  "already_subscribed": false,
  "waitlist_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Duplicate Email (201 Created)
```json
{
  "success": true,
  "message": "You're already on the waitlist!",
  "already_subscribed": true,
  "waitlist_id": null
}
```

---

## ❌ Error Responses

### Validation Error (422)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address"
    }
  ]
}
```

### Rate Limited (429)
```json
{
  "detail": "Too many requests. Please wait a moment before trying again."
}
```

### Server Error (500/503)
```json
{
  "detail": "Service temporarily unavailable. Please try again in a moment."
}
```

---

## 🛡️ Security Features

### Bot Protection (Honeypot)
Add a hidden field to your form for bot detection:

```html
<!-- IMPORTANT: Hidden field for bot detection -->
<input type="text" name="website" style="display:none;" tabindex="-1" autocomplete="off">
```

**JavaScript Example:**
```javascript
// Ensure honeypot field is empty (bots often fill all fields)
document.querySelector('input[name="website"]').value = '';
```

### Rate Limiting
- **Per minute**: 2 requests per IP
- **Per hour**: 5 requests per IP
- Automatic temporary bans for bot detection

---

## 💻 Frontend Implementation Examples

### Vanilla JavaScript
```javascript
async function joinWaitlist(email, source = 'web') {
  try {
    // Ensure honeypot field is empty
    const honeypot = document.querySelector('input[name="website"]');
    if (honeypot) honeypot.value = '';
    
    const response = await fetch('/api/v1/waitlist', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        source: source
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      if (data.already_subscribed) {
        showMessage('You\'re already on the waitlist! 🎉', 'info');
      } else {
        showMessage('Successfully added to waitlist! 🚀', 'success');
        // Optional: Track conversion
        analytics.track('waitlist_signup', { source: source });
      }
      return { success: true, data };
    } else {
      // Handle specific errors
      if (response.status === 422) {
        showMessage('Please enter a valid email address', 'error');
      } else if (response.status === 429) {
        showMessage('Too many requests. Please try again later.', 'warning');
      } else {
        showMessage('Something went wrong. Please try again.', 'error');
      }
      return { success: false, error: data };
    }
  } catch (error) {
    console.error('Waitlist signup error:', error);
    showMessage('Network error. Please check your connection.', 'error');
    return { success: false, error };
  }
}

// Usage
document.getElementById('waitlist-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('email').value;
  const result = await joinWaitlist(email, 'homepage');
});
```

### React Hook Example
```jsx
import { useState } from 'react';

function useWaitlist() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');

  const joinWaitlist = async (email, source = 'web') => {
    setLoading(true);
    setMessage('');

    try {
      const response = await fetch('/api/v1/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          source
        })
      });

      const data = await response.json();

      if (response.ok) {
        if (data.already_subscribed) {
          setMessage("You're already on the waitlist! 🎉");
          setMessageType('info');
        } else {
          setMessage('Successfully added to waitlist! 🚀');
          setMessageType('success');
        }
        return { success: true, data };
      } else {
        if (response.status === 422) {
          setMessage('Please enter a valid email address');
        } else if (response.status === 429) {
          setMessage('Too many requests. Please try again later.');
        } else {
          setMessage('Something went wrong. Please try again.');
        }
        setMessageType('error');
        return { success: false, error: data };
      }
    } catch (error) {
      setMessage('Network error. Please check your connection.');
      setMessageType('error');
      return { success: false, error };
    } finally {
      setLoading(false);
    }
  };

  return { joinWaitlist, loading, message, messageType };
}

// Usage Component
function WaitlistForm() {
  const { joinWaitlist, loading, message, messageType } = useWaitlist();
  const [email, setEmail] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    await joinWaitlist(email, 'landing-page');
    setEmail(''); // Clear form on success
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Enter your email"
        required
        disabled={loading}
      />
      {/* Hidden honeypot field */}
      <input type="text" name="website" style={{display: 'none'}} tabIndex="-1" />
      
      <button type="submit" disabled={loading || !email}>
        {loading ? 'Joining...' : 'Join Waitlist'}
      </button>
      
      {message && (
        <div className={`message ${messageType}`}>
          {message}
        </div>
      )}
    </form>
  );
}
```

### Vue.js Example
```vue
<template>
  <form @submit.prevent="joinWaitlist">
    <input
      v-model="email"
      type="email"
      placeholder="Enter your email"
      required
      :disabled="loading"
    />
    <!-- Hidden honeypot field -->
    <input type="text" name="website" style="display:none" tabindex="-1" />
    
    <button type="submit" :disabled="loading || !email">
      {{ loading ? 'Joining...' : 'Join Waitlist' }}
    </button>
    
    <div v-if="message" :class="['message', messageType]">
      {{ message }}
    </div>
  </form>
</template>

<script>
export default {
  data() {
    return {
      email: '',
      loading: false,
      message: '',
      messageType: ''
    };
  },
  methods: {
    async joinWaitlist() {
      this.loading = true;
      this.message = '';

      try {
        const response = await fetch('/api/v1/waitlist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: this.email.trim().toLowerCase(),
            source: 'vue-app'
          })
        });

        const data = await response.json();

        if (response.ok) {
          if (data.already_subscribed) {
            this.message = "You're already on the waitlist! 🎉";
            this.messageType = 'info';
          } else {
            this.message = 'Successfully added to waitlist! 🚀';
            this.messageType = 'success';
            this.email = ''; // Clear form
          }
        } else {
          this.handleError(response.status);
        }
      } catch (error) {
        this.message = 'Network error. Please check your connection.';
        this.messageType = 'error';
      } finally {
        this.loading = false;
      }
    },
    
    handleError(status) {
      if (status === 422) {
        this.message = 'Please enter a valid email address';
      } else if (status === 429) {
        this.message = 'Too many requests. Please try again later.';
      } else {
        this.message = 'Something went wrong. Please try again.';
      }
      this.messageType = 'error';
    }
  }
};
</script>
```

---

## 🎨 UX Best Practices

### Loading States
```css
/* Button loading state */
.btn-loading {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-loading::after {
  content: " ";
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #ffffff;
  border-radius: 50%;
  border-top-color: transparent;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### Message Styling
```css
.message {
  padding: 12px 16px;
  border-radius: 6px;
  margin-top: 12px;
  font-size: 14px;
}

.message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.message.info {
  background: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}

.message.warning {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}
```

---

## 📊 Source Tracking

Track signup sources for analytics:

```javascript
// Different sources for tracking
const sources = {
  homepage: 'homepage',
  blog: 'blog-post',
  social: 'social-media',
  email: 'email-campaign',
  referral: 'referral'
};

// Use in form submission
await joinWaitlist(email, sources.homepage);
```

---

## 🧪 Testing

### Local Development
```javascript
// Test with local API
const API_BASE = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:8000/api'
  : '/api';

// Test different scenarios
const testCases = [
  { email: 'test@example.com', source: 'test' },
  { email: 'invalid-email', source: 'test' }, // Should fail
  { email: 'duplicate@example.com', source: 'test' }, // Should show already subscribed
];
```

### Error Handling Test
```javascript
// Simulate network error
const mockNetworkError = () => {
  // Temporarily disable network or use service worker to simulate
  navigator.serviceWorker.controller?.postMessage({ type: 'SIMULATE_OFFLINE' });
};
```

---

## 📈 Analytics Integration

### Google Analytics
```javascript
// Track successful signups
if (result.success && !result.data.already_subscribed) {
  gtag('event', 'signup', {
    event_category: 'waitlist',
    event_label: source,
    value: 1
  });
}
```

### Custom Analytics
```javascript
// Track to your analytics service
analytics.track('waitlist_signup', {
  email_hash: btoa(email), // Don't send raw email
  source: source,
  timestamp: new Date().toISOString(),
  already_subscribed: result.data.already_subscribed
});
```

---

## 🔧 Admin Endpoint (Internal Use)

### `GET /v1/admin/waitlist/stats`

Retrieve waitlist statistics (no authentication required for now - add in production).

#### Response
```json
{
  "total_count": 1247,
  "recent_entries": [
    {
      "email": "user@example.com",
      "source": "web",
      "joined_at": "2024-01-15T10:30:00Z"
    }
  ],
  "sources_breakdown": {
    "web": 980,
    "social": 267
  },
  "latest_signup": "2024-01-15T10:30:00Z"
}
```

### Admin Dashboard Example
```javascript
async function getWaitlistStats() {
  try {
    const response = await fetch('/api/v1/admin/waitlist/stats');
    const stats = await response.json();
    
    document.getElementById('total-count').textContent = stats.total_count;
    document.getElementById('latest-signup').textContent = 
      new Date(stats.latest_signup).toLocaleString();
    
    // Display sources breakdown
    const sourcesHtml = Object.entries(stats.sources_breakdown)
      .map(([source, count]) => `<li>${source}: ${count}</li>`)
      .join('');
    document.getElementById('sources-list').innerHTML = sourcesHtml;
    
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}
```

---

## 🚀 Deployment Checklist

### Before Launch
- [ ] Test all error scenarios (invalid email, rate limiting, network errors)
- [ ] Verify honeypot field is properly hidden and empty
- [ ] Test form submission with different email formats
- [ ] Confirm analytics tracking is working
- [ ] Test on different devices and browsers
- [ ] Verify rate limiting behavior
- [ ] Test duplicate email handling

### Production Ready
- [ ] Configure proper CORS headers
- [ ] Set up monitoring for 429/503 errors
- [ ] Add admin authentication to stats endpoint
- [ ] Set up alerts for high error rates
- [ ] Configure proper logging aggregation

---

## 🆘 Troubleshooting

### Common Issues

**422 Validation Error**
- Check email format validation on frontend
- Ensure request body is valid JSON
- Verify Content-Type header

**429 Rate Limited**
- Implement proper error messaging
- Consider adding client-side rate limiting
- Show retry timer to users

**CORS Errors**
- Verify API CORS configuration
- Check request origin matches allowed origins

**Network Errors**
- Implement proper error boundaries
- Add retry logic for transient failures
- Show helpful error messages

### Debug Mode
```javascript
const DEBUG = process.env.NODE_ENV === 'development';

if (DEBUG) {
  console.log('Waitlist request:', { email, source });
  console.log('Response:', response.status, data);
}
```

---

## 📞 Support

For integration questions or issues:
1. Check browser console for errors
2. Verify API endpoint is accessible
3. Test with simple curl command:
   ```bash
   curl -X POST http://localhost:8000/api/v1/waitlist \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","source":"test"}'
   ```

---

**🎉 Happy coding! The waitlist API is ready for frontend integration.**
