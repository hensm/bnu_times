import re
import requests
import sys
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from flask import Flask, abort, render_template
from typing import Dict, List, Union


TIMETABLE_URL = "https://mytimetable.bucks.ac.uk"

@dataclass
class TimetableEntry:
    name: str
    desc: str
    type: str
    module: str
    time_start: datetime
    time_end: datetime
    weeks: str
    room: str
    staff: str

@dataclass
class Timetable:
    days: List[List[TimetableEntry]]


def get_form_fields(content: bytes):
    """
    Gets first form field values from HTML content.
    """

    soup = BeautifulSoup(content, "html.parser")
    fields: Dict[str, Union[str, List[str]]] = {}

    form = soup.find("form")

    for input in form.find_all("input"):
        if not (input.has_attr("name") and input.has_attr("value")):
            continue

        if input["type"] in ("text", "hidden", "submit"):
            fields[input["name"]] = input["value"]

    for select in soup.find_all("select"):
        opts = select.find_all("option")
        fields[select["name"]] = [
            opt["value"] for opt in opts if opt.has_attr("selected")
        ]
    
    return fields


session: requests.Session = None
session_res: requests.Response = None

def ensure_valid_session_state():
    """
    Makes a request to the timetable site index for session
    cookies/data. Follows a 302 redirect to the timetable index,
    submits an ASP form to switch to the student timetables
    section for subsequent requests.
    """

    global session
    global session_res

    # Only once
    if session is not None:
        return

    session = requests.Session()
    initial_res = session.get(TIMETABLE_URL)

    # Get ASP form data from initial page and switch to student
    # timetables section.
    session_res = session.post(initial_res.url, data=dict(
        get_form_fields(initial_res.content),
        **{
            "__EVENTTARGET": "LinkBtn_studentsbytext",
            "tLinkType": "information"
        }))


def get_timetable(student_id: str) -> Timetable:
    """
    Makes a request for the timetable with a given student ID.
    """

    student_id_pattern = re.compile(r"^\d{8}$")
    if not student_id_pattern.match(student_id):
        print("invalid id %s" % student_id, file=sys.stderr)
        return None

    ensure_valid_session_state()

    # Make request for individual timetable
    res_timetable = session.post(session_res.url, data=dict(
        get_form_fields(session_res.content),
        **{
            "__EVENTTARGET": "tObjectInput",
            "tObjectInput": student_id,
            "lbWeeks": "t",
            "lbDays": "1-7",
            "dlType": "TextSpreadsheet;swsurl;SWSNET Student TextSpreadsheet"
        }))

    # The list timetable provides a week-by-week view with 7
    # HTML tables containing the events Mon-Fri, all with the
    # same column info, so collect all the data into dataclasses
    # for export.
    timetable_soup = BeautifulSoup(res_timetable.content, "html.parser")
    timetable_data_days = []

    time_header = timetable_soup.select_one(".header-1-2-3")
    (week_start, week_end) = map(
            lambda x: datetime.strptime(x, "%d %b %Y"),
            time_header.text.split("-"))
    
    print(week_start, week_end)

    for day_index, sheet in enumerate(timetable_soup.select(".spreadsheet")):
        time_day = week_start + timedelta(days=day_index)

        def parse_event_time(time_string: str):
            return datetime.combine(
                    time_day,
                    datetime.strptime(time_string, "%H:%M").time())

        sheet_data = []
        for row in sheet.select("tr:not(.columnTitles)"):
            cols = [ col.text for col in row.find_all("td") ]
            cols[4] = parse_event_time(cols[4])
            cols[5] = parse_event_time(cols[5])

            sheet_data.append(TimetableEntry(*cols))

        timetable_data_days.append(sheet_data)

    return Timetable(days=timetable_data_days)



app = Flask(__name__)

@app.route("/")
def index():
    return render_template("./index.html")

@app.route("/timetable/<student_id>")
def timetable(student_id):
    timetable = get_timetable(student_id)
    if timetable is None:
        abort(400)
    
    return asdict(timetable)


if __name__ == "__main__":
    app.run(debug=True)
