import urllib.request
import csv
from io import StringIO
import string
import ssl

class scheduleCore:
    def __init__(self, sheet_url):
        self.link = sheet_url
        self.data = {}

    def raw(self):
        self.__ensure_loaded()
        return self.data

    def __load(self):
        if not self.link:
            raise ValueError("No sheet URL provided")
        
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(self.link, context=context) as response:
            csv_text = response.read().decode('utf-8')
        
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        if not rows:
            return
        
        for r_idx, row in enumerate(rows, start=1):
            self.data[r_idx] = row

    def __ensure_loaded(self):
        if not self.data:
            self.__load()

    def maplike(self):
        self.__ensure_loaded()
        flat_map = {}
        for r_idx, row in self.data.items():
            for c_idx, value in enumerate(row):
                col_letters = ''
                n = c_idx + 1
                while n > 0:
                    n, rem = divmod(n-1, 26)
                    col_letters = chr(65 + rem) + col_letters
                key = f"{col_letters}{r_idx}"
                flat_map[key] = value
        return flat_map