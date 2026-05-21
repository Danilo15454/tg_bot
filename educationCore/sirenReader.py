from urllib import response

from alerts_in_ua import Client as AlertsClient
import requests

class sirenReminder:
    def __init__(self, City:str, ApiKey:str):
        self.City = City
        self.Client = AlertsClient(token=ApiKey)
        self.Data = {}

    def getData(self):
        request = self.Client.get_active_alerts()
        print(request)

    def cityTake(self):
        response = requests.get("https://ubilling.net.ua/aerialalerts/?source=skog&raw")
    
        data = response.json()

        for district in data["raw"]["3"]["districts"]:
            if district["name"] == "Дніпровський район":
                print(district["alert"])
                return district["alert"]
        
        
        
