import api
import calendar
import datetime
import json
from dataclasses import asdict
from flask import Flask, request, abort, render_template

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/timetable")
def timetable():
    student_id = request.args.get("student_id", type=str)
    timetable = api.get_timetable(student_id)
    if timetable is None:
        abort(400)
    
    data_days = []
    for i, day in enumerate(timetable.days):
        data_days.append({
            "name": calendar.day_name[i],
            "entries": day
        })
    
    return render_template("timetable.html",
            student_id=timetable.student_id,
            student_name=timetable.student_name,
            days=data_days)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/api/timetable/<student_id>")
def api_timetable(student_id):
    timetable = api.get_timetable(student_id)
    if timetable is None:
        abort(400)

    return asdict(timetable)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
