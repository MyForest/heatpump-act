import datetime
import statistics
import structlog

from typing import Generator
from .action import Action
from .temperature_thresholds import TemperatureThresholds
from .action_manage_power_state_for_space_heating import ManageSpaceHeatingPower

from .device_infos import DeviceInfos

# --------------------------------------------------------------------------------
class EnsureZone1FlowTemperatureIsCorrect:
    """Notably, the external conditions might change and we might need to just nudge it"""

    @staticmethod
    def ensure_target_flow_temp_at_maximum(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:
        latest_device_info = device_infos[-1]

        if not latest_device_info["Power"]:
            return

        if latest_device_info["ForcedHotWaterMode"]:
            return

        reason = "to create an appropriate level of demand on the heat pump"

        recent_infos = device_infos[-5:]
        recent_average_temp = statistics.mean([float(device_info["OutdoorTemperature"]) for device_info in recent_infos])

        max_flow_temp = TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)

        structlog.get_logger().debug("Recent outdoor temp", recent_average_temp=recent_average_temp)
        if recent_average_temp > 9:
            # The pump switches itself off too soon to be gently managed
            # We're certainly going to be in an on-off cycle. The off cycles might be an hour or more
            new_target_temperature = max_flow_temp
        else:

            previous_event = device_infos[-2]
            if previous_event["DefrostMode"]:
                reason = "which is a lower target flow temp to keep us efficient as we just came off a defrost"
                new_target_temperature = ManageSpaceHeatingPower.sensible_startup_flow_temperature(calculation_moment, device_infos) + 3
            else:
                # Down to about 0 we can do on-off cycles with gentle increases, but below that we might be able to just do a long run
                if recent_average_temp < 0:
                    temp = TemperatureThresholds.min_flow_temp(calculation_moment, device_infos)
                    temp = temp + TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)
                    new_target_temperature = temp / 2
                else:
                    new_target_temperature = EnsureZone1FlowTemperatureIsCorrect.__gently_increase_target_temperature(calculation_moment, device_infos)
                    reason = "so it's gently increasing"

        current_target_temperature = float(latest_device_info["TargetHCTemperatureZone1"])

        new_target_temperature = min(new_target_temperature, max_flow_temp)

        if current_target_temperature != new_target_temperature:
            yield Action(
                "SetHeatFlowTemperatureZone1",
                new_target_temperature,
                f"Setting target flow temperature to {new_target_temperature} °C {reason}. The maximum is {max_flow_temp} °C.",
            )

    @staticmethod
    def __gently_increase_target_temperature_only_using_temperatures(calculation_moment: datetime.datetime, device_infos) -> float:
        # This method was created when we stopped getting the heat pump frequency data from MELCloud
        recent_device_infos = device_infos[-1:]
        current_target_temperature = float(device_infos[-1]["TargetHCTemperatureZone1"])

        flow_temperature = statistics.mean([device_info["FlowTemperature"] for device_info in recent_device_infos])

        max_flow_temp = TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)
        if (flow_temperature - 10) >= max_flow_temp:
            suggestion = max_flow_temp - 2
            structlog.get_logger().debug("Suggesting a new flow target temperature because the flow is really hot", suggestion=suggestion, flow_temperature=flow_temperature)
            return suggestion

        if flow_temperature >= current_target_temperature:
            suggestion = min(max_flow_temp, flow_temperature + 2)
            structlog.get_logger().debug(
                "Suggesting a new flow target temperature because the flow is already higher than the current target temperature",
                suggestion=suggestion,
                flow_temperature=flow_temperature,
                current_target_temperature=current_target_temperature,
            )
            return suggestion

        if flow_temperature < current_target_temperature - 10:
            suggestion = max(25, min(max_flow_temp, flow_temperature + 2))
            structlog.get_logger().debug(
                "Suggesting a new flow target temperature because the flow is much lower than the current target temperature",
                suggestion=suggestion,
                flow_temperature=flow_temperature,
                current_target_temperature=current_target_temperature,
            )
            return suggestion

        return min(max_flow_temp, current_target_temperature)

    @staticmethod
    def __gently_increase_target_temperature(calculation_moment: datetime.datetime, device_infos) -> float:

        latest_device_info = device_infos[-1]
        current_target_temperature = float(latest_device_info["TargetHCTemperatureZone1"])

        # Let's see if the heat pump thinks it's time to give up
        current_frequency = latest_device_info["HeatPumpFrequency"]
        previous_frequency = device_infos[-2]["HeatPumpFrequency"]

        if previous_frequency == 0 and current_frequency == 0:
            # The frequency is not informative
            return EnsureZone1FlowTemperatureIsCorrect.__gently_increase_target_temperature_only_using_temperatures(calculation_moment, device_infos)

        new_target_temperature = current_target_temperature

        if current_frequency < 40:
            if current_frequency < previous_frequency:
                structlog.get_logger().debug("The power level has dropped", previous_frequency=previous_frequency, current_frequency=current_frequency)

                if float(latest_device_info["FlowTemperature"]) >= current_target_temperature:
                    new_target_temperature = float(latest_device_info["FlowTemperature"]) + 2
                    structlog.get_logger().debug(
                        "Pushing the target temp to "
                        + str(new_target_temperature)
                        + " because the flow of "
                        + str(float(latest_device_info["FlowTemperature"]))
                        + " °C is already at least as warm as the current target temperature of "
                        + str(current_target_temperature)
                        + " °C"
                    )
                else:

                    # It's winding down because the flow is warm enough
                    # If we've bumped up the target recently then give it another iteration to catch up
                    if current_target_temperature > device_infos[-2]["TargetHCTemperatureZone1"] or current_target_temperature > device_infos[-3]["TargetHCTemperatureZone1"]:
                        structlog.get_logger().debug("Leaving target alone because it was only recently increased", currentTargetTemperature=current_target_temperature)
                    else:
                        new_target_temperature = current_target_temperature + 2
                        if current_frequency < 28:
                            # It's very close to being gone so give it a bigger nudge
                            new_target_temperature = current_target_temperature + 3
                            structlog.get_logger().debug(
                                "Pushing the target temperature because it looks like the pump is about to stop", newTargetTemperature=new_target_temperature
                            )
            else:
                batch = device_infos[-4:-2]

                avg = statistics.mean([deviceInfo["HeatPumpFrequency"] for deviceInfo in batch])

                # It's running low
                if avg == current_frequency:
                    # It's on a plateau near the bottom
                    # It might just give up soon but we want it to keep going.
                    new_target_temperature = max(
                        current_target_temperature,
                        float(latest_device_info["FlowTemperature"]) + 2,
                    )

        if new_target_temperature == current_target_temperature:
            return current_target_temperature

        # Ensure we're encouraging a warmer flow rather than a colder one by accident
        new_target_temperature = max(new_target_temperature, latest_device_info["FlowTemperature"])

        if new_target_temperature == current_target_temperature:
            return current_target_temperature

        maxTemp = TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)
        if new_target_temperature > maxTemp:
            new_target_temperature = maxTemp
            if current_target_temperature != new_target_temperature:
                # Only debug when it's interesting
                structlog.get_logger().debug("Although the heat pump is winding down, we're limiting the target temp to the max", newTargetTemperature=new_target_temperature)
        else:
            pass
            structlog.get_logger().debug(
                "The heat pump is starting to wind down so increase the desired target temperature to create some demand", newTargetTemperature=new_target_temperature
            )

        return new_target_temperature
