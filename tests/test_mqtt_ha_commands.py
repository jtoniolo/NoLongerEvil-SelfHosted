"""Tests for Home Assistant commands received over MQTT."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from nolongerevil.integrations.mqtt.mqtt_integration import MqttIntegration
from nolongerevil.lib.types import DeviceObject, IntegrationConfig
from nolongerevil.services.device_state_service import DeviceStateService
from nolongerevil.services.subscription_manager import SubscriptionManager

SERIAL = "TEST12345678"


@pytest.fixture
async def integration(
    state_service: DeviceStateService, subscription_manager: SubscriptionManager
) -> MqttIntegration:
    """Create an MQTT integration with one initialized device."""
    for key, value in (
        (f"device.{SERIAL}", {}),
        (f"shared.{SERIAL}", {"can_heat": True, "can_cool": True}),
    ):
        await state_service.upsert_object(
            DeviceObject(
                serial=SERIAL,
                object_key=key,
                object_revision=1,
                object_timestamp=1234567890,
                value=value,
                updated_at=datetime.now(),
            )
        )
    config = IntegrationConfig(
        user_id="user",
        type="mqtt",
        enabled=True,
        config={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return MqttIntegration(config, state_service, subscription_manager)


class TestHaModeCommand:
    """Tests for the HA mode command."""

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ("heat_cool", "range"),
            ("heat", "heat"),
            ("cool", "cool"),
            ("off", "off"),
            ("auto", "auto"),
        ],
    )
    async def test_mode_payload_is_translated(
        self, integration: MqttIntegration, payload: str, expected: str
    ):
        """Test HA modes are translated and other values pass through."""
        target = "nolongerevil.integrations.mqtt.mqtt_integration.execute_command"
        with patch(target, new=AsyncMock()) as execute:
            await integration._handle_ha_command(f"nest/{SERIAL}/ha/mode/set", payload)

        execute.assert_awaited_once()
        assert execute.await_args.args[3:] == ("set_mode", expected)

    async def test_heat_cool_sets_range_mode(
        self, integration: MqttIntegration, state_service: DeviceStateService
    ):
        """Test heat_cool from HA sets the device to range mode."""
        await integration._handle_ha_command(f"nest/{SERIAL}/ha/mode/set", "heat_cool")

        shared = state_service.get_object(SERIAL, f"shared.{SERIAL}")
        assert shared is not None
        assert shared.value["target_temperature_type"] == "range"
