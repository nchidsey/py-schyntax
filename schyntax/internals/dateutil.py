import calendar


def get_days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def get_days_in_previous_month(year, month):
    month -= 1
    if month == 0:
        year -= 1
        month = 12
    return get_days_in_month(year, month)
