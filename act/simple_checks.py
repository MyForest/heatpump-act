from .device_infos import DeviceInfos


class SimpleChecks:
    @staticmethod
    def are_device_infos_missing(device_infos: DeviceInfos) -> bool:
        if device_infos:
            return False
        return True

    @staticmethod
    def is_hot_water_forced_on(device_infos: DeviceInfos) -> bool:
        if device_infos:
            deviceInfo = device_infos[-1]

            return deviceInfo["ForcedHotWaterMode"]
        return False

    @staticmethod
    def is_holiday_mode_on(device_infos: DeviceInfos) -> bool:
        if device_infos:
            deviceInfo = device_infos[-1]
            return deviceInfo["HolidayMode"]
        return False

    @staticmethod
    def is_defrost_mode_on(device_infos: DeviceInfos) -> bool:
        if device_infos:
            deviceInfo = device_infos[-1]
            return deviceInfo["DefrostMode"]
        return False

    @staticmethod
    def is_heatpump_offline(device_infos: DeviceInfos) -> bool:
        if device_infos:
            deviceInfo = device_infos[-1]
            return deviceInfo["Offline"]
        return False
