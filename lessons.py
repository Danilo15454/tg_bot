from datetime import datetime, timedelta
days_list = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
DAYS = {"ПН":"B","ВТ":"C","СР":"D","ЧТ":"E","ПТ":"F","СБ":"G","ВС":"H"}
TIME_CELLS = 4
WEEK = {"AT":"A","JUMP":1}
MIT_LINK = "https://meet.google.com/{}"
ZOOM_LINK = "https://krkm-dnu-edu-ua.zoom.us/j/{}"

LESSON_COLUMN = "K"
NAME_LESSON_COLUMN = "J"


class lessonHandler:
    def __init__(self,lesson_count:int,week_count:int,maplike):
        self.lesson_count = lesson_count
        self.week_count = week_count
        self.lessons_ids = {}
        self.lessons_names = {}
        self.sc_instance = maplike
        self.full_lesson_schedule = {}

    def load(self):
        for k in range(self.lesson_count):
            self.lessons_ids[k+1] = self.sc_instance.get(f"{LESSON_COLUMN}{k+1}")
            self.lessons_names[k + 1] = self.sc_instance.get(f"{NAME_LESSON_COLUMN}{k+1}")
        for w in range(self.week_count):
            self.full_lesson_schedule[w+1] = self.parseWeek(w)

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

    def schedule_today(self):
        now = datetime.now()
        day = days_list[now.weekday()]
        week_num = 1 if now.isocalendar().week % 2 == 0 else 2
        
        output = f"📅 Розклад на сьогодні ({day})\n\n"
        sched = self.full_lesson_schedule.get(week_num, {}).get(day, {})
        
        if not sched:
            return output + "Пар на сьогодні немає\n\n"

        for time in sorted(sched.keys(), key=lambda t: [int(x) for x in t.split(":")]):
            les = sched[time]
            name, lid = les.get("name", "Без назви"), les.get("id", "")
            
            if "|" in lid:
                g1, g2 = lid.split("|")
                l1 = (MIT_LINK if "-" in g1 else ZOOM_LINK).format(g1)
                l2 = (MIT_LINK if "-" in g2 else ZOOM_LINK).format(g2)
                output += f"{time} — {name}\n{l1} (1 група)\n{l2} (2 група)\n\n"
            else:
                l = (MIT_LINK if "-" in lid else ZOOM_LINK).format(lid)
                output += f"{time} — {name}\n{l}\n\n"

        return output

    def schedule_tomorrow(self):
        from datetime import timedelta
        date = datetime.now() + timedelta(days=1)
        
        is_weekend = date.weekday() >= 5
        while date.weekday() >= 5:
            date += timedelta(days=1)

        day = days_list[date.weekday()]
        week_num = 1 if date.isocalendar().week % 2 == 0 else 2
        
        if is_weekend:
            output = f"📅 **Сьогодні вихідний, тому розклад на {day}**\n\n"
        else:
            output = f"📅 **Розклад на завтра ({day})**\n\n"

        sched = self.full_lesson_schedule.get(week_num, {}).get(day, {})
        if not sched:
            return output + f"**Пар на {day} немає**\n\n"

        for time in sorted(sched.keys(), key=lambda t: [int(x) for x in t.split(":")]):
            les = sched[time]
            name, lid = les.get("name", "Без назви"), les.get("id", "")
            
            if "|" in lid:
                g1, g2 = lid.split("|")
                l1 = (MIT_LINK if "-" in g1 else ZOOM_LINK).format(g1)
                l2 = (MIT_LINK if "-" in g2 else ZOOM_LINK).format(g2)
                output += f"**{time}** — {name}\n{l1} (1 група)\n{l2} (2 група)\n\n"
            else:
                l = (MIT_LINK if "-" in lid else ZOOM_LINK).format(lid)
                output += f"**{time}** — {name}\n{l}\n\n"

        return output


    def take_schedule_day(self, day_name: str):
        output = f"📅 Розклад {day_name}\n\n"

        week1 = self.full_lesson_schedule.get(1, {}).get(day_name, {})
        week2 = self.full_lesson_schedule.get(2, {}).get(day_name, {})
        
        all_times = set(week1.keys()) | set(week2.keys())

        def format_lesson_info(lesson):
            name = lesson.get("name", "Без назви")
            lid = lesson.get("id", "")
            
            if "|" in lid:
                g1, g2 = lid.split("|")
                link1 = MIT_LINK.format(g1) if "-" in g1 else ZOOM_LINK.format(g1)
                link2 = MIT_LINK.format(g2) if "-" in g2 else ZOOM_LINK.format(g2)
                return f"{name}\n{link1} (1 група)\n{link2} (2 група)"
            else:
                link = MIT_LINK.format(lid) if "-" in lid else ZOOM_LINK.format(lid)
                return f"{name}\n{link}"

        sorted_times = sorted(all_times, key=lambda t: [int(x) for x in t.split(':')])

        for time in sorted_times:
            l1 = week1.get(time)
            l2 = week2.get(time)

            if l1 == l2:
                output += f"{time} — {format_lesson_info(l1)}\n\n"
            else:
                if l1:
                    output += f"1 тиждень \n**{time}** — {format_lesson_info(l1)}\n\n"
                if l2:
                    output += f"2 тиждень \n**{time}** — {format_lesson_info(l2)}\n\n"

        return output
