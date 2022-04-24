import datetime

import pytest
from act.action_manage_power_state_for_space_heating import ManageSpaceHeatingPower
from act.temperature_thresholds import TemperatureThresholds


@pytest.mark.parametrize(
    ["flow_temp", "return_temp", "outdoor_temp", "low", "high"],
    [
        pytest.param(10, 10, 10, 30, 43, id="Cold flow and warm outside"),
        pytest.param(33, 28, 10, 28, 45, id="Warm flow and warm outside"),
        pytest.param(40, 33, 10, 33, 45, id="Hot flow and warm outside"),
        pytest.param(10, 10, 3, 20, 30, id="Cold flow and cold outside"),
        pytest.param(33, 22, 3, 28, 35, id="Warm flow and cold outside"),
        pytest.param(41, 27, 3, 28, 45, id="Hot flow and cold outside"),
    ],
)
def test_startup_flow_temperature_is_sensible(flow_temp, return_temp, outdoor_temp, low, high):

    # Assemble
    if high is None:
        high = low

    assert high >= low, "The high boundary should be at least as big as the low boundary. You have mis-configured this test."

    device_infos = [{"FlowTemperature": flow_temp, "ReturnTemperature": return_temp, "OutdoorTemperature": outdoor_temp}]

    # Act
    calculation_moment = datetime.datetime.utcnow()
    suggested_startup_temperature = ManageSpaceHeatingPower.sensible_startup_flow_temperature(calculation_moment, device_infos)

    # Assert
    assert suggested_startup_temperature <= TemperatureThresholds.max_flow_temp(calculation_moment, device_infos), "The startup temp is higher than the maximum allowable flow temp"

    assert suggested_startup_temperature >= TemperatureThresholds.min_flow_temp(calculation_moment, device_infos), "The startup temp is lower than the minimum allowable flow temp"

    assert suggested_startup_temperature <= high, "The startup temp is higher than the upper boundary for this scenario"

    assert suggested_startup_temperature >= low, "The startup temp is lower than the lower boundary for this scenario"
