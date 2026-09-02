import requests
import time
from io import BytesIO


class sirenReminder:
    def __init__(self, City: str):
        self.City = City
        self.Data = {}

        self._alert_data = None
        self._alert_data_time = 0

    def getData(self):
        request = self.Client.get_active_alerts()
        print(request)

    def getMap(self):
        request = requests.get("https://ubilling.net.ua/aerialalerts/?map=true")
        request.raise_for_status()
        return BytesIO(request.content)

    def cityTake(self):
        if (self._alert_data is None or time.time() - self._alert_data_time >= 60):
            response = requests.get("https://ubilling.net.ua/aerialalerts/?source=default&raw")
            response.raise_for_status()

            self._alert_data = response.json()
            self._alert_data_time = time.time()

        def find_alert(obj, name):
            name_lower = name.lower()

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, dict) and "enabled" in value:
                        if name_lower in key.lower():
                            return value["enabled"]

                    result = find_alert(value, name)
                    if result is not None:
                        return result

            elif isinstance(obj, list):
                for item in obj:
                    result = find_alert(item, name)
                    if result is not None:
                        return result

            return None

        root = self._alert_data.get("raw", self._alert_data) if isinstance(self._alert_data, dict) else self._alert_data

        return find_alert(root, self.City)