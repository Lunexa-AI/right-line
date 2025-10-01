"""
Long-term memory for user patterns and preferences.

Tracks user behavior over time in Firestore for:
- Expertise level detection
- Legal interest areas
- Query complexity patterns
- Response preferences
- Personalization

Follows .cursorrules: async-first, incremental updates, privacy-aware.
"""

from datetime import datetime
from typing import Dict, Any, List

import structlog

logger = structlog.get_logger(__name__)


class LongTermMemory:
    """
    Tracks user patterns and preferences over time using Firestore.
    
    Features:
    - Incremental profile updates
    - Expertise level tracking
    - Interest area frequency
    - Query pattern analysis
    
    Usage:
        memory = LongTermMemory(firestore_client)
        profile = await memory.get_user_profile(user_id)
        await memory.update_after_query(user_id, query_metadata)
        context = await memory.get_personalization_context(user_id)
    """
    
    def __init__(self, firestore_client):
        """
        Initialize long-term memory.
        
        Args:
            firestore_client: Async Firestore client
        """
        self.firestore = firestore_client
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's long-term profile.
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile dict (creates default if not exists)
        """
        doc_ref = self.firestore.collection("users").document(user_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            # Create default profile
            default_profile = {
                "user_id": user_id,
                "legal_interests": [],
                "area_frequency": {},
                "query_count": 0,
                "expertise_level": "citizen",
                "typical_complexity": "moderate",
                "preferred_response_length": "standard",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            logger.info("Created default user profile", user_id=user_id)
            return default_profile
        
        return doc.to_dict()
    
    async def update_after_query(
        self,
        user_id: str,
        query: str,
        complexity: str,
        legal_areas: List[str],
        user_type: str
    ):
        """
        Update user profile after each query (incremental).
        
        Args:
            user_id: User identifier
            query: Query text (for pattern analysis)
            complexity: Query complexity
            legal_areas: Legal areas covered
            user_type: Detected user type
        """
        try:
            doc_ref = self.firestore.collection("users").document(user_id)
            
            # Import Firestore helpers for increments
            from google.cloud.firestore_v1 import ArrayUnion, Increment
            
            # Build update dict
            update_data = {
                "query_count": Increment(1),
                "updated_at": datetime.utcnow().isoformat(),
                "last_query_complexity": complexity,
                "detected_user_type": user_type
            }
            
            # Add legal areas to interests
            if legal_areas:
                update_data["legal_interests"] = ArrayUnion(legal_areas)
                
                # Increment frequency for first area
                for area in legal_areas[:1]:  # Just first area to avoid too many fields
                    update_data[f"area_frequency.{area}"] = Increment(1)
            
            await doc_ref.update(update_data)
            
            logger.debug(
                "User profile updated",
                user_id=user_id,
                complexity=complexity,
                legal_areas=legal_areas
            )
            
        except Exception as e:
            logger.error("Failed to update user profile", error=str(e), user_id=user_id)
    
    async def get_personalization_context(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get personalization context for query processing.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with expertise level, interests, typical complexity, etc.
        """
        profile = await self.get_user_profile(user_id)
        
        # Extract top interests by frequency
        area_freq = profile.get("area_frequency", {})
        top_interests = sorted(
            area_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 interests
        
        return {
            "expertise_level": profile.get("expertise_level", "citizen"),
            "typical_complexity": profile.get("typical_complexity", "moderate"),
            "top_legal_interests": [area for area, count in top_interests],
            "query_count": profile.get("query_count", 0),
            "is_returning_user": profile.get("query_count", 0) > 5
        }
