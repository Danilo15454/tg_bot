from datetime import datetime, timedelta
import copy
from scheduleChange import lessonReschedulerHandler
days_list = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
DAYS = {"ПН":"B","ВТ":"C","СР":"D","ЧТ":"E","ПТ":"F","СБ":"G","ВС":"H"}
TIME_CELLS = 4
WEEK = {"AT":"A","JUMP":1}
MIT_LINK = "https://meet.google.com/{}?authuser={}"
ZOOM_LINK = "https://krkm-dnu-edu-ua.zoom.us/j/{}"

LESSON_COLUMN = "K"
NAME_LESSON_COLUMN = "J"

def today_int():
    now = datetime.now()
    return now.day

def tommorow_int():
    now = datetime.now() + timedelta(days=1)
    return now.day

def _format_link_raw(l,n):
   return MIT_LINK.format(l, n) if "-" in l else ZOOM_LINK.format(l)

def format_link(string: str,mit: int=0) -> str:
    if not string:
        return ""
    
    if "|" in string:
        g1, g2 = string.split("|")
        return f"{_format_link_raw(g1,mit)} (1 група)\n{_format_link_raw(g2,mit)} (2 група)"
    else:
        return _format_link_raw(string,mit)
    
def getWeek(date) -> int:
    return 1 if date.isocalendar().week % 2 == 0 else 2
def weekDay(date) -> str:
    return days_list[date.weekday()]

class lessonHandler:
    def __init__(self,lesson_count:int,week_count:int,maplike):
        self.lesson_count = lesson_count
        self.week_count = week_count
        self.lessons_ids = {}
        self.lessons_names = {}
        self.sc_instance = maplike
        self.full_lesson_schedule = {}
        self.changer = None
    
    def getLessonIds(self,extra:bool=True) -> str:
        text = (
            "Введіть номер уроку:\n"
        )

        if extra:
            text += "[-1] - Відмінити зміни\n"
            text += "[0] - Видалити урок\n"

        for index,value in enumerate(self.lessons_names.values()):
            text += f"[{index+1}] - {value}\n"
        return text

    def load(self):
        for k in range(self.lesson_count):
            self.lessons_ids[k+1] = self.sc_instance.get(f"{LESSON_COLUMN}{k+1}")
            self.lessons_names[k + 1] = self.sc_instance.get(f"{NAME_LESSON_COLUMN}{k+1}")
        for w in range(self.week_count):
            self.full_lesson_schedule[w+1] = self.parseWeek(w)

    def setChanger(self,changer:lessonReschedulerHandler):
        self.changer = changer

    def _repack_day(self,day:dict,day_num:int):
        if self.changer and self.changer.isChanged(day_num):
            new_day = copy.deepcopy(day)
            for time, lesson_id in self.changer.data.get(str(day_num), {}).items():
                if lesson_id == "-1":
                    if time in new_day:
                        del new_day[time]
                else:
                    lesson_code = self.lessons_ids.get(int(lesson_id))
                    lesson_name = self.lessons_names.get(int(lesson_id))
                    new_day[time] = { "name":lesson_name,"id":lesson_code }
            return new_day
        else:
            return day

    def parseDay(self, timeC: str, dayC: str, base_row: int):
        result = {}

        for n in range(TIME_CELLS):
            row = base_row + (n + 1)
            time = self.sc_instance.get(f"{timeC}{row}")
            lessonID = self.sc_instance.get(f"{dayC}{row}")
            try:
                lessonID = int(lessonID)
            except (TypeError, ValueError):
                continue
            lesson_code = self.lessons_ids.get(lessonID)
            lesson_name = self.lessons_names.get(lessonID)

            result[time] = {
                "name": lesson_name,
                "id": lesson_code
            }

        return result
    
    def parseWeek(self, week: int):
        result = {}
        week_base_row = (week * (TIME_CELLS+2) ) + 1
        for d in DAYS:
            dayMap = self.parseDay(WEEK["AT"], DAYS[d], week_base_row)
            if dayMap:
                result[d] = dayMap
        return result
    
    # -----------------------------------------------------
    def take_day(self):
        now = datetime.now()
        week_num = getWeek(now)
        return self.getSchedule(week_num,now,True)
    
    def has_lesson(self,week:int,day:int,lid:int) -> tuple[bool,str]:
        target_day = self.getSchedule(week,day)
        target_name = self.lessons_names.get(lid)
        if target_name is not None:
            for lesson in target_day.values():
                if lesson['name'] == target_name:
                    return True,lesson['name']
        return False,""
    
    def getSchedule(self,week_num:int,day,edited:bool=True):
        day_name = weekDay(day)
        if edited:
            orig = self.full_lesson_schedule.get(week_num, {}).get(day_name, {})
            return self._repack_day(orig, day.day)
        else:
           return self.full_lesson_schedule.get(week_num, {}).get(day_name, {})
    # -----------------------------------------------------

    def schedule_target_day(self,day_int:int,mit:int=0):
        now = datetime.now().replace(day=day_int)
        day = weekDay(now)
        week_num = getWeek(now)
        
        output = f"📅 Розклад на {day_int} : (<b>{day}</b>)\n\n"
        sched = self.getSchedule(week_num,now,True)
        
        if not sched:
            return output + "<b>Пар на день немає</b>\n\n"

        for time in sorted(sched.keys(), key=lambda t: [int(x) for x in t.split(":")]):
            les = sched[time]
            name, lid = les.get("name", "Без назви"), les.get("id", "")
            output += f"<b>{time}</b> — {name}\n{format_link(lid,mit)}\n\n"
        return output

    def schedule_today(self,mit:int=0):
        now = datetime.now()
        day = weekDay(now)
        week_num = getWeek(now)
        
        output = f"📅 Розклад на сьогодні (<b>{day}</b>)\n\n"
        sched = self.getSchedule(week_num,now,True)
        
        if not sched:
            return output + "<b>Пар на сьогодні немає</b>\n\n"

        for time in sorted(sched.keys(), key=lambda t: [int(x) for x in t.split(":")]):
            les = sched[time]
            name, lid = les.get("name", "Без назви"), les.get("id", "")
            output += f"<b>{time}</b> — {name}\n{format_link(lid,mit)}\n\n"

        return output

    def schedule_tomorrow(self,mit:int=0):
        date = datetime.now() + timedelta(days=1)
        
        is_weekend = date.weekday() >= 5
        while date.weekday() >= 5:
            date += timedelta(days=1)

        day = weekDay(date)
        week_num = getWeek(date)
        
        if is_weekend:
            output = f"📅 Сьогодні вихідний, тому розклад на <b>{day}</b>\n\n"
        else:
            output = f"📅 Розклад на завтра (<b>{day}</b>)\n\n"

        sched = self.getSchedule(week_num,date,True)
        if not sched:
            return output + f"Пар на <b>{day}</b> немає\n\n"

        for time in sorted(sched.keys(), key=lambda t: [int(x) for x in t.split(":")]):
            les = sched[time]
            name, lid = les.get("name", "Без назви"), les.get("id", "")
            output += f"<b>{time}</b> — {name}\n{format_link(lid,mit)}\n\n"

        return output


    def take_schedule_day(self, day_name: str,mit:int=0):
        output = f"📅 Розклад <b>{day_name}</b>\n\n"

        weekday = days_list.index(day_name)
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        date = start_of_week + timedelta(days=weekday)

        week1 = self.getSchedule(1,date,True)
        week2 = self.getSchedule(2,date,True)
        
        all_times = set(week1.keys()) | set(week2.keys())

        def format_lesson_info(lesson):
            name = lesson.get("name", "Без назви")
            lid = lesson.get("id", "")
            return f"{name}\n{format_link(lid,mit)}"

        sorted_times = sorted(all_times, key=lambda t: [int(x) for x in t.split(':')])

        for time in sorted_times:
            l1 = week1.get(time)
            l2 = week2.get(time)

            if l1 == l2:
                output += f"<b>{time}</b> — {format_lesson_info(l1)}\n\n"
            else:
                if l1:
                    output += f"1 тиждень \n<b>{time}</b> — {format_lesson_info(l1)}\n\n"
                if l2:
                    output += f"2 тиждень \n<b>{time}</b> — {format_lesson_info(l2)}\n\n"

        return output
