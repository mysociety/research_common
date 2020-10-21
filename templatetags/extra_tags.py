from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

register = template.Library()

val = URLValidator()


@register.filter
def last_two(value):
    try:
        return str(value)[2:]
    except (ValueError, ZeroDivisionError):
        return None


@register.filter
def readable_p(value):
    if value > 0.01:
        return round(value, 2)
    if value < 0.00001:
        return "<0.00001"
    if value < 0.0001:
        return "<0.0001"
    if value < 0.001:
        return "<0.001"
    if value < 0.01:
        return "<0.01"


@register.filter
def divide(value, arg):
    try:
        return int(value) / int(arg)
    except (ValueError, ZeroDivisionError):
        return None


def get_first_url(url):
    """
    some urls have been joined by the system, this 
    gets the first one back
    """
    poss_sep = [" : ", " "]
    if url:
        if "http" in url and is_valid_url(url) == False:
            for s in poss_sep:
                if s in url:
                    return url.split(s)[0]

    return url


def is_valid_url(url):

    if url[0] == "/":
        test_url = "http://127.0.0.1/{0}".format(url)
    else:
        test_url = url

    try:
        val(test_url)
        return True
    except ValidationError:
        return False


@register.filter
def yes_no(v):
    """
    boolean to Yes/No
    """
    if v:
        return "Yes"
    elif v == False:
        return "No"
    else:
        return "N/A"


@register.filter
def nice_email(v):
    return v.replace("@", " (at) ")


@register.filter
def as_percentage_of(part, whole):
    try:
        return "%d%%" % (float(part) / whole * 100)
    except (ValueError, ZeroDivisionError):
        return ""


def comma(value): return "{:,}".format(value)


@register.filter("round")
def roundf(item):
    if type(item) not in [int, float]:
        if item == None:
            return "-"
        else:
            return item
    else:
        v = round(item, 2)
        if v % 1 == 0:
            v = int(v)
        return comma(v)


@register.filter
def positive(item):
    if item < 0:
        return 0 - item
    else:
        return item


@register.filter
def none_tidy(item):
    if item == None:
        return "-"
    else:
        return item


@register.filter
def nice_decile(item):
    if item <= 5:
        value = item + 1
        return "top {0}0%".format(value)
    else:
        value = 11-item
        return "bottom {0}0%".format(value)


@register.filter
def zero_if_none(item):
    if item == None:
        return 0
    else:
        return item


@register.filter
def add_comment(reference, report):
    if reference:
        return report.cm.add_comment(reference)
    else:
        return ""


@register.filter
def strip(v):
    if v:
        return v.strip()
    else:
        return ""


@register.filter("url")
def url(item, url):
    """
    return link
    """
    url = get_first_url(url)

    item = escape(item)

    if url:

        if url[:3] == "www":
            url = "http://" + url

        if is_valid_url(url):
            form = '<a href="{1}">{0}</a>'
        else:
            form = '{0} ({1})'
        return mark_safe(form.format(item, url))
    else:
        return item


@register.filter("int")
def e_int(obj):
    """
    return comma seperated integer from float
    """
    if obj == "":
        obj = 0
    num = int(obj)
    return"{:,}".format(num)


@register.filter
def sub(obj, object2):
    """
    basic substitution
    """
    return obj-object2


@register.filter
def percent(obj, object2):
    """
    return percentage of 1 of 2
    """
    if object2:
        return int(float(int(obj))/object2*100)
    else:
        return 0


@register.filter
def no_float_zeros(v):
    """
    if a float that is equiv to integer - return int instead
    """
    if v % 1 == 0:
        return int(v)
    else:
        return v


@register.filter
def evenchunks(l, n):
    """
    return a list in two even junks
    """
    if type(l) != list:
        l = list(l)

    import math
    n = int(math.floor(len(l)/float(n))) + 10
    print(len(l))
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


@register.filter
def intdistance(d):
    if d == "":
        d = 0
    if d < 1:
        return "{0} m".format(int(d*1000))
    else:
        return "{0} km".format(int(d))


@register.filter
def yield2(l):
    """
    return a list in two even junks
    """

    l = list(l)

    for x in range(0, len(l), 2):
        try:
            yield [l[x], l[x+1]]
        except IndexError:
            yield [l[x], None]


@register.filter
def evenquerychunks(l, n):
    """
    return a list in two even junks
    """

    l = list(l)

    import math
    n = int(math.floor(len(l)/float(n))) + 1
    print(len(l))
    """Yield successive n-sized chunks from l."""
    results = []
    for i in range(0, len(l), n):
        results.append(l[i:i+n])

    return results


@register.filter
def chunks(l, n):
    """
    returns a list in set n
    """
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


@register.filter
def first3(ls):
    return ls[:4]


@register.filter
def threeremainder(l, n):
    ll = l[4:]
    for i in range(0, len(ll), n):
        yield ll[i:i+n]


@register.filter
def clip(st, length):
    """
    will clip down a string to the length specified
    """
    if len(st) > length:
        return st[:length] + "..."
    else:
        return st


@register.filter
def limit(st, length):
    """
    same as clip - but doesn't add ellipses
    """
    return st[:length]


@register.filter
def five(ls):
    """
    returns first five of list
    """
    return ls[:5]


@register.filter
def human_travel(hours):
    """
    given decimal hours - names it look nice in human
    """
    import math

    m = int((hours % 1) * 60)
    h = int(math.floor(hours))
    if h > 24:
        d = int(math.floor(h/24))
        h = h % 24
    else:
        d = 0

    st = ""

    if d:
        st += "{0} Day".format(d)
        if d > 1:
            st += "s"
    if h:
        st += " {0} Hour".format(h)
        if h > 1:
            st += "s"
    if m and not d:
        st += " {0} Minute".format(m)
        if m > 1:
            st += "s"
    st = st.strip()
    return st
