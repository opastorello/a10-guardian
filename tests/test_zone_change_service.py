"""
Unit tests for ZoneChangeService
Tests zone change detection, monitoring, and notifications
"""

from unittest.mock import Mock, patch

import pytest

from a10_guardian.services.zone_change_service import ZoneChangeService


@pytest.fixture
def mock_client():
    """Mock A10Client"""
    client = Mock()
    client.get = Mock()  # Synchronous mock, not async
    return client


@pytest.fixture
def mock_notifier():
    """Mock NotificationService"""
    notifier = Mock()
    notifier.send_notification = Mock()  # Synchronous mock, not async
    return notifier


@pytest.fixture
def zone_service(mock_client, mock_notifier):
    """ZoneChangeService instance with mocked dependencies"""
    return ZoneChangeService(mock_client, mock_notifier)


@pytest.fixture
def sample_zone():
    """Sample zone data for testing"""
    return {
        "id": "zone-123",
        "zone_name": "192.0.2.100",
        "operational_mode": "protect",
        "profile_name": "default",
        "zone_oper_policy": "policy-1",
        "created_time": "2024-01-01T00:00:00Z",
        "modified_time": "2024-01-01T00:00:00Z",
    }


class TestZoneChangeService:
    """Test suite for ZoneChangeService"""

    def test_initialization(self, zone_service):
        """Test service initialization"""
        assert zone_service.known_zones == {}
        assert zone_service.client is not None
        assert zone_service.notifier is not None

    def test_normalize_zone_removes_timestamps(self, zone_service, sample_zone):
        """Test that normalize_zone removes volatile fields"""
        normalized = zone_service.normalize_zone_for_comparison(sample_zone)

        assert "created_time" not in normalized
        assert "modified_time" not in normalized
        assert normalized["zone_name"] == "192.0.2.100"
        assert normalized["operational_mode"] == "protect"

    def test_detect_new_zones(self, zone_service, sample_zone):
        """Test detection of newly created zones"""
        current_zones = {"zone-123": sample_zone}

        new_ids, deleted_ids, modified_ids = zone_service.detect_zone_changes(current_zones)

        assert "zone-123" in new_ids
        assert len(deleted_ids) == 0
        assert len(modified_ids) == 0

    def test_detect_deleted_zones(self, zone_service, sample_zone):
        """Test detection of deleted zones"""
        # First, populate with a known zone
        zone_service.known_zones = {"zone-123": {"snapshot": sample_zone, "first_seen": 1234567890}}

        # Now check with empty current zones
        current_zones = {}
        new_ids, deleted_ids, modified_ids = zone_service.detect_zone_changes(current_zones)

        assert len(new_ids) == 0
        assert "zone-123" in deleted_ids
        assert len(modified_ids) == 0

    def test_detect_modified_zones(self, zone_service, sample_zone):
        """Test detection of modified zones"""
        # Setup known zone
        zone_service.known_zones = {"zone-123": {"snapshot": sample_zone.copy(), "first_seen": 1234567890}}

        # Modify the zone
        modified_zone = sample_zone.copy()
        modified_zone["operational_mode"] = "monitor"  # Changed from "protect"

        current_zones = {"zone-123": modified_zone}
        new_ids, deleted_ids, modified_ids = zone_service.detect_zone_changes(current_zones)

        assert len(new_ids) == 0
        assert len(deleted_ids) == 0
        assert "zone-123" in modified_ids

    def test_generate_change_summary(self, zone_service):
        """Test change summary generation"""
        old_zone = {"operational_mode": "monitor", "profile_name": "default", "zone_services": [1, 2, 3, 4]}

        new_zone = {"operational_mode": "protect", "profile_name": "gaming", "zone_services": [1, 2, 3, 4, 5, 6]}

        summary = zone_service.generate_change_summary(old_zone, new_zone)

        assert "monitor → protect" in summary.lower()
        assert "4 → 6" in summary

    @patch("a10_guardian.services.zone_change_service.settings")
    def test_notify_zone_created_when_enabled(self, mock_settings, zone_service, sample_zone):
        """Test zone creation notification when enabled"""
        mock_settings.NOTIFY_ZONE_CREATED = True
        # Mock get_zone_change_user to return a username
        zone_service.get_zone_change_user = Mock(return_value="admin")

        zone_service.notify_zone_created(sample_zone)

        zone_service.notifier.send_notification.assert_called_once()
        call_args = zone_service.notifier.send_notification.call_args
        assert "Zone Created" in call_args[1]["title"]

    @patch("a10_guardian.services.zone_change_service.settings")
    def test_notify_zone_created_when_disabled(self, mock_settings, zone_service, sample_zone):
        """Test zone creation notification when disabled"""
        mock_settings.NOTIFY_ZONE_CREATED = False

        zone_service.notify_zone_created(sample_zone)

        zone_service.notifier.send_notification.assert_not_called()

    @patch("a10_guardian.services.zone_change_service.settings")
    def test_notify_zone_modified_when_enabled(self, mock_settings, zone_service, sample_zone):
        """Test zone modification notification when enabled"""
        mock_settings.NOTIFY_ZONE_MODIFIED = True
        # Mock get_zone_change_user to return a username
        zone_service.get_zone_change_user = Mock(return_value="admin")

        old_zone = sample_zone.copy()
        new_zone = sample_zone.copy()
        new_zone["operational_mode"] = "monitor"

        zone_service.notify_zone_modified("zone-123", old_zone, new_zone)

        zone_service.notifier.send_notification.assert_called_once()
        call_args = zone_service.notifier.send_notification.call_args
        assert "Zone Modified" in call_args[1]["title"]

    @patch("a10_guardian.services.zone_change_service.settings")
    def test_notify_zone_deleted_when_enabled(self, mock_settings, zone_service, sample_zone):
        """Test zone deletion notification when enabled"""
        mock_settings.NOTIFY_ZONE_DELETED = True
        # Mock get_zone_change_user to return a username
        zone_service.get_zone_change_user = Mock(return_value="admin")

        zone_service.notify_zone_deleted("zone-123", sample_zone)

        zone_service.notifier.send_notification.assert_called_once()
        call_args = zone_service.notifier.send_notification.call_args
        assert "Zone Deleted" in call_args[1]["title"]

    def test_fetch_all_zones_single_page(self, zone_service, sample_zone):
        """Test fetching zones when all fit in single page"""
        # Mock two calls: 1) list zones, 2) get zone detail
        zone_service.client.get.side_effect = [
            {"total": 1, "object_list": [sample_zone]},  # List call
            sample_zone,  # Detail call for zone-123
        ]

        zones = zone_service.fetch_all_zones()

        assert len(zones) == 1
        assert "zone-123" in zones
        assert zones["zone-123"]["zone_name"] == "192.0.2.100"

    def test_fetch_all_zones_pagination(self, zone_service, sample_zone):
        """Test fetching zones with pagination"""
        # Create two different zones for testing
        zone1 = sample_zone.copy()
        zone1["id"] = "zone-1"
        zone2 = sample_zone.copy()
        zone2["id"] = "zone-2"

        # Mock calls: list page 1, detail zone-1, detail zone-2, list page 2 (empty)
        zone_service.client.get.side_effect = [
            {"total": 2, "object_list": [zone1, zone2]},  # List page 1
            zone1,  # Detail for zone-1
            zone2,  # Detail for zone-2
        ]

        zones = zone_service.fetch_all_zones()

        # Should have fetched 2 zones
        assert len(zones) == 2
        assert "zone-1" in zones
        assert "zone-2" in zones
