#!/usr/bin/env python3
"""
Analyze query logs to identify gaps in hardcoded responses.

This script analyzes the analytics database to find common queries
that don't match any hardcoded responses, helping identify what
new responses should be added.
"""

import asyncio
import sqlite3
from collections import Counter
from pathlib import Path
from typing import List, Tuple

import structlog

# Setup logging
logger = structlog.get_logger(__name__)

DB_PATH = Path("/data/rightline_analytics.db")


def analyze_unmatched_queries() -> List[Tuple[str, int]]:
    """Analyze queries that didn't match any hardcoded responses."""
    
    if not DB_PATH.exists():
        logger.warning("Analytics database not found", path=str(DB_PATH))
        return []
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        # Get all unmatched queries
        cursor = conn.execute("""
            SELECT query_text, COUNT(*) as count
            FROM query_logs
            WHERE status = 'no_match' OR response_topic IS NULL
            GROUP BY LOWER(query_text)
            ORDER BY count DESC
            LIMIT 50
        """)
        
        unmatched = [(row["query_text"], row["count"]) for row in cursor]
        
        logger.info(f"Found {len(unmatched)} unique unmatched queries")
        
        return unmatched
        
    finally:
        conn.close()


def analyze_query_patterns() -> dict:
    """Analyze common patterns in queries."""
    
    if not DB_PATH.exists():
        return {}
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        # Get all queries
        cursor = conn.execute("SELECT query_text FROM query_logs")
        queries = [row["query_text"].lower() for row in cursor]
        
        # Common keywords
        keywords = []
        for query in queries:
            keywords.extend(query.split())
        
        keyword_counts = Counter(keywords)
        
        # Filter out common words
        stop_words = {
            "the", "is", "at", "which", "on", "a", "an", "and", "or", 
            "but", "in", "with", "to", "for", "of", "as", "from", "by",
            "what", "how", "when", "where", "who", "why", "can", "do",
            "does", "are", "was", "were", "been", "be", "have", "has",
            "had", "will", "would", "could", "should", "may", "might",
            "i", "me", "my", "you", "your", "it", "its", "this", "that"
        }
        
        filtered_keywords = {
            word: count for word, count in keyword_counts.items()
            if word not in stop_words and len(word) > 2 and count > 1
        }
        
        # Sort by frequency
        top_keywords = sorted(
            filtered_keywords.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        return {
            "total_queries": len(queries),
            "unique_queries": len(set(queries)),
            "top_keywords": top_keywords
        }
        
    finally:
        conn.close()


def suggest_new_topics(unmatched: List[Tuple[str, int]]) -> List[str]:
    """Suggest new topics to add based on unmatched queries."""
    
    suggestions = []
    
    # Keywords that suggest specific topics
    topic_keywords = {
        "pension": ["pension", "retirement", "provident", "nssa"],
        "overtime": ["overtime", "extra hours", "weekend work", "public holiday"],
        "leave": ["annual leave", "vacation", "sick leave", "maternity", "paternity"],
        "dismissal": ["fired", "dismissed", "termination", "unfair dismissal"],
        "contract": ["contract", "agreement", "employment terms", "probation"],
        "discrimination": ["discrimination", "harassment", "unfair treatment"],
        "safety": ["safety", "health", "workplace injury", "accident"],
        "union": ["union", "workers committee", "collective bargaining"],
        "gratuity": ["gratuity", "severance", "retrenchment package"],
        "notice": ["notice period", "resignation", "notice pay"],
    }
    
    for query, count in unmatched:
        query_lower = query.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                if topic not in suggestions:
                    suggestions.append(topic)
                    logger.info(
                        f"Suggested topic '{topic}' based on query: '{query}' (count: {count})"
                    )
                break
    
    return suggestions


def main():
    """Main analysis function."""
    
    print("\n" + "=" * 60)
    print("RightLine Query Analysis Report")
    print("=" * 60 + "\n")
    
    # Analyze unmatched queries
    unmatched = analyze_unmatched_queries()
    
    if unmatched:
        print("📊 Top Unmatched Queries:")
        print("-" * 40)
        for i, (query, count) in enumerate(unmatched[:20], 1):
            print(f"{i:2}. [{count:3}x] {query}")
        print()
    
    # Analyze patterns
    patterns = analyze_query_patterns()
    
    if patterns:
        print("🔍 Query Patterns:")
        print("-" * 40)
        print(f"Total queries: {patterns.get('total_queries', 0)}")
        print(f"Unique queries: {patterns.get('unique_queries', 0)}")
        print("\nTop Keywords:")
        for word, count in patterns.get("top_keywords", [])[:10]:
            print(f"  - {word}: {count}x")
        print()
    
    # Suggest new topics
    if unmatched:
        suggestions = suggest_new_topics(unmatched)
        
        if suggestions:
            print("💡 Suggested New Topics to Add:")
            print("-" * 40)
            for topic in suggestions:
                print(f"  ✓ {topic}")
            print()
    
    print("\n📝 Recommendations:")
    print("-" * 40)
    print("1. Add responses for the top unmatched queries")
    print("2. Focus on topics with high keyword frequency")
    print("3. Consider adding variations of existing responses")
    print("4. Improve response matching for common misspellings")
    print()


if __name__ == "__main__":
    main()
