class lessonReschedulerHandler:
    def __init__(self, data: dict, push_func):
        self.data = data
        self.push = push_func
        self.for_removal = {}

    def _cleanup(self):
        for day,items in list(self.data.items()):
            if len(items) == 0:
                del self.data[day]

    def clearDay(self, day: int):
        self.data.pop(str(day), None)
        self.push(self.data,"scheduled")

    def clearLesson(self, day: int, time: str):
        self.data.get(str(day), {}).pop(time, None)
        self._cleanup()
        self.push(self.data,"scheduled")

    def clearOld(self, current_day: int):
        for day in list(self.data.keys()):
            if day.isdigit() and int(day) < current_day:
                del self.data[day]
        self.push(self.data,"scheduled")

    def schedule(self, day: int, time: str, lesson_id: int, isOriginal=True):
        key = str(day)
        self.data.setdefault(key, {})
        self.data[key][time] = lesson_id

        if int(lesson_id) == -1 and not isOriginal:
            self.clearLesson(day, time)
            
        self.push(self.data,"scheduled")

    def isChanged(self, day: int):
        return bool(self.data.get(str(day)))
    
    def getChanges(self, day: int):
        return self.data.get(str(day), {})
    
    # 
