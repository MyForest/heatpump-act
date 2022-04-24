import datetime
import logging
import math
import os

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
        rh = stats["outdoorRelativeHumidity"]
        temp = stats["outdoorTemperature"]
        wind = stats["wind"]

        vap_press = (float(rh) / 100.0) * 6.105 * math.exp(17.27 * temp / (237.7 + temp))
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
        windChill = min(
            13.12 + (temp * 0.6215) + (((0.3965 * temp) - 11.37) * (wind_kph**0.16)),
            temp,
        )

        return round(windChill, 2)

    @staticmethod
    def interesting_statistics(calculation_moment: datetime.datetime) -> dict:
        """Go backwards from calc time in case there is no data at that specific time (there won't be)"""

        default_weather = {
            "wind": 0,
            "outdoorTemperature": 10,
            "outdoorRelativeHumidity": 50,
            "moment": calculation_moment,
        }

        weatherDataRootFolder = "/weather"
        if not os.path.exists(weatherDataRootFolder):
            logging.debug(f"Unable to find weather folder {weatherDataRootFolder}")
            return default_weather

        timeFilter = calculation_moment.isoformat()[:19].replace("T", " ")
        tolerance = calculation_moment - datetime.timedelta(minutes=60)
        toleranceFilter = tolerance.isoformat()[:19].replace("T", " ")

        for root, dirs, files in os.walk(weatherDataRootFolder, topdown=True):
            dirs.sort(reverse=True)
            files.sort(reverse=True)

            for f in files:
                fullPath = os.path.join(root, f)
                with open(fullPath) as weatherFile:
                    for line in reversed(weatherFile.readlines()):
                        parts = line.split(",")
                        moment = parts[0]
                        if moment < toleranceFilter:
                            raise Exception(f"Unable to find weather data beyond tolerance of {toleranceFilter}")

                        if moment < timeFilter:
                            if parts[7] and parts[4] and parts[5]:
                                wind = float(parts[7])  # average
                                relativeHumidity = float(parts[4])
                                outdoorTemperature = float(parts[5])
                                if wind != None:
                                    if relativeHumidity != None:
                                        # logging.debug("Getting weather stats from " + fullPath + " and moment " + str(moment))
                                        return {
                                            "wind": wind,
                                            "outdoorTemperature": outdoorTemperature,
                                            "outdoorRelativeHumidity": relativeHumidity,
                                            "moment": datetime.datetime.strptime(moment, "%Y-%m-%d %H:%M:%S"),
                                        }

        raise Exception(f"Unable to find weather data for {calculation_moment.isoformat()}")


if __name__ == "__main__":
    app()
