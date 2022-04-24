from act.act import Act
from act.device_infos import DeviceInfos


def test_something():

    device_infos: DeviceInfos = [
        {
            "TankWaterTemperature": 12,
            "FlowTemperature": 30,
            "ReturnTemperature": 28,
            "ForcedHotWaterMode": 0,
            "Power": 1,
            "LastTimeStamp": "2019-11-03T14:48:26",
            "OutdoorTemperature": 5,
            "OperationMode": 0,
            "RoomTemperatureZone1": 23,
            "SetTankWaterTemperature": 48,
            "TargetHCTemperatureZone1": 40,
            "HeatPumpFrequency": 26,
        }
    ]

    Act().describe_device_infos_being_operated_on(device_infos)
