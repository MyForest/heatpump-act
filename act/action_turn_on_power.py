import datetime
import sys
from typing import Generator, Optional

import structlog

from .action import Action
from .action_covid import Covid
from .device_infos import DeviceInfos
from .effective_temperature import EffectiveTemperature
from .schedule import Schedule
from .state_change import StateChange


# --------------------------------------------------------------------------------
class TurnOnPower:
    @staticmethod
    def turn_on_power(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        current_power = device_infos[-1]["Power"]

        structlog.get_logger().debug("Current power state", current_power=current_power)

        if not current_power:
            reason = TurnOnPower.should_turn_on_power(calculation_moment, device_infos)
            if reason:
                yield Action("Power", "true", reason)

    @staticmethod
    def should_turn_on_power(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:

        if not Covid.can_be_powered_off(calculation_moment, device_infos):
            return "COVID mode indicates we need the heating on"

        latest_device_info = device_infos[-1]
        if latest_device_info["Power"]:
            return None

        if latest_device_info["ForcedHotWaterMode"]:
            return "Something indicated the tank should be forcibly warmed up"

        if TurnOnPower.__should_dwell(calculation_moment, device_infos):
            return None

        reasons = [
            TurnOnPower.should_outdoor_temperature_turn_it_on(calculation_moment, device_infos),
            TurnOnPower.should_room_temperature_turn_it_on(device_infos),
        ]

        interestingReasons = [reason for reason in reasons if reason]
        if interestingReasons:
            return ", ".join(interestingReasons)

        if Schedule.previous_job(calculation_moment) != Schedule.on_job_name():
            # Let's find out when the next planned on time is
            next_allowed_on_time = Schedule.next_job_moment(calculation_moment, Schedule.on_job_name())
            if next_allowed_on_time:
                structlog.get_logger().debug("The next time heating is allowed", next_allowed_on_time=next_allowed_on_time.isoformat())

        return None

    @staticmethod
    def __should_dwell(calculation_moment, device_infos: DeviceInfos) -> bool:
        last_heating = StateChange.last_heating(device_infos)

        if last_heating:
            time_since_last_heating = calculation_moment - last_heating
            threshold = 900
            if calculation_moment.hour > 0 and calculation_moment.hour < 5:
                # Be less reactive during the night
                threshold = threshold * 2

            if time_since_last_heating.total_seconds() < threshold:
                structlog.get_logger().debug(
                    "Should dwell since the heating was last on recntly (less than the threshold)",
                    threshold=threshold,
                    time_since_last_heating=time_since_last_heating.total_seconds(),
                )
                return True

        return False

    @staticmethod
    def should_outdoor_temperature_turn_it_on(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Optional[str]:

        outdoor_temperature = float(device_infos[-1]["OutdoorTemperature"])
        effective_temperature = outdoor_temperature
        # Can we get a better temperature?
        try:
            effective_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
            structlog.get_logger().debug(
                "Effective temperature comparison",
                effective_temperature=effective_temperature,
                outdoor_temperature=outdoor_temperature,
                delta=round(effective_temperature - outdoor_temperature, 2),
            )
        except:
            structlog.get_logger().warning("Unable to get effective temperature", exception_type=sys.exc_info()[0], exception=sys.exc_info()[1])

        # The efficiency is very low when it's cold so don't be too trigger happy
        too_cold = -4

        if outdoor_temperature < too_cold:
            return f"It's {outdoor_temperature} °C outside and anything less than {too_cold} °C is considered cold enough to turn on for"

        # Be a little more demanding of the effective temp when it's not scheduled to be on
        too_cold = too_cold - 4
        if effective_temperature < too_cold:
            return f"It's effectively {effective_temperature} °C outside and anything less than {too_cold} °C is considered cold enough to turn on for"

        return None

    @staticmethod
    def should_room_temperature_turn_it_on(
        device_infos: DeviceInfos,
    ) -> Optional[str]:

        room_temperature = float(device_infos[-1]["RoomTemperatureZone1"])

        too_cold = 10

        if room_temperature < too_cold:
            return f"It's only {room_temperature} °C in the room and anything less than {too_cold} °C is considered cold enough to turn on for"

        return None
