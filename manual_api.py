import datetime
import json
import logging
import re
from time import sleep

import icalendar
import pytz
import hashlib

logging.basicConfig()  # init a basic output in terminal

CLASS_LENGTH = datetime.timedelta(minutes=45)

CLASS = {
    0: datetime.timedelta(hours=8, minutes=30),
    1: datetime.timedelta(hours=9, minutes=20),
    2: datetime.timedelta(hours=10, minutes=20),
    3: datetime.timedelta(hours=11, minutes=10),
    4: datetime.timedelta(hours=14, minutes=30),
    5: datetime.timedelta(hours=15, minutes=20),
    6: datetime.timedelta(hours=16, minutes=20),
    7: datetime.timedelta(hours=17, minutes=10),
    8: datetime.timedelta(hours=19, minutes=30),
    9: datetime.timedelta(hours=20, minutes=20),
    10: datetime.timedelta(hours=21, minutes=10),
    11: datetime.timedelta(hours=22, minutes=0)
}


def md5(s):
    return hashlib.md5(s.encode('UTF')).hexdigest()


class APIError(Exception):
    pass


def lazyJsonParse(j):
    '''
    this function is copied from stackoverflow
    '''
    j = re.sub(r"{\s*'?(\w)", r'{"\1', j)
    j = re.sub(r",\s*'?(\w)", r',"\1', j)
    j = re.sub(r"(\w)'?\s*:", r'\1":', j)
    j = re.sub(r":\s*'(\w+)'\s*([,}])", r':"\1"\2', j)
    return json.loads(j)


class Course():

    def __init__(self, data):
        self.id = data[2]
        self.name = data[3]
        self.teacherId = data[0]
        self.teacher = data[1]
        self.time = []

    def __repr__(self):
        return repr({
            "id": self.id,
            "name": self.name,
            "teacherId": self.teacherId,
            "teacher": self.teacher,
            "time": self.time
        })

    def __str__(self):
        return "{} - {}: {}".format(self.teacher, self.name, self.time)


def phrase_sem(raw_html):
    def parseCourse(text):
        temp = json.loads('[' + re.search(r"(?<=TaskActivity\().+?(?=\);)", text).group() + "]")
        basicData = Course(temp)
        for i in re.findall(r'(\d+)(\*unitCount\+)(\d+);', text):
            basicData.time.append(
                {"weekday": int(i[0]), "time": [int(i[2])], "week": temp[-1], "location": temp[5]})
        return basicData

    source = raw_html
    # Strip the html code and get the js code
    courses = [parseCourse(i[0]) for i in
               re.findall(r'(activity\s=\s.*(\s+\bindex[\s\S]*?activity;)+)', source)]
    # merge the same course
    _courses = {}
    for i in courses:
        if i.id in _courses:
            _courses[i.id].time.extend(i.time)
        else:
            _courses[i.id] = i
    # merge the sibling course
    course = _courses.values()
    for i in course:
        time, i.time = i.time, []
        time.sort(key=lambda x: (x['weekday'], x['time'][0]))
        i.time.append(time[0])
        for t in time[1:]:
            ft = i.time[-1]
            if abs(t['time'][0] - ft['time'][-1]) == 1 and t['weekday'] == ft['weekday']:
                ft['time'].append(t['time'][0])
            else:
                i.time.append(t)

    return list(_courses.values())


def genTable(courses, the_first_day, name='我'):
    """
    the first day means the first monday of the first week.
    """
    table = icalendar.Calendar()
    table.add('PRODID', '-//Sync Course//course.pandada8.me//')
    table.add('version', '2.0')
    table.add('X-WR-CALNAME', '{}的课表'.format(name))
    table.add('X-WR-CALDESC', '{}的课表，由Sync生成'.format(name))
    table.add('X-WR-TIMEZONE', "Asia/Shanghai")
    table.add('CALSCALE', 'GREGORIAN')
    table.add('METHOD', 'PUBLISH')

    tz = pytz.timezone('Asia/Shanghai')
    _now = datetime.datetime.now()
    now = tz.localize(_now)
    for i in courses:
        for t in i.time:
            for n, w in enumerate(t['week'][1:]):
                if int(w):
                    targetTime = datetime.timedelta(days=7 * n + t['weekday']) + the_first_day + CLASS[
                        min(t['time'])]
                    targetEndTime = datetime.timedelta(days=7 * n + t['weekday'], minutes=45) + the_first_day + \
                                    CLASS[max(t['time'])]
                    e = icalendar.Event()
                    e.add('dtstart', tz.localize(targetTime))
                    e.add('dtend', tz.localize(targetEndTime))
                    e['summary'] = "{} {} {}".format(i.name.split('(')[0],
                                                     i.teacher + "老师" if i.teacher else "", t['location'])
                    e['location'] = icalendar.vText(t['location'])
                    # e['SEQUENCE'] = 1
                    e['TRANSP'] = icalendar.vText('OPAQUE')
                    e['status'] = 'confirmed'
                    e.add('created', now)
                    e.add('DTSTAMP', _now)
                    e["UID"] = '{}@sync.pandada8.me'.format(md5(str(targetTime) + i.name))
                    e.add('LAST-MODIFIED', _now)

                    table.add_component(e)
    return table


def manual():
    try:
        with open('raw.html', 'r') as inf:
            raw_html = inf.read()
    except OSError as e:
        print(e)
        print("请在课表页面使用`审核元素`（不能用`查看源码`），复制完整的raw html保存到此目录下的 `raw.html` ")

    courses = phrase_sem(str(raw_html))

    day = input('请输入开学第一周中某一天工作日(YYYY/MM/DD)：')
    day = datetime.datetime.strptime(day, "%Y/%m/%d")
    day = day - datetime.timedelta(days=day.weekday())

    with open('我的课表' + '.ics', 'wb') as fp:
        fp.write(genTable(courses, day).to_ical())
    print('成功导出！')


if __name__ == "__main__":
    manual()
