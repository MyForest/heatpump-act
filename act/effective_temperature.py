import datetime
import math
import os
from typing import Dict, Optional

import structlog
import typer

app = typer.Typer()


class EffectiveTemperature:
    @app.command()
    @staticmethod
    def apparent_temp(
        calculation_moment: datetime.datetime = typer.Option(
            default=datetime.datetime.utcnow(),
            help="Run as though it is this UTC moment in ISO8601 format.",
        ),
    ) -> float:
        stats = EffectiveTemperature.interesting_statistics(calculation_moment)

        # https://pywws.readthedocs.io/en/latest/api/pywws.conversions.html#pywws.conversions.apparent_temp
        relative_humidity = stats["outdoorRelativeHumidity"]
        temp = stats["outdoorTemperature"]
        wind = stats["wind"]

        vap_press = (float(relative_humidity) / 100.0) * 6.105 * math.exp(17.27 * temp / (237.7 + temp))
        eff = temp + (0.33 * vap_press) - (0.70 * wind) - 4.00

        if eff > 100:
            raise Exception("The effective temperature is " + str(eff))
        return round(eff, 2)

    @app.command()
    @staticmethod
    def wind_chill(
        calculation_moment: datetime.datetime = typer.Option(
            default=datetime.datetime.utcnow(),
            help="Run as though it is this UTC moment in ISO8601 format.",
        ),
    ) -> float:
        stats = EffectiveTemperature.interesting_statistics(calculation_moment)

        # https://pywws.readthedocs.io/en/latest/_modules/pywws/conversions.html#wind_chill
        temp = stats["outdoorTemperature"]
        wind = stats["wind"]

        wind_kph = wind * 3.6
        if wind_kph <= 4.8 or temp > 10.0:
            return temp
        wind_chill = min(
            13.12 + (temp * 0.6215) + (((0.3965 * temp) - 11.37) * (wind_kph**0.16)),
            temp,
        )

        return round(wind_chill, 2)

    @staticmethod
    def interesting_statistics(calculation_moment: datetime.datetime) -> Dict:
        """Go backwards from calc time in case there is no data at that specific time (there won't be)"""

        default_weather = {
            "wind": 0,
            "outdoorTemperature": 10,
            "outdoorRelativeHumidity": 50,
            "moment": calculation_moment,
        }

        weather_data_root_folder = "/weather"
        if not os.path.exists(weather_data_root_folder):
            structlog.get_logger().debug(f"Unable to find weather folder {weather_data_root_folder}")
            return default_weather

        time_filter = calculation_moment.isoformat()[:19].replace("T", " ")
        tolerance = calculation_moment - datetime.timedelta(minutes=60)
        tolerance_filter = tolerance.isoformat()[:19].replace("T", " ")

        weather_info = EffectiveTemperature.walk_files(weather_data_root_folder, time_filter, tolerance_filter)
        if weather_info:
            return weather_info

        raise Exception(f"Unable to find weather data for {calculation_moment.isoformat()}")

    @staticmethod
    def walk_files(weather_data_root_folder, time_filter, tolerance_filter) -> Optional[Dict]:
        for root, dirs, files in os.walk(weather_data_root_folder, topdown=True):
            dirs.sort(reverse=True)
            files.sort(reverse=True)

            for file_name in files:
                full_path = os.path.join(root, file_name)
                with open(full_path, encoding="utf-8") as weather_file:
                    for line in reversed(weather_file.readlines()):
                        parts = line.split(",")
                        moment = parts[0]
                        if moment < tolerance_filter:
                            raise Exception(f"Unable to find weather data beyond tolerance of {tolerance_filter}")

                        if moment < time_filter:
                            if parts[7] and parts[4] and parts[5]:
                                wind = float(parts[7])  # average
                                relative_humidity = float(parts[4])
                                outdoor_temperature = float(parts[5])
                                if wind is not None:
                                    if relative_humidity is not None:
                                        # logging.debug("Getting weather stats from " + fullPath + " and moment " + str(moment))
                                        return {
                                            "wind": wind,
                                            "outdoorTemperature": outdoor_temperature,
                                            "outdoorRelativeHumidity": relative_humidity,
                                            "moment": datetime.datetime.strptime(moment, "%Y-%m-%d %H:%M:%S"),
                                        }

        return None


if __name__ == "__main__":
    app()
