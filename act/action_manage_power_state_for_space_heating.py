import datetime
import os
import statistics
from typing import Generator, Optional

import structlog
from dotenv import load_dotenv

from .action import Action
from .occupant_comes_home import OccupantComesHome
from .action_turn_on_power import TurnOnPower
from .device_infos import DeviceInfos
from .dwell import Dwell
from .effective_temperature import EffectiveTemperature
from .emoncms import EmonCMS
from .last_time_stamp import LastTimeStamp
from .schedule import Schedule
from .target_water_temperature import TargetWaterTemperature
from .temperature_thresholds import TemperatureThresholds

load_dotenv()

# --------------------------------------------------------------------------------
class ManageSpaceHeatingPower:
    @staticmethod
    def manage(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        device_info = device_infos[-1]

        if device_info["ForcedHotWaterMode"]:
            return

        if device_info["Power"]:
            structlog.get_logger().debug("Determining if we should turn off")
            reason = ManageSpaceHeatingPower.reason_we_should_turn_off(calculation_moment, device_infos)
            if reason:
                structlog.get_logger().debug("Apparently we should turn off", reason=reason)
                avoid = ManageSpaceHeatingPower.avoid_cleverness(device_infos)

                if avoid is None:
                    reason_to_heat_tank = ManageSpaceHeatingPower.warm_up_tank(calculation_moment, device_infos)

                    if reason_to_heat_tank:
                        yield Action(
                            "ForcedHotWaterMode",
                            "true",
                            reason_to_heat_tank,
                        )
                        return
                else:
                    reason = avoid

                yield Action("Power", "false", f"Turning off because {reason}")

            else:
                structlog.get_logger().debug("There's no reason to turn off the power as far as the space heating algorithm is concerned")
        else:
            structlog.get_logger().debug("Determining if we should turn on")
            reason = ManageSpaceHeatingPower.reason_we_should_turn_on(calculation_moment, device_infos)
            if reason:

                new_target_temperature = ManageSpaceHeatingPower.sensible_startup_flow_temperature(calculation_moment, device_infos)

                yield Action(
                    "SetHeatFlowTemperatureZone1",
                    new_target_temperature,
                    f"Setting initial target flow temperature to {new_target_temperature} °C. The flow is currently {device_info['FlowTemperature']} °C",
                )

                yield Action(
                    "Power",
                    "true",
                    f"Turning on so we can do some heating. {reason}",
                )
            else:
                reason_to_heat_tank = ManageSpaceHeatingPower.warm_up_tank(calculation_moment, device_infos)

                if reason_to_heat_tank:
                    yield Action(
                        "ForcedHotWaterMode",
                        "true",
                        reason_to_heat_tank,
                    )
                    yield Action(
                        "Power",
                        "true",
                        "Turning on so we can heat the water",
                    )
                    return
                structlog.get_logger().debug("There's no reason to turn on the power as far as the space heating algorithm is concerned")

    @staticmethod
    def sensible_startup_flow_temperature(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> float:

        latest_device_info = device_infos[-1]

        if latest_device_info["OutdoorTemperature"] > 9:
            # There's no point being clever
            return TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)

        if latest_device_info["ReturnTemperature"] > 35:
            # It's likely to drop to the return temperature as soon as we start pumping
            new_target_temperature = latest_device_info["ReturnTemperature"]
            new_target_temperature = new_target_temperature + 2
        else:
            new_target_temperature = latest_device_info["FlowTemperature"] + 2
            if latest_device_info["OutdoorTemperature"] > 6:
                # It's likely to turn off soon after it comes on so give it a bigger nudge
                new_target_temperature = new_target_temperature + 2

        new_target_temperature = min(
            new_target_temperature,
            TemperatureThresholds.max_flow_temp(calculation_moment, device_infos),
        )

        new_target_temperature = max(
            new_target_temperature,
            TemperatureThresholds.min_flow_temp(calculation_moment, device_infos),
        )

        return new_target_temperature

    @staticmethod
    def avoid_cleverness(
        device_infos: DeviceInfos,
    ) -> Optional[str]:
        recent_defrosts = [device_info for device_info in device_infos[-20:] if device_info.get("DefrostMode") in device_info]

        if recent_defrosts:
            return f"There were { len(recent_defrosts) } defrosts as recently as {LastTimeStamp.last_time_stamp_in_utc(recent_defrosts[-1]).isoformat()}"

        return None

    @staticmethod
    def warm_up_tank(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:

        tank_temperature_below_which_we_should_heat_water = TargetWaterTemperature.tank_temperature_to_trigger_hot_water(calculation_moment, device_infos)
        desired_temp = TargetWaterTemperature.target_tank_temperature(calculation_moment, device_infos)

        latest_device_info = device_infos[-1]
        tank_temp = float(latest_device_info["TankWaterTemperature"])
        flow_temp = float(latest_device_info["FlowTemperature"])

        structlog.get_logger().debug(
            "Temperatures being considered",
            tank_temperature_below_which_we_should_heat_water=tank_temperature_below_which_we_should_heat_water,
            tank_temp=tank_temp,
            desired_temp=desired_temp,
        )

        if tank_temp < tank_temperature_below_which_we_should_heat_water:
            response = f"We're going to heat the tank to {desired_temp} °C because it's at {tank_temp} °C"
            response += f"which is lower than the trigger temperature of {tank_temperature_below_which_we_should_heat_water} °C "
            response += f"and the flow is at {flow_temp} °C"
            return response

        return None

    @staticmethod
    def reason_we_should_turn_off(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:

        try:
            structlog.get_logger().debug("Working out if turning off should be blocked because we should be turning on")
            reason_to_be_on = TurnOnPower.should_turn_on_power(calculation_moment, device_infos)
            if reason_to_be_on:
                # Don't get into a fight
                structlog.get_logger().debug("We should not turn off because we should be on", reason_to_be_on=reason_to_be_on)
                return None

            structlog.get_logger().debug("Power doesn't need to be on")

        except StopIteration:
            structlog.get_logger().debug("Power doesn't need to be on")

        duration_in_minutes = 5
        recent_device_infos = device_infos[-duration_in_minutes:]
        recent_power_states = [device_info["Power"] for device_info in recent_device_infos]
        recent_on_power_states = [x for x in recent_power_states if x]
        if len(recent_on_power_states) < duration_in_minutes:
            structlog.get_logger().debug("Power has not been on for long so leaving it alone to avoid stressing the heatpump out", duration_in_minutes=duration_in_minutes)
            return None

        device_info = device_infos[-1]

        flow_temperature = float(device_info["FlowTemperature"])
        return_temperature = float(device_info["ReturnTemperature"])
        temperature_delta = flow_temperature - return_temperature

        max_flow_temp = TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)
        average_recent_flow_temperature = statistics.mean([device_info["FlowTemperature"] for device_info in device_infos[-10:]])
        if average_recent_flow_temperature >= max_flow_temp:
            average_recent_target_temperature = statistics.mean([device_info["TargetHCTemperatureZone1"] for device_info in device_infos[-10:]])
            if average_recent_target_temperature >= max_flow_temp:
                return f"the average recent target temperature {average_recent_target_temperature} °C is higher than the maximum of {max_flow_temp} °C."

        reason = ManageSpaceHeatingPower.is_plenty_warm_enough(calculation_moment, device_infos)
        if reason:
            return f"It's plenty warm enough so the power shouldn't be on for heating. {reason}"

        if temperature_delta > 5:
            structlog.get_logger().debug("The return is still coming back a fair bit colder than the flow", temperature_delta=temperature_delta)
            return None

        dwell_time = Dwell.turn_off_dwell(calculation_moment, device_infos)
        structlog.get_logger().debug("turnOff dwell time", dwell_time=round(dwell_time))

        should_have_been_hot_since = calculation_moment - datetime.timedelta(seconds=dwell_time)

        interesting_infos = [device_info for device_info in device_infos if LastTimeStamp.last_time_stamp_in_utc(device_info) >= should_have_been_hot_since]

        acceptable_missing = 3
        suitable_number_of_events = (dwell_time / 60) - acceptable_missing
        if len(interesting_infos) < suitable_number_of_events:
            structlog.get_logger().warning("There are insufficient readings to look at so not turning off power", size=len(interesting_infos))

        target_temp = TemperatureThresholds.max_flow_temp(calculation_moment, device_infos)
        min_temp = TemperatureThresholds.min_flow_temp(calculation_moment, device_infos)
        # It might not get up to the threshold exactly
        target_temp = max(target_temp - 1, min_temp + 1)
        hot_infos = [device_info for device_info in interesting_infos if float(device_info["FlowTemperature"]) > target_temp]

        has_been_warm = len(hot_infos) == len(interesting_infos)

        if hot_infos:
            has_been_warm_duration = (calculation_moment - LastTimeStamp.last_time_stamp_in_utc(hot_infos[0])).total_seconds()

        flow_info = f" - the flow is currently {device_infos[-1]['FlowTemperature']} °C"

        if has_been_warm:
            return f"It has been warm enough to turn off the heating{flow_info}"

        if hot_infos:
            wait_info = f" but it needs to be above {target_temp} °C for another {int(dwell_time - has_been_warm_duration)} seconds"
        else:
            wait_info = f" but it needs to be above {target_temp} °C for {int(dwell_time)} seconds"

        structlog.get_logger().debug(f"It hasn't been warm enough to turn off the heating{ flow_info } { wait_info }")

        return None

    @staticmethod
    def is_plenty_warm_enough(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:

        if len(device_infos) < 2:
            return None

        first = device_infos[0]
        last = device_infos[-1]

        last_temperature = last["OutdoorTemperature"]
        try:
            last_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        if last_temperature > TemperatureThresholds.no_heating_required(calculation_moment, device_infos):
            return f"It's {last_temperature} °C so we don't need heating"

        first_temperature = first["OutdoorTemperature"]
        try:
            first_temperature = EffectiveTemperature.apparent_temp(LastTimeStamp.last_time_stamp_in_utc(first))
        except:
            pass

        # We really need a prediction of how hot it's going to be, but we can get an idea by seeing how it's warming now

        time_delta = (LastTimeStamp.last_time_stamp_in_utc(last) - LastTimeStamp.last_time_stamp_in_utc(first)).total_seconds()
        if time_delta <= 0:
            structlog.get_logger().debug("We can't tell how the temperature is changing")
            return None

        temperature_delta = last_temperature - first_temperature

        temperature_change_rate = 3600 * temperature_delta / time_delta

        if last_temperature > 5:
            if temperature_change_rate > 1:
                structlog.get_logger().debug(
                    "It's reasonably warm and it's getting warmer so we don't need heating",
                    last_temperature=last_temperature,
                    temperature_change_rate=round(temperature_change_rate, 2),
                )

        return None

    @staticmethod
    def is_plenty_sunny_enough(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> bool:

        solar_reading = EmonCMS.get_feed_value(int(os.environ["EMONCMS_SOLAR_FEED_ID"]), calculation_moment)
        solar_power_in_watts = solar_reading["value"]

        device_info = device_infos[0]
        last_temperature = device_info["OutdoorTemperature"]
        try:
            last_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        #   TODO: Would be better to use effective temp with insolation
        if last_temperature > 10 and solar_power_in_watts > 800:
            structlog.get_logger().debug("It's sunny enough to not need heating at this temperature", last_temperature=last_temperature, solar_power_in_watts=solar_power_in_watts)
            return True

        if last_temperature > 7 and solar_power_in_watts > 1200:
            structlog.get_logger().debug("It's sunny enough to not need heating at this temperature", last_temperature=last_temperature, solar_power_in_watts=solar_power_in_watts)
            return True

        structlog.get_logger().debug("Solar power", solar_power_in_watts=solar_power_in_watts)
        return False

    @staticmethod
    def reason_we_should_turn_on(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:

        if OccupantComesHome.needs_to_be_warmer(calculation_moment, device_infos):
            return "Needs to be warm for occupant coming home"

        if ManageSpaceHeatingPower.is_plenty_sunny_enough(calculation_moment, device_infos):
            structlog.get_logger().debug("Not turning on because it's plenty sunny enough")
            return None

        try:
            reason = ManageSpaceHeatingPower.is_plenty_warm_enough(calculation_moment, device_infos)
            if reason:
                return None
        except:
            pass

        structlog.get_logger().debug("It's not warm or sunny outside")

        if ManageSpaceHeatingPower.are_the_humans_awake(calculation_moment, device_infos):
            structlog.get_logger().debug("Ignoring schedule because the humans are awake")
        else:
            if Schedule.previous_job(calculation_moment) == Schedule.off_job_name():
                structlog.get_logger().debug("Heat pump was previously turned off by a schedule. We're not going to override that")
                return None

        dwell_time = Dwell.turn_on_dwell(calculation_moment, device_infos)

        should_have_been_cold_since = calculation_moment - datetime.timedelta(seconds=dwell_time)

        interesting_infos = [device_info for device_info in device_infos if LastTimeStamp.last_time_stamp_in_utc(device_info) >= should_have_been_cold_since]

        acceptable_missing = 3
        suitable_number_of_events = (dwell_time / 60) - acceptable_missing
        if len(interesting_infos) < suitable_number_of_events:
            structlog.get_logger().warning("There are insufficient readings to look at so not turning on power", size=len(interesting_infos))

        min_temp = TemperatureThresholds.min_flow_temp(calculation_moment, device_infos)
        cold_infos = [device_info for device_info in interesting_infos if float(device_info["ReturnTemperature"]) < min_temp]

        has_been_cold = len(cold_infos) == len(interesting_infos)

        flow_info = f" - the return temperature is currently {device_infos[-1]['ReturnTemperature']} °C"

        if has_been_cold:
            structlog.get_logger().info(f"It has been cold enough to turn on the heating{flow_info}")
        else:

            if cold_infos:
                has_been_old_duration = (calculation_moment - LastTimeStamp.last_time_stamp_in_utc(cold_infos[0])).total_seconds()

                on_in_seconds = int(dwell_time - has_been_old_duration)
                wait_info = f" for another {on_in_seconds} seconds"

            else:
                will_be_cold = ManageSpaceHeatingPower.when_will_it_be_cold_enough_to_turn_on(calculation_moment, device_infos, min_temp)
                if will_be_cold:
                    cold_plus_dwell = will_be_cold + datetime.timedelta(seconds=dwell_time)
                    wait_info = f" so we'll probably wait until {cold_plus_dwell.isoformat()[11:16] } using a dwell time of {round(dwell_time)} seconds"
                else:
                    wait_info = f" for {round(dwell_time)} seconds"

            structlog.get_logger().debug(
                f"It hasn't been cold enough to turn on the heating {flow_info} but it needs to be below the minimum temperature of {min_temp} °C{wait_info}"
            )

        if has_been_cold:
            return "Has been cold"

        return None

    @staticmethod
    def are_the_humans_awake(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> bool:
        # Don't expose this logic at the moment
        return False

    @staticmethod
    def when_will_it_be_cold_enough_to_turn_on(calculation_moment: datetime.datetime, device_infos: DeviceInfos, min_temp: float) -> Optional[datetime.datetime]:

        last_on = ManageSpaceHeatingPower.when_was_heating_last_on(device_infos)
        if last_on:
            structlog.get_logger().debug("Heat pump was last on", last_on=last_on)
        else:
            structlog.get_logger().debug("Could not determine when heat pump was last on")
            return None

        seconds_since_last_on = (calculation_moment - last_on).total_seconds()

        formatted_time = last_on.isoformat()

        return_when_turned_off = float(
            [device_info for device_info in device_infos if LastTimeStamp.last_time_stamp_in_utc(device_info).isoformat() == formatted_time][0]["ReturnTemperature"]
        )

        structlog.get_logger().debug(
            "The return temperature when we last turned off the heating", return_when_turned_off=return_when_turned_off, seconds_since_last_on=seconds_since_last_on
        )

        current_return = float(device_infos[-1]["ReturnTemperature"])

        if return_when_turned_off == current_return:
            # We don't know what the drop is going to be
            return None

        drop_per_second = (return_when_turned_off - current_return) / seconds_since_last_on

        seconds_until_cold = (current_return - min_temp) / drop_per_second

        time_when_cold = calculation_moment + datetime.timedelta(seconds=seconds_until_cold)

        structlog.get_logger().debug("Time when the return temperature will be at the minimum temperature", minTemp=min_temp, time_when_cold=time_when_cold.isoformat()[11:16])

        return time_when_cold

    @staticmethod
    def when_was_heating_last_on(device_infos: DeviceInfos) -> Optional[datetime.datetime]:

        for device_info in reversed(device_infos):
            if device_info["OperationMode"]:
                return LastTimeStamp.last_time_stamp_in_utc(device_info)

        return None
