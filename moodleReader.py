import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

class MoodleHandler:
    LOGIN_URL = "https://moodle.krkm.dnu.edu.ua/login/index.php"
    CALENDAR_URL = "https://moodle.krkm.dnu.edu.ua/calendar/view.php?view=day&time={}"
    LOGIN_ERROR = "Немає данних для входа."
    FETCH_FAIL = "Не вдалося загрузити матеріал."
    KEY_ERROR = "Неправильний ключ або формат ключа."
    CACHE_DURATION = timedelta(minutes=10)

    def __init__(self, key: str):
        parts = key.split(":", 1)
        if len(parts) != 2:
            self.KEY = None
            self.key_error = True
        else:
            self.KEY = parts
            self.key_error = False
        self.session: requests.Session | None = None
        self._cache: dict[str, tuple[str, datetime]] = {}

    def close(self):
        self.key_error = True
        if self.session:
            self.session.close()

    def _session_expired(self, html: str) -> bool:
        if not html:
            return True
        indicators = [
            "login/index.php",
            "logintoken", 
            'name="username"'
        ]
        return any(ind in html for ind in indicators)


    def _login(self) -> bool:
        if self.key_error or self.KEY is None:
            return False

        login, password = self.KEY
        s = requests.Session()

        try:
            r = s.get(self.LOGIN_URL, timeout=10)
        except requests.RequestException:
            return False

        soup = BeautifulSoup(r.text, "html.parser")
        token_tag = soup.find("input", {"name": "logintoken"})
        token = token_tag["value"] if token_tag else None

        payload = {
            "username": login,
            "password": password,
        }
        if token:
            payload["logintoken"] = token

        try:
            r = s.post(self.LOGIN_URL, data=payload, timeout=10)
        except requests.RequestException:
            return False

        if "logout" not in r.text.lower():
            return False

        self.session = s
        return True

    def cache_stamp(self, url: str) -> str:
        cached = self._cache.get(url)
        if cached:
            _, ts = cached
            remaining = self.CACHE_DURATION - (datetime.now() - ts)
            if remaining.total_seconds() <= 0:
                return "00:00"
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"

    def _request(self, url: str, retry=True) -> str:
        cached = self._cache.get(url)
        if cached:
            html, ts = cached
            if datetime.now() - ts < self.CACHE_DURATION:
                return html

        if self.key_error or self.KEY is None:
            return self.KEY_ERROR

        if self.session is None:
            if not self._login():
                return self.LOGIN_ERROR

        try:
            r = self.session.get(url, timeout=10)
        except requests.RequestException:
            return self.FETCH_FAIL

        if retry and self._session_expired(r.text):
            if not self._login():
                return self.LOGIN_ERROR
            try:
                r = self.session.get(url, timeout=10)
            except requests.RequestException:
                return self.FETCH_FAIL

        html = r.text or self.FETCH_FAIL
        self._cache[url] = (html, datetime.now())
        return html

    def has_lessons(self, date: datetime) -> (bool | str):
        start_of_day = datetime(date.year, date.month, date.day)
        unix_ts = int(start_of_day.timestamp())

        link = self.CALENDAR_URL.format(unix_ts)
        html = self._request(link)
        if html in [self.KEY_ERROR, self.LOGIN_ERROR, self.FETCH_FAIL]:
            return html

        soup = BeautifulSoup(html, "html.parser")
        events = soup.select("div.event, div.calendar_event, div.calendar-event")
        return bool(events)

    def day_lessons(self, date: datetime) -> str:
        start_of_day = datetime(date.year, date.month, date.day)
        unix_ts = int(start_of_day.timestamp())

        html = self._request(self.CALENDAR_URL.format(unix_ts))
        if html in [self.KEY_ERROR, self.LOGIN_ERROR, self.FETCH_FAIL]:
            return html

        soup = BeautifulSoup(html, "html.parser")
        events = soup.select("div.event, div.calendar_event, div.calendar-event")

        if not events:
            return "<i>Немає нічого на цей день.</i>"

        result = []
        for e in events:
            title_tag = e.select_one(".name, .event-title, .calendar-event-title")
            title = title_tag.get_text(strip=True) if title_tag else "Untitled"
            event_html = f"<b>{title}</b>"

            desc_tag = e.select_one(".description, .event-description, .calendar-event-description")
            desc_lines = []
            if desc_tag:
                rows = desc_tag.select(".row")
                for row in rows:
                    span = row.find("span", class_="dimmed_text")
                    if span:
                        a_tag = span.find("a")
                        if a_tag and a_tag.has_attr("href"):
                            href = a_tag['href']
                            full_text = span.get_text(" ", strip=True)
                            text = f"<a href='{href}'>{full_text}</a>"
                        else:
                            text = span.get_text(" ", strip=True)
                    else:
                        a_tag = row.find("a")
                        if a_tag and a_tag.has_attr("href"):
                            text = f"<a href='{a_tag['href']}'>{a_tag.get_text(strip=True)}</a>"
                        else:
                            text = row.get_text(" ", strip=True)
                    if text:
                        desc_lines.append(text)
            desc_html = "\n".join(desc_lines)

            course_tag = e.select_one(".fa-graduation-cap + div a, .fa-graduation-cap + div")
            if course_tag:
                if course_tag.name == "a" and course_tag.has_attr("href"):
                    course_html = f"<a href='{course_tag['href']}'>{course_tag.get_text(strip=True)}</a>"
                else:
                    course_html = f"{course_tag.get_text(strip=True)}"
            else:
                course_html = ""

            group_tag = e.select_one(".fa-group + div")
            group_html = f"{group_tag.get_text(strip=True)}" if group_tag else ""

            link_tag = e.select_one(".card-footer a, .card-link")
            link_html = f"<a href='{link_tag['href']}'>Перейти к елементу курсу</a>" if link_tag and link_tag.has_attr("href") else ""

            parts = [desc_html, course_html, group_html, link_html]
            event_html += "\n" + "\n".join([p for p in parts if p])
            result.append(event_html)

        return "\n\n".join(result)
