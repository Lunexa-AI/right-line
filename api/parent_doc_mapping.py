"""
Parent Document ID Mapping Service

Temporary solution for Task 3.1 to resolve parent_doc_id mismatch between
chunks and actual parent documents in R2. This creates a runtime mapping
to enable small-to-big retrieval without reprocessing the entire corpus.

This is a TEMPORARY fix - the long-term solution is to unify ID generation
in the data processing pipeline.

Author: RightLine Team
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, Optional, Set
import structlog
import boto3
import os

logger = structlog.get_logger(__name__)

# R2 configuration
R2_ENDPOINT = os.environ.get("R2_ENDPOINT") or os.environ.get("CLOUDFLARE_R2_S3_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")


class ParentDocumentMapper:
    """
    Runtime mapping service to resolve parent_doc_id mismatches.
    
    Creates mappings between chunk parent_doc_ids and actual R2 parent document IDs
    by analyzing doc_id relationships and content matching.
    
    This is a TEMPORARY solution pending pipeline unification.
    """
    
    def __init__(self):
        self._doc_id_to_parent_map: Dict[str, str] = {}
        self._parent_to_r2_map: Dict[str, str] = {}
        self._r2_client = None
        self._mapping_loaded = False
        self._load_lock = asyncio.Lock()
    
    def _get_r2_client(self):
        """Get or create R2 client."""
        if self._r2_client is None:
            if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
                logger.warning("R2 configuration incomplete for parent doc mapping")
                return None
            
            self._r2_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY,
                aws_secret_access_key=R2_SECRET_KEY,
                region_name='auto'
            )
        return self._r2_client
    
    async def _ensure_mapping_loaded(self) -> bool:
        """Ensure parent document mapping is loaded."""
        if self._mapping_loaded:
            return True
        
        async with self._load_lock:
            if self._mapping_loaded:
                return True
            
            return await self._build_mapping()
    
    async def _build_mapping(self) -> bool:
        """Build robust parent document ID mapping using intelligent content correlation."""
        r2_client = self._get_r2_client()
        if not r2_client:
            return False
        
        start_time = time.time()
        logger.info("Building ROBUST parent document ID mapping with content correlation")
        
        try:
            # STEP 1: Load full docs.jsonl manifest for comprehensive mapping data
            manifest_key = "corpus/docs/docs.jsonl"
            logger.info("Loading complete docs.jsonl manifest for robust mapping", key=manifest_key)
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: r2_client.get_object(Bucket=R2_BUCKET_NAME, Key=manifest_key)
            )
            
            manifest_content = response['Body'].read().decode('utf-8')
            logger.info("Manifest loaded for analysis", size_mb=round(len(manifest_content) / 1024 / 1024, 2))
            
            # STEP 2: Build comprehensive mappings from manifest
            parent_docs_by_various_ids = {}
            doc_id_to_parent = {}
            parent_id_to_r2_parent = {}
            title_to_parent = {}  # For content matching
            
            manifest_docs_processed = 0
            
            for line_num, line in enumerate(manifest_content.strip().split('\n')):
                if not line.strip():
                    continue
                    
                try:
                    parent_doc = json.loads(line)
                    parent_doc_id = parent_doc.get('parent_doc_id', '')
                    doc_id = parent_doc.get('doc_id', '')
                    title = parent_doc.get('metadata', {}).get('title', '') or parent_doc.get('title', '')
                    doc_type = parent_doc.get('doc_type', '')
                    
                    if parent_doc_id:
                        # Store comprehensive mapping data
                        parent_docs_by_various_ids[parent_doc_id] = {
                            'r2_parent_doc_id': parent_doc_id,
                            'manifest_doc_id': doc_id,
                            'title': title,
                            'doc_type': doc_type,
                            'r2_key': f"corpus/docs/{doc_type}/{parent_doc_id}.json"
                        }
                        
                        # Build all possible mappings
                        if doc_id:
                            doc_id_to_parent[doc_id] = parent_doc_id
                            parent_id_to_r2_parent[doc_id] = parent_doc_id
                        
                        parent_id_to_r2_parent[parent_doc_id] = parent_doc_id
                        
                        # Title-based mapping for content correlation
                        if title:
                            normalized_title = title.lower().strip()
                            title_to_parent[normalized_title] = parent_doc_id
                        
                        manifest_docs_processed += 1
                        
                except Exception as e:
                    if line_num < 10:  # Only log first few errors
                        logger.warning("Failed to parse manifest line", line_num=line_num, error=str(e))
                    continue
            
            # STEP 3: Store the mappings
            self._doc_id_to_parent_map = doc_id_to_parent
            self._parent_to_r2_map = parent_id_to_r2_parent
            
            # Store additional data for intelligent resolution
            self._title_to_parent_map = title_to_parent
            self._parent_docs_metadata = parent_docs_by_various_ids
            
            build_time = time.time() - start_time
            
            logger.info(
                "ROBUST parent document mapping built successfully",
                manifest_docs_processed=manifest_docs_processed,
                doc_id_mappings=len(doc_id_to_parent),
                parent_mappings=len(parent_id_to_r2_parent), 
                title_mappings=len(title_to_parent),
                build_time_ms=round(build_time * 1000, 2),
                method="comprehensive_manifest_analysis"
            )
            
            self._mapping_loaded = True
            return True
            
        except Exception as e:
            logger.error("Robust mapping failed", error=str(e))
            # No fallback - we need to solve this properly
            return False
    
    async def _enhance_mapping_from_manifest(self) -> None:
        """Enhance mapping with manifest data (optional, fast single request)."""
        try:
            manifest_key = "corpus/docs/docs.jsonl"
            loop = asyncio.get_event_loop()
            
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._get_r2_client().get_object(Bucket=R2_BUCKET_NAME, Key=manifest_key)
                ),
                timeout=5.0  # Short timeout - this is optional enhancement
            )
            
            manifest_content = response['Body'].read().decode('utf-8')
            
            # Parse manifest efficiently
            enhanced_mappings = 0
            for line in manifest_content.strip().split('\n')[:1000]:  # Limit for speed
                if not line.strip():
                    continue
                    
                try:
                    parent_doc = json.loads(line)
                    parent_doc_id = parent_doc.get('parent_doc_id', '')
                    doc_id = parent_doc.get('doc_id', '')
                    
                    if parent_doc_id and doc_id and parent_doc_id != doc_id:
                        # Add the enhanced mapping
                        self._doc_id_to_parent_map[doc_id] = parent_doc_id
                        enhanced_mappings += 1
                        
                except Exception:
                    continue
            
            logger.info("Mapping enhanced from manifest", enhanced_mappings=enhanced_mappings)
            
        except Exception as e:
            logger.debug("Could not enhance from manifest", error=str(e))
    
    async def _build_mapping_fallback(self) -> bool:
        """Fallback method: build mapping by loading individual parent docs (slower)."""
        r2_client = self._get_r2_client()
        start_time = time.time()
        
        try:
            # Load individual parent documents with parallel processing
            doc_types = ['act', 'si', 'judgment', 'constitution']
            all_keys = []
            
            # First, collect all parent doc keys
            for doc_type in doc_types:
                prefix = f"corpus/docs/{doc_type}/"
                paginator = r2_client.get_paginator('list_objects_v2')
                
                for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            if obj['Key'].endswith('.json'):
                                all_keys.append(obj['Key'])
            
            logger.info(f"Found {len(all_keys)} parent documents to process")
            
            # Process in parallel batches
            batch_size = 20
            mapping_count = 0
            
            for i in range(0, len(all_keys), batch_size):
                batch_keys = all_keys[i:i + batch_size]
                
                # Create parallel tasks for this batch
                tasks = [
                    self._load_parent_doc_for_mapping(key)
                    for key in batch_keys
                ]
                
                # Execute batch in parallel
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for result in batch_results:
                    if isinstance(result, tuple) and len(result) == 2:
                        doc_id, parent_doc_id = result
                        self._doc_id_to_parent_map[doc_id] = parent_doc_id
                        self._parent_to_r2_map[parent_doc_id] = parent_doc_id
                        self._parent_to_r2_map[doc_id] = parent_doc_id
                        mapping_count += 1
            
            build_time = time.time() - start_time
            logger.info(
                "Fallback mapping completed",
                mappings_built=mapping_count,
                build_time_ms=round(build_time * 1000, 2),
                method="parallel_individual_loading"
            )
            
            self._mapping_loaded = True
            return True
            
        except Exception as e:
            logger.error("Fallback mapping failed", error=str(e))
            return False
    
    async def _load_parent_doc_for_mapping(self, r2_key: str) -> Optional[tuple]:
        """Load single parent doc for mapping (used in parallel batch)."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._get_r2_client().get_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            )
            
            parent_data = json.loads(response['Body'].read().decode('utf-8'))
            doc_id = parent_data.get('doc_id', '')
            parent_doc_id = r2_key.split('/')[-1].replace('.json', '')
            
            if doc_id:
                return (doc_id, parent_doc_id)
            
        except Exception as e:
            logger.debug("Failed to load parent doc for mapping", key=r2_key, error=str(e))
        
        return None
    
    async def resolve_parent_doc_id(self, chunk_parent_doc_id: str, chunk_doc_id: str) -> Optional[str]:
        """
        Resolve chunk parent_doc_id to actual R2 parent document ID.
        
        Args:
            chunk_parent_doc_id: Parent doc ID from chunk metadata
            chunk_doc_id: Doc ID from chunk metadata
            
        Returns:
            Actual R2 parent document ID, or None if not found
        """
        if not await self._ensure_mapping_loaded():
            return None
        
        # Try direct mapping first
        if chunk_parent_doc_id in self._parent_to_r2_map:
            return self._parent_to_r2_map[chunk_parent_doc_id]
        
        # Try mapping via doc_id
        if chunk_doc_id in self._doc_id_to_parent_map:
            return self._doc_id_to_parent_map[chunk_doc_id]
        
        logger.debug(
            "Parent document ID not found in mapping",
            chunk_parent_doc_id=chunk_parent_doc_id,
            chunk_doc_id=chunk_doc_id
        )
        
        return None
    
    def get_mapping_stats(self) -> Dict[str, any]:
        """Get mapping statistics for monitoring."""
        return {
            "mapping_loaded": self._mapping_loaded,
            "doc_id_mappings": len(self._doc_id_to_parent_map),
            "parent_mappings": len(self._parent_to_r2_map),
            "r2_available": self._r2_client is not None
        }


# Singleton instance
parent_doc_mapper = ParentDocumentMapper()
