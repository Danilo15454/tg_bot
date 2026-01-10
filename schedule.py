import urllib.request
import csv
from io import StringIO
import string
import ssl

class scheduleCore:
    def __init__(self, sheet_url):
        self.link = sheet_url
        self.data = {}
        self.headers = []

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
        
        self.headers = rows[0]
        for r_idx, row in enumerate(rows[1:], start=1):
            self.data[r_idx] = {}
            for c_idx, value in enumerate(row):
                col_name = self.headers[c_idx]
                self.data[r_idx][col_name] = value

    def __ensure_loaded(self):
        if not self.data:
            self.__load()

    def get_data(self):
        self.__ensure_loaded()
        return self.data

    def getRow(self, n):
        self.__ensure_loaded()
        return self.data.get(n, None)

    def getCell(self, coord):
        self.__ensure_loaded()
        coord = coord.upper().strip()
        if len(coord) < 2:
            return None
        
        col_letters = ''.join([c for c in coord if c in string.ascii_uppercase])
        row_numbers = ''.join([c for c in coord if c.isdigit()])
        if not col_letters or not row_numbers:
            return None

        row_index = int(row_numbers)

        col_index = 0
        for i, char in enumerate(reversed(col_letters)):
            col_index += (string.ascii_uppercase.index(char) + 1) * (26**i)
        col_index -= 1

        if col_index >= len(self.headers):
            return None
        col_name = self.headers[col_index]

        row = self.data.get(row_index, None)
        if row is None:
            return None
        return row.get(col_name, None)
    
    def maplike(self):
        self.__ensure_loaded()
        flat_map = {}
        for r_idx, row in self.data.items():
            for c_idx, col_name in enumerate(self.headers):

                col_letters = ''
                n = c_idx + 1
                while n > 0:
                    n, rem = divmod(n-1, 26)
                    col_letters = chr(65 + rem) + col_letters
                key = f"{col_letters}{r_idx}"
                flat_map[key] = row.get(col_name, "")
        return flat_map