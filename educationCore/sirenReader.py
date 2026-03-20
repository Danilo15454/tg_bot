from alerts_in_ua import Client as AlertsClient

class sirenReminder:
    def __init__(self, City:str, ApiKey:str):
        self.City = City
        self.Client = AlertsClient(token=ApiKey)
        self.Data = {}

    def getData(self):
        request = self.Client.get_active_alerts()
        print(request)
        
