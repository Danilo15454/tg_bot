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
        if self._alert_data is None or time.time() - self._alert_data_time >= 60:
            response = requests.get("https://ubilling.net.ua/aerialalerts/?source=Klymenko&raw")
            response.raise_for_status()

            self._alert_data = response.json()
            self._alert_data_time = time.time()

        root = (
            self._alert_data.get("raw", self._alert_data)
            if isinstance(self._alert_data, dict)
            else self._alert_data
        )

        if root.get("3"):
            for district in root["3"].get("districts", []):
                if district.get("name") == self.City:
                    return district.get("alert")

        city_data = root.get(self.City)
        if city_data:
            return city_data.get("enabled")

        return False