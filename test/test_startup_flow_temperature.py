import datetime
from typing import Optional

from act.action_manage_power_state_for_space_heating import ManageSpaceHeatingPower
from act.device_infos import DeviceInfos
from act.temperature_thresholds import TemperatureThresholds


def assert_in_range(
    device_infos: DeviceInfos,
    candidate: float,
    low: float,
    high: Optional[float] = None,
) -> None:

    assert candidate <= TemperatureThresholds.max_flow_temp(datetime.datetime.utcnow(), device_infos)
    assert candidate >= TemperatureThresholds.min_flow_temp(datetime.datetime.utcnow(), device_infos)
    assert candidate >= low

    if high is None:
        high = low

    assert candidate <= high


def test_sensible_when_cold_flow_and_warm_outside():
    device_infos = [{"FlowTemperature": 10, "ReturnTemperature": 10, "OutdoorTemperature": 10}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        30,
        43,
    )


def test_sensible_when_warm_flow_and_warm_outside():
    device_infos = [{"FlowTemperature": 33, "ReturnTemperature": 28, "OutdoorTemperature": 10}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        28,
        45,
    )


def test_sensible_when_hot_flow_and_warm_outside():
    device_infos = [{"FlowTemperature": 40, "ReturnTemperature": 33, "OutdoorTemperature": 10}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        33,
        45,
    )


def test_sensible_when_cold_flow_and_cold_outside():
    device_infos = [{"FlowTemperature": 10, "ReturnTemperature": 10, "OutdoorTemperature": 3}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        20,
        30,
    )


def test_sensible_when_warm_flow_and_cold_outside():
    device_infos = [{"FlowTemperature": 33, "ReturnTemperature": 22, "OutdoorTemperature": 3}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        28,
        35,
    )


def test_sensible_when_hot_flow_and_cold_outside():
    device_infos = [{"FlowTemperature": 41, "ReturnTemperature": 27, "OutdoorTemperature": 3}]
    assert_in_range(
        device_infos,
        ManageSpaceHeatingPower.sensible_startup_flow_temperature(datetime.datetime.utcnow(), device_infos),
        28,
        45,
    )
