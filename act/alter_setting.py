import json
import os
from dotenv import load_dotenv
from datetime import datetime
import structlog
import typer
from typing import Any

import urllib3

load_dotenv()

# --------------------------------------------------------------------------------
class AlterSetting:
    def __init__(self) -> None:
        self.__logger = structlog.get_logger(self.__class__.__name__)

    def record_action(self, name: str, value: Any, message: str, source: str) -> None:
        effectiveMoment = datetime.utcnow()
        actionsFolder = os.path.join(
            "/state",
            "actions",
            "raw",
            "{:%Y}".format(effectiveMoment),
            "{:%m}".format(effectiveMoment),
            "{:%d}".format(effectiveMoment),
        )

        if not os.path.exists(actionsFolder):
            self.__logger(f"Creating {actionsFolder}")
            os.makedirs(actionsFolder)

        path = os.path.join(
            actionsFolder,
            f"{ effectiveMoment.isoformat() }_{ name }_{ value }.json",
        )
        with open(path, "w+t") as action_file:
            self.__logger.debug(f"Saving '{name}' action to {path}")
            json.dump(
                {
                    "name": name,
                    "value": value,
                    "source": source,
                    "message": message,
                    "moment": f"{effectiveMoment.isoformat()}+00:00",
                },
                action_file,
                indent=4,
                sort_keys=True,
            )

    # --------------------------------------------------------------------------------
    def alter_setting(
        self,
        name: str = typer.Option(
            default="SetTankWaterTemperature",
            help="Setting name",
        ),
        value: str = typer.Option(
            default="48",
            help="Setting value",
        ),
        message: str = typer.Option(default="Specified on command line"),
        source: str = typer.Option(default="AlterSetting.main"),
        shoosh: bool = False,
    ) -> None:
        """
        Instruct the heatpump to alter a setting.
        """

        self.do(name, value, message, source, shoosh)

    # --------------------------------------------------------------------------------
    def do(self, name: str, value: str | float, message: str, source: str, shoosh: bool = False) -> None:

        self.record_action(name, value, message, source)

        http = urllib3.PoolManager()

        baseURL = "https://app.melcloud.com/Mitsubishi.Wifi.Client/"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-MitsContextKey": os.environ["MITS_CONTEXT_KEY"],
        }

        # EffectiveFlags - setting name
        # 8 OperationModeZone1   [ 0= Room, 1 = Flow, 2= Curve ]

        # The prohibit commands don't seem to perform the update

        flags = {
            "Power": 1,
            "OperationMode": 2,
            "EcoHotWater": 4,
            "OperationModeZone1": 8,
            "OperationModeZone2": 16,
            "SetTankWaterTemperature": 32,
            "TargetHCTemperatureZone1": 128,
            "TargetHCTemperatureZone2": 512,
            "ForcedHotWaterMode": 65536,
            "HolidayMode": 131072,
            "ProhibitHotWater": 262144,
            "ProhibitHeatingZone1": 524288,
            "ProhibitCoolingZone1": 1048576,
            "ProhibitHeatingZone2": 2097152,
            "ProhibitCoolingZone2": 4194304,
            "Demand": 67108864,
            "ThermostatTemperatureZone1": 8589934592,
            "ThermostatTemperatureZone2": 34359738368,
            "SetFlowTemperature": 281474976710656,
            "After here I added manually": True,
            "SetHeatFlowTemperatureZone1": 281474976710656,
            "SetTemperatureZone1": 33554432,
            "ProhibitZone1": 524288,
        }

        # Read the current values because some of the updategrams require multiple settings and we don't know the current value for the other settings
        fake = {"EffectiveFlags": 0, "DeviceID": os.environ["DEVICE_ID"], "DeviceType": 1}
        r = http.request(
            "POST",
            f"{baseURL}Device/SetAtw",
            headers=headers,
            body=json.dumps(fake).encode("utf-8"),
        )

        updateGram = json.loads(r.data.decode("utf-8"))

        # Now update the setting specified
        updateGram["EffectiveFlags"] = flags[name]
        derived_value: Any = value
        if value == "true":
            derived_value = True
        if value == "false":
            derived_value = False
        updateGram[name] = derived_value

        self.validate_settings(updateGram)

        body = json.dumps(updateGram).encode("utf-8")

        if not shoosh:
            self.__logger.info("Sending update...")
        r = http.request("POST", f"{baseURL}Device/SetAtw", headers=headers, body=body)

        if not shoosh:
            self.__logger.info(r.data)

    # --------------------------------------------------------------------------------
    def validate_settings(self, updateGram):

        # MINIMUM_ATW_SET_TEMPERATURE: 10,
        # MAXIMUM_ATW_SET_TEMPERATURE: 30,

        if float(updateGram["SetHeatFlowTemperatureZone1"]) < 25:
            raise Exception("The flow temp can't be below 25 °C")

        if float(updateGram["SetTankWaterTemperature"]) < 10:
            raise Exception("The water tank temp can't be below 10 °C")

        max_hot_water_temp = 60
        if float(updateGram["SetTankWaterTemperature"]) > max_hot_water_temp:
            raise Exception(f"The water tank temp can't be above {max_hot_water_temp} °C")


if __name__ == "__main__":
    typer.run(AlterSetting().alter_setting)
