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
            device_info = device_infos[-1]

            return device_info["ForcedHotWaterMode"]
        return False

    @staticmethod
    def is_holiday_mode_on(device_infos: DeviceInfos) -> bool:
        if device_infos:
            device_info = device_infos[-1]
            return device_info["HolidayMode"]
        return False

    @staticmethod
    def is_defrost_mode_on(device_infos: DeviceInfos) -> bool:
        if device_infos:
            device_info = device_infos[-1]
            return device_info["DefrostMode"]
        return False

    @staticmethod
    def is_heatpump_offline(device_infos: DeviceInfos) -> bool:
        if device_infos:
            device_info = device_infos[-1]
            return device_info["Offline"]
        return False
