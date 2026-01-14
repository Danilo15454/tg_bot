from datetime import datetime
days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS = {"ПН":"B","ВТ":"C","СР":"D","ЧТ":"E","ПТ":"F","СБ":"G","ВС":"H"}
TIME_CELLS = 4
WEEK = {"AT":"A","JUMP":1}
LESSON_COLUMN = "K"

now = datetime.now()
today = days[now.weekday()]
tomorrow = days[now.weekday() + 1]
week = now.isocalendar().week

def week_parity() :
    if week % 2 == 0:
        print('четная')
    else:
        print('нечет')  
#Четная неделя = 1 розклад
#Нечетная неделя = 2 розклад


class lessonHandler:
    def __init__(self,lesson_count:int,week_count:int,maplike):
        self.lesson_count = lesson_count
        self.week_count = week_count
        self.lessons_ids = {}
        self.sc_instance = maplike
        self.full_lesson_schedule = {}

    def load(self):
        for k in range(self.lesson_count):
            self.lessons_ids[k+1] = self.sc_instance.get(f"{LESSON_COLUMN}{k+1}")
        for w in range(self.week_count):
            self.full_lesson_schedule[w+1] = self.parseWeek(w)

    def parseDay(self, timeC: str, dayC: str, base_row: int):
        result = {}
        for n in range(TIME_CELLS):
            print(f"DAY:{dayC} CELL:{n+1} WEEK:{base_row}")
            row = base_row + (n + 1)
            time = self.sc_instance.get(f"{timeC}{row}")
            lessonID = self.sc_instance.get(f"{dayC}{row}")
            try:
                result[time] = self.lessons_ids.get(int(lessonID))
            except ValueError:
                continue
        return result
    
    def parseWeek(self, week: int):
        result = {}
        week_base_row = (week * (TIME_CELLS+2) ) + 1
        for d in DAYS:
            dayMap = self.parseDay(WEEK["AT"], DAYS[d], week_base_row)
            if dayMap:
                result[d] = dayMap
        return result
    
