# Gweta Memory Architecture

## Overview

Two-tier memory system for conversation intelligence and personalization:

1. **Short-Term Memory** (Session/Conversation Context)
2. **Long-Term Memory** (User Patterns and Preferences)

**Design Philosophy**: Enable natural multi-turn conversations and personalized responses while maintaining token efficiency and privacy.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Query Orchestrator                        │
└──────┬──────────────────────────────────────────┬───────────┘
       │                                          │
       ▼                                          ▼
┌──────────────────┐                    ┌──────────────────┐
│  Memory          │                    │  Memory          │
│  Coordinator     │                    │  Updater         │
└────┬─────────┬───┘                    └───────┬──────────┘
     │         │                                 │
     ▼         ▼                                 ▼
┌─────────┐ ┌──────────┐              ┌──────────────────┐
│ Short-  │ │ Long-    │              │ Update both      │
│ Term    │ │ Term     │              │ after query      │
│ Memory  │ │ Memory   │              │ complete         │
└────┬────┘ └────┬─────┘              └──────────────────┘
     │           │
     ▼           ▼
┌─────────┐ ┌──────────┐
│ Redis   │ │Firestore │
│(Session)│ │ (User)   │
└─────────┘ └──────────┘
```

---

## 1. Short-Term Memory (Conversation Context)

### **Purpose**
Track conversation within current session for:
- Pronoun resolution ("it", "this", "that")
- Follow-up question understanding
- Conversation coherence
- Context-aware query rewriting

### **Storage**: Redis (Fast, Ephemeral)
```
Key Pattern: session:{session_id}:messages
Structure: List (newest first)
TTL: 24 hours
Max Size: 10-20 messages (sliding window)
```

### **Data Structure**
```python
{
  "role": "user" | "assistant",
  "content": str,  # Full message text
  "timestamp": datetime,
  "metadata": {
    "legal_areas": List[str],
    "complexity": str,
    "intent": str
  }
}
```

### **Operations**
- `add_message(session_id, role, content, metadata)`
- `get_context(session_id, max_tokens=2000)` → Last N messages within token budget
- `get_last_n_exchanges(session_id, n=3)` → Last N Q&A pairs
- `clear_session(session_id)` → Clear session history

### **Token Budget**: 70% of memory budget (~1400/2000 tokens)

---

## 2. Long-Term Memory (User Patterns)

### **Purpose**
Track user behavior over time for:
- Expertise level detection (citizen vs professional)
- Legal interest areas
- Typical query complexity
- Response style preferences
- Personalization

### **Storage**: Firestore (Persistent, Indexed)
```
Collection: users/{user_id}
Document Structure:
{
  user_id: str,
  legal_interests: List[str],
  area_frequency: Dict[str, int],
  query_count: int,
  expertise_level: "citizen" | "professional",
  typical_complexity: "simple" | "moderate" | "complex" | "expert",
  preferred_response_length: "concise" | "standard" | "detailed",
  created_at: datetime,
  updated_at: datetime,
  last_query_date: datetime
}
```

### **Operations**
- `get_user_profile(user_id)` → Complete profile
- `update_after_query(user_id, query_metadata)` → Incremental update
- `get_personalization_context(user_id)` → Context for query processing
- `detect_expertise_level(user_id)` → Based on query patterns

### **Token Budget**: 30% of memory budget (~600/2000 tokens)

---

## 3. Memory Coordinator

### **Purpose**
Unified interface combining both memory types with intelligent token allocation.

### **Methods**
```python
class MemoryCoordinator:
    def __init__(redis_client, firestore_client):
        self.short_term = ShortTermMemory(redis_client)
        self.long_term = LongTermMemory(firestore_client)
    
    async def get_full_context(user_id, session_id, max_tokens=2000):
        """Get combined memory context."""
        # 70% short-term, 30% long-term
        short_term = await self.short_term.get_context(session_id, 1400)
        long_term = await self.long_term.get_personalization_context(user_id)
        return {conversation, user_profile, tokens_used}
    
    async def update_memories(user_id, session_id, query, response, metadata):
        """Update both memory systems after query."""
        await self.short_term.add_message(...)
        await self.long_term.update_after_query(...)
```

---

## Integration Points

### **1. Query Rewriter** (ARCH-035)
```python
# Get conversation context
memory = await coordinator.get_full_context(user_id, session_id)

# Resolve pronouns
if "it" in query:
    # Look at last assistant response
    last_response = memory['conversation'][-1]
    # Resolve "it" based on context

# Enhance query with context
rewritten = f"{query} [Context: {previous_topic}]"
```

### **2. Intent Classifier** (ARCH-036)
```python
# Get user profile
profile = await coordinator.get_personalization_context(user_id)

# Use patterns for better classification
if profile['expertise_level'] == 'professional':
    user_type = 'professional'
    complexity = profile['typical_complexity']
```

### **3. Synthesis** (ARCH-041)
```python
# Include conversation context
if memory['conversation']:
    prompt += f"\n\nPrevious conversation context: {memory['conversation'][-3:]}"

# Adapt to user preferences
if profile['preferred_response_length'] == 'concise':
    max_tokens = 800
```

### **4. Post-Query Update** (ARCH-037)
```python
# After successful query
await coordinator.update_memories(
    user_id=user_id,
    session_id=session_id,
    query=query,
    response=response,
    metadata={
        'complexity': complexity,
        'legal_areas': legal_areas,
        'user_type': user_type
    }
)
```

---

## Follow-Up Question Handling

### **Detection Patterns**
```python
follow_up_patterns = [
    r"^(what about|how about|and if|but if)",
    r"(it|that|this|those|these)\b",
    r"(as you said|as mentioned)",
    r"^(yes|no|okay)",
    r"(tell me more|explain|clarify)"
]
```

### **Resolution Process**
```
1. Detect follow-up pattern
2. Fetch last 2-3 exchanges
3. Extract topic from previous query/response
4. Resolve references:
   - "it" → specific term from context
   - "what about X" → X in context of previous topic
   - "tell me more" → expand on previous topic
5. Rewrite query to be self-contained
```

---

## Token Budget Management

### **Total Budget**: 2000 tokens for memory

**Allocation**:
- Short-term: 1400 tokens (70%)
  - Last 5-10 exchanges
  - Prioritize recent over old
  - Compress if needed
- Long-term: 600 tokens (30%)
  - Top 5 interest areas
  - Expertise level
  - Preferences summary

**Compression Strategy** (if needed):
```python
# For old messages (>5 exchanges ago)
original_message = "Long detailed legal answer about labour law..." (500 tokens)
compressed = "Discussion about labour law employee rights" (50 tokens)
# Saves: 450 tokens (90% reduction)
```

---

## Privacy & Compliance

### **PII Handling**
- ✅ No PII in short-term cache (only session messages)
- ✅ Long-term profiles anonymized (patterns, not raw queries)
- ✅ Configurable retention policies
- ✅ User data deletion support

### **Data Retention**
- **Short-term**: Auto-delete after 24h (Redis TTL)
- **Long-term**: Configurable retention (default: keep patterns)
- **Right to be forgotten**: Delete user document in Firestore

### **Security**
- Redis: Session-scoped (no cross-user leakage)
- Firestore: User-scoped with security rules
- No sensitive legal content stored permanently

---

## Performance Characteristics

### **Short-Term Memory**:
- **Fetch**: <10ms (Redis)
- **Write**: <5ms (Redis)
- **Size**: ~1KB per message
- **Capacity**: Unlimited (TTL-managed)

### **Long-Term Memory**:
- **Fetch**: <50ms (Firestore)
- **Write**: <100ms (Firestore, incremental)
- **Size**: ~2KB per user profile
- **Capacity**: Unlimited

### **Combined**:
- **Total fetch**: <60ms (parallel)
- **Total write**: <100ms (can be async/background)

---

## Implementation Files

```
libs/memory/
├── __init__.py
├── short_term.py          # ShortTermMemory class
├── long_term.py           # LongTermMemory class
├── coordinator.py         # MemoryCoordinator class
└── compression.py         # Message compression utilities

tests/libs/memory/
├── __init__.py
├── test_short_term.py     # Short-term memory tests
├── test_long_term.py      # Long-term memory tests
├── test_coordinator.py    # Coordinator tests
└── test_follow_ups.py     # Follow-up detection tests
```

---

## Success Metrics

### **Conversation Continuity**:
- Follow-up resolution rate: >90%
- Pronoun resolution accuracy: >85%
- Conversation coherence: >4.5/5

### **Personalization**:
- Expertise detection accuracy: >80%
- Complexity adaptation: >75%
- User satisfaction improvement: +20%

### **Performance**:
- Memory fetch latency: <60ms
- Token budget utilization: <30% of total
- No impact on query latency

---

## Example Scenarios

### **Scenario 1: Follow-Up Question**
```
Turn 1:
User: "What is unfair dismissal?"
AI: [Detailed answer about Labour Act Section 12]
[Store in short-term: topic=unfair_dismissal, doc=Labour_Act_S12]

Turn 2:
User: "What about notice period?"
[Memory provides: previous topic was unfair dismissal]
[Rewrite: "What is the notice period for termination of employment under Labour Act?"]
AI: "Building on our discussion of unfair dismissal, the notice period..."
```

### **Scenario 2: Pronoun Resolution**
```
Turn 1:
User: "What is the Labour Act?"
AI: [Explanation]
[Store: topic=Labour_Act]

Turn 2:
User: "Is it mandatory?"
[Detect: "it" needs resolution]
[Resolve: "it" = "the Labour Act" from context]
[Rewrite: "Is the Labour Act mandatory?"]
AI: "Yes, the Labour Act is binding legislation..."
```

### **Scenario 3: User Profiling**
```
After 10 queries over 2 weeks:
Profile: {
  expertise_level: "professional",
  top_interests: ["employment_law", "company_law"],
  typical_complexity: "complex",
  query_count: 10
}

Next query automatically:
- Uses professional persona
- Provides complex analysis
- References employment law when relevant
```

---

## Architecture Complete ✅

**Defined**:
- ✅ Two-tier memory system (short + long)
- ✅ Storage strategies (Redis + Firestore)
- ✅ Token budget allocation (70/30 split)
- ✅ Integration points (4 nodes)
- ✅ Privacy/compliance approach
- ✅ Performance targets
- ✅ File structure

**Ready for**: ARCH-032 (Implement Short-Term Memory)

---

**Created**: 2024-10-01  
**Status**: Architecture design complete, ready for implementation
