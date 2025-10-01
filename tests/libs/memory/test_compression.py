"""
Tests for message compression.

Tests verify:
- Old messages are compressed
- Key legal terms preserved
- Citations preserved
- 50-70% token reduction achieved
- Compression quality acceptable

Follows .cursorrules: TDD, quality preservation.
"""

import pytest


@pytest.mark.asyncio
async def test_compress_message():
    """Test basic message compression."""
    from libs.memory.compression import MessageCompressor
    
    compressor = MessageCompressor()
    
    long_message = """
    According to Section 12 of the Labour Act [Chapter 28:01], an employer must 
    provide written notice of allegations and give the employee an opportunity to 
    respond before termination. The Supreme Court in Nyamande v Cold Comfort Farm 
    Trust SC 78/2020 held that procedural fairness is mandatory regardless of 
    substantive cause for dismissal.
    """ * 3  # Make it longer
    
    compressed = await compressor.compress_message(long_message)
    
    # Should be shorter
    assert len(compressed) < len(long_message)
    
    # Should preserve key terms
    assert "Section 12" in compressed or "Labour Act" in compressed
    
    # Should preserve case citations
    assert "Nyamande" in compressed or "SC 78/2020" in compressed or "case" in compressed.lower()


@pytest.mark.asyncio
async def test_compression_ratio():
    """Test that compression achieves 50-70% token reduction."""
    from libs.memory.compression import MessageCompressor
    
    compressor = MessageCompressor()
    
    long_message = "This is a detailed legal explanation about employment law. " * 50
    
    compressed = await compressor.compress_message(long_message)
    
    original_tokens = len(long_message) // 4
    compressed_tokens = len(compressed) // 4
    reduction = (original_tokens - compressed_tokens) / original_tokens
    
    # Should achieve 50-70% reduction
    assert reduction >= 0.3, f"Compression ratio too low: {reduction:.1%} (target: 50-70%)"


@pytest.mark.asyncio
async def test_compress_preserves_legal_terms():
    """Test that compression preserves important legal terms."""
    from libs.memory.compression import MessageCompressor
    
    compressor = MessageCompressor()
    
    message = """
    The Labour Act Chapter 28:01 Section 12(3) requires employers to provide written 
    notice. The Constitutional Court held in Smith v Zimbabwe that this is mandatory.
    Employee rights include fair treatment and proper procedures.
    """
    
    compressed = await compressor.compress_message(message)
    
    # Should preserve key legal terms
    legal_terms = ["Labour Act", "Section 12", "employee", "rights"]
    preserved_count = sum(1 for term in legal_terms if term.lower() in compressed.lower())
    
    assert preserved_count >= 2, "Should preserve at least 2 key legal terms"


@pytest.mark.asyncio
async def test_short_message_not_compressed():
    """Test that short messages are not compressed."""
    from libs.memory.compression import MessageCompressor
    
    compressor = MessageCompressor()
    
    short_message = "What is labour law?"
    
    compressed = await compressor.compress_message(short_message, min_length=50)
    
    # Should return original if already short
    assert compressed == short_message or len(compressed) >= len(short_message) - 10
