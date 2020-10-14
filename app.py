import api
import datetime
from dataclasses import asdict
from flask import Flask, request, abort, render_template


app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/timetable")
def timetable():
    param_student_id = request.args.get("student_id", type=str)
    param_week = request.args.get("week", type=str)

    if not param_student_id:
        abort(400)
    
    week = api.Week(param_week) if param_week else api.Week.Current

    timetable = api.get_timetable(param_student_id, week)
    if timetable is None:
        abort(400)
    
    def make_ordinal(n):
        rem = n % 100
        suffixes = ["th", "st", "nd", "rd", "th"]
        return suffixes[0] if 10 <= rem <= 20 else suffixes[min(rem % 10, 4)]
    
    data_days = []
    for i, day in enumerate(timetable.days):
        date = timetable.date_start + datetime.timedelta(days=i)
        data_days.append({
            "name": date.strftime("%A"),
            "date": date.strftime(f"{date.day}{make_ordinal(date.day)} %B"),
            "entries": day
        })

    return render_template(
        "timetable.html",
        student_id=timetable.student_id,
        student_name=timetable.student_name,
        days=data_days)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/api/timetable/<student_id>")
def api_timetable(student_id):
    timetable = api.get_timetable(student_id, api.Week.Current)
    if timetable is None:
        abort(400)

    return asdict(timetable)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
