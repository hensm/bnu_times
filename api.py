import re
import requests
import sys
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
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
    staff: List[str]

@dataclass
class Timetable:
    student_id: str
    student_name: str
    student_course: str
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

    re_student_id = re.compile(r"^\d{8}$")
    if not re_student_id.match(student_id):
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
    # HTML tables containing the events Mon-Sun, all with the
    # same column info, so collect all the data into dataclasses
    # for export.
    timetable_soup = BeautifulSoup(res_timetable.content, "html.parser")
    timetable_data_days = []

    header_student_name = timetable_soup.select_one(".header-0-0-0")
    header_student_course = timetable_soup.select_one(".header-0-0-2")
    header_time = timetable_soup.select_one(".header-1-2-3")

    (week_start, week_end) = map(
            lambda x: datetime.strptime(x, "%d %b %Y"),
            header_time.text.split("-"))

    for day_index, sheet in enumerate(timetable_soup.select(".spreadsheet")):
        time_day = week_start + timedelta(days=day_index)

        def parse_event_time(time_string: str):
            return datetime.combine(
                    time_day,
                    datetime.strptime(time_string, "%H:%M").time())

        sheet_data = []
        for row in sheet.select("tr:not(.columnTitles)"):
            # idx  column      description
            # -------------------------------------------------------
            # 0    name        Session name
            # 1    desc        Short session description
            # 2    type        Type of session
            # 3    module      Module string
            # 4    time_start  DateTime string for start of session
            # 5    time_end    DateTime string for end of session
            # 6    weeks       List of applicable week ranges
            # 7    room        Room string
            # 8    staff       List of assigned staff

            cols = [ col.text for col in row.find_all("td") ]

            def split_strip(col: str, sep=","):
                return [ x.strip() for x in col.split(sep)]

            # Cleanup data
            cols[4] = parse_event_time(cols[4])
            cols[5] = parse_event_time(cols[5])
            cols[6] = split_strip(cols[6])
            cols[8] = split_strip(cols[8])

            sheet_data.append(TimetableEntry(*cols))

        timetable_data_days.append(sheet_data)

    return Timetable(
            student_id=student_id,
            student_name=header_student_name.text,
            student_course=header_student_course.text,
            days=timetable_data_days)
