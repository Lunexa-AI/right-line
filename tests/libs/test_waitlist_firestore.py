"""Unit tests for waitlist Firestore operations."""

import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, UTC
import uuid

from libs.firestore.waitlist import (
    add_to_waitlist,
    check_email_exists,
    get_waitlist_stats,
    get_waitlist_entry_by_id,
    _get_waitlist_entry_by_email,
)
from libs.models.firestore import WaitlistEntry


class TestWaitlistFirestore(unittest.IsolatedAsyncioTestCase):
    """Test cases for waitlist Firestore operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_email = "test@example.com"
        self.test_source = "web"
        self.test_metadata = {"ip_address": "192.168.1.1", "user_agent": "test-agent"}
        self.test_waitlist_id = str(uuid.uuid4())
        self.test_timestamp = datetime.now(UTC)

    def _create_mock_client(self, existing_entry=None, should_fail=False, fail_on_set=False):
        """Helper to create properly mocked Firestore client."""
        mock_client = Mock()
        mock_collection = Mock()
        mock_query = Mock()
        mock_doc_ref = Mock()

        if should_fail:
            # Make the collection call itself fail
            mock_client.collection.side_effect = Exception("Connection failed")
            return mock_client, mock_collection, mock_query, mock_doc_ref

        # Setup query for existing entry check
        if existing_entry:
            mock_doc = Mock()
            mock_doc.to_dict.return_value = existing_entry
            mock_query.get = AsyncMock(return_value=[mock_doc])
        else:
            mock_query.get = AsyncMock(return_value=[])

        # Setup document operations
        mock_doc_ref.get = AsyncMock()
        if fail_on_set:
            mock_doc_ref.set = AsyncMock(side_effect=Exception("Database write failed"))
        else:
            mock_doc_ref.set = AsyncMock()
        
        # Setup collection chaining
        mock_collection.where.return_value = mock_query
        mock_collection.document.return_value = mock_doc_ref
        mock_client.collection.return_value = mock_collection

        return mock_client, mock_collection, mock_query, mock_doc_ref

    async def test_add_to_waitlist_new_email_success(self):
        """Test successfully adding a new email to waitlist."""
        # Arrange
        mock_client, mock_collection, mock_query, mock_doc_ref = self._create_mock_client()
        
        # Act
        with patch('libs.firestore.waitlist.uuid.uuid4', return_value=self.test_waitlist_id):
            created, entry = await add_to_waitlist(
                mock_client, self.test_email, self.test_source, self.test_metadata
            )
        
        # Assert
        self.assertTrue(created)
        self.assertEqual(entry.email, self.test_email)
        self.assertEqual(entry.source, self.test_source)
        self.assertEqual(entry.metadata, self.test_metadata)
        self.assertEqual(entry.waitlist_id, self.test_waitlist_id)
        
        # Verify Firestore operations
        mock_collection.where.assert_called()
        mock_query.get.assert_called_once()
        mock_doc_ref.set.assert_called_once()

    async def test_add_to_waitlist_duplicate_email(self):
        """Test adding duplicate email returns existing entry."""
        # Arrange
        existing_entry_data = {
            "waitlist_id": "existing-id",
            "email": self.test_email,
            "joined_at": self.test_timestamp,
            "source": "referral",
            "metadata": {"ip_address": "different-ip"},
        }
        
        mock_client, mock_collection, mock_query, mock_doc_ref = self._create_mock_client(
            existing_entry=existing_entry_data
        )
        
        # Act
        created, entry = await add_to_waitlist(
            mock_client, self.test_email, self.test_source, self.test_metadata
        )
        
        # Assert
        self.assertFalse(created)
        self.assertEqual(entry.email, self.test_email)
        self.assertEqual(entry.waitlist_id, "existing-id")
        self.assertEqual(entry.source, "referral")  # Should return existing data
        
        # Verify no document creation was attempted
        mock_doc_ref.set.assert_not_called()

    async def test_add_to_waitlist_firestore_error(self):
        """Test handling Firestore connection errors."""
        # Arrange
        mock_client, _, _, _ = self._create_mock_client(should_fail=True)
        
        # Act & Assert
        with self.assertRaises(RuntimeError) as context:
            await add_to_waitlist(mock_client, self.test_email, self.test_source)
        
        self.assertIn("Failed to add email to waitlist", str(context.exception))

    async def test_check_email_exists_found(self):
        """Test checking existing email returns True."""
        # Arrange
        existing_entry = {
            "waitlist_id": self.test_waitlist_id,
            "email": self.test_email,
            "joined_at": self.test_timestamp,
            "source": self.test_source,
            "metadata": self.test_metadata,
        }
        mock_client, _, _, _ = self._create_mock_client(existing_entry=existing_entry)
        
        # Act
        exists = await check_email_exists(mock_client, self.test_email)
        
        # Assert
        self.assertTrue(exists)

    async def test_check_email_exists_not_found(self):
        """Test checking non-existing email returns False."""
        # Arrange
        mock_client, _, _, _ = self._create_mock_client()
        
        # Act
        exists = await check_email_exists(mock_client, self.test_email)
        
        # Assert
        self.assertFalse(exists)

    async def test_check_email_exists_firestore_error(self):
        """Test check_email_exists handles errors gracefully."""
        # Arrange
        mock_client, _, _, _ = self._create_mock_client(should_fail=True)
        
        # Act
        exists = await check_email_exists(mock_client, self.test_email)
        
        # Assert - Should return False on error to avoid blocking signups
        self.assertFalse(exists)

    async def test_get_waitlist_stats_success(self):
        """Test retrieving waitlist statistics successfully."""
        # Arrange
        mock_client = Mock()
        mock_collection = Mock()
        
        # Mock count result
        mock_count_result = [(Mock(value=150),)]
        mock_collection.count.return_value.get = AsyncMock(return_value=mock_count_result)
        
        # Mock recent entries
        mock_doc1 = Mock()
        mock_doc1.to_dict.return_value = {
            "email": "user1@example.com",
            "source": "web",
            "joined_at": self.test_timestamp,
        }
        
        mock_doc2 = Mock()
        mock_doc2.to_dict.return_value = {
            "email": "user2@example.com", 
            "source": "referral",
            "joined_at": self.test_timestamp,
        }
        
        mock_collection.order_by.return_value.limit.return_value.get = AsyncMock(
            return_value=[mock_doc1, mock_doc2]
        )
        
        mock_client.collection.return_value = mock_collection
        
        # Act
        stats = await get_waitlist_stats(mock_client, limit=2)
        
        # Assert
        self.assertEqual(stats["total_count"], 150)
        self.assertEqual(len(stats["recent_entries"]), 2)
        self.assertEqual(stats["sources_breakdown"]["web"], 1)
        self.assertEqual(stats["sources_breakdown"]["referral"], 1)
        self.assertEqual(stats["latest_signup"], self.test_timestamp)

    async def test_get_waitlist_stats_empty_waitlist(self):
        """Test retrieving stats from empty waitlist."""
        # Arrange
        mock_client = Mock()
        mock_collection = Mock()
        
        mock_count_result = [(Mock(value=0),)]
        mock_collection.count.return_value.get = AsyncMock(return_value=mock_count_result)
        mock_collection.order_by.return_value.limit.return_value.get = AsyncMock(return_value=[])
        
        mock_client.collection.return_value = mock_collection
        
        # Act
        stats = await get_waitlist_stats(mock_client)
        
        # Assert
        self.assertEqual(stats["total_count"], 0)
        self.assertEqual(len(stats["recent_entries"]), 0)
        self.assertEqual(stats["sources_breakdown"], {})
        self.assertIsNone(stats["latest_signup"])

    async def test_get_waitlist_stats_firestore_error(self):
        """Test get_waitlist_stats handles errors gracefully."""
        # Arrange
        mock_client = Mock()
        mock_client.collection.side_effect = Exception("Database error")
        
        # Act
        stats = await get_waitlist_stats(mock_client)
        
        # Assert - Should return empty stats with error info
        self.assertEqual(stats["total_count"], 0)
        self.assertEqual(len(stats["recent_entries"]), 0)
        self.assertIn("error", stats)

    async def test_get_waitlist_entry_by_id_found(self):
        """Test retrieving waitlist entry by ID successfully."""
        # Arrange
        entry_data = {
            "waitlist_id": self.test_waitlist_id,
            "email": self.test_email,
            "joined_at": self.test_timestamp,
            "source": self.test_source,
            "metadata": self.test_metadata,
        }
        
        mock_client = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        
        mock_snapshot = Mock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = entry_data
        
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_collection.document.return_value = mock_doc_ref
        mock_client.collection.return_value = mock_collection
        
        # Act
        entry = await get_waitlist_entry_by_id(mock_client, self.test_waitlist_id)
        
        # Assert
        self.assertIsNotNone(entry)
        self.assertEqual(entry.waitlist_id, self.test_waitlist_id)
        self.assertEqual(entry.email, self.test_email)

    async def test_get_waitlist_entry_by_id_not_found(self):
        """Test retrieving non-existing waitlist entry returns None."""
        # Arrange
        mock_client = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        
        mock_snapshot = Mock()
        mock_snapshot.exists = False
        
        mock_doc_ref.get = AsyncMock(return_value=mock_snapshot)
        mock_collection.document.return_value = mock_doc_ref
        mock_client.collection.return_value = mock_collection
        
        # Act
        entry = await get_waitlist_entry_by_id(mock_client, "nonexistent-id")
        
        # Assert
        self.assertIsNone(entry)

    async def test_get_waitlist_entry_by_id_firestore_error(self):
        """Test get_waitlist_entry_by_id handles errors gracefully."""
        # Arrange
        mock_client = Mock()
        mock_client.collection.side_effect = Exception("Connection failed")
        
        # Act
        entry = await get_waitlist_entry_by_id(mock_client, self.test_waitlist_id)
        
        # Assert
        self.assertIsNone(entry)

    async def test_get_waitlist_entry_by_email_found(self):
        """Test private helper function _get_waitlist_entry_by_email."""
        # Arrange
        entry_data = {
            "waitlist_id": self.test_waitlist_id,
            "email": self.test_email,
            "joined_at": self.test_timestamp,
            "source": self.test_source,
            "metadata": self.test_metadata,
        }
        
        mock_client, _, _, _ = self._create_mock_client(existing_entry=entry_data)
        
        # Act
        entry = await _get_waitlist_entry_by_email(mock_client, self.test_email)
        
        # Assert
        self.assertIsNotNone(entry)
        self.assertEqual(entry.email, self.test_email)
        self.assertEqual(entry.waitlist_id, self.test_waitlist_id)

    async def test_get_waitlist_entry_by_email_not_found(self):
        """Test _get_waitlist_entry_by_email returns None for non-existing email."""
        # Arrange
        mock_client, _, _, _ = self._create_mock_client()
        
        # Act
        entry = await _get_waitlist_entry_by_email(mock_client, self.test_email)
        
        # Assert
        self.assertIsNone(entry)

    async def test_get_waitlist_entry_by_email_error(self):
        """Test _get_waitlist_entry_by_email handles errors gracefully."""
        # Arrange
        mock_client, _, _, _ = self._create_mock_client(should_fail=True)
        
        # Act
        entry = await _get_waitlist_entry_by_email(mock_client, self.test_email)
        
        # Assert
        self.assertIsNone(entry)

    async def test_concurrent_access_scenario(self):
        """Test handling concurrent access to the same email."""
        # This test simulates a race condition where two requests
        # try to add the same email simultaneously
        
        # Arrange
        existing_entry_data = {
            "waitlist_id": "concurrent-id",
            "email": self.test_email,
            "joined_at": self.test_timestamp,
            "source": self.test_source,
            "metadata": self.test_metadata,
        }
        
        # First call: no existing entry
        mock_client1, mock_collection1, mock_query1, mock_doc_ref1 = self._create_mock_client()
        
        # Second call: entry exists
        mock_client2, mock_collection2, mock_query2, mock_doc_ref2 = self._create_mock_client(
            existing_entry=existing_entry_data
        )
        
        # Act - First request proceeds to create
        with patch('libs.firestore.waitlist.uuid.uuid4', return_value=self.test_waitlist_id):
            created1, entry1 = await add_to_waitlist(
                mock_client1, self.test_email, self.test_source, self.test_metadata
            )
        
        # Second request finds existing entry
        created2, entry2 = await add_to_waitlist(
            mock_client2, self.test_email, self.test_source, self.test_metadata
        )
        
        # Assert
        self.assertTrue(created1)  # First request created entry
        self.assertEqual(entry1.waitlist_id, self.test_waitlist_id)
        
        self.assertFalse(created2)  # Second request found existing
        self.assertEqual(entry2.waitlist_id, "concurrent-id")


if __name__ == '__main__':
    unittest.main()