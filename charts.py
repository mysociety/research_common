'''
Objects to manage creation of charts and their
translation into images
'''

import base64
import io
import json
import os
import random
import shutil
import string
import tempfile
import time
from collections import OrderedDict
from hashlib import md5

import altair as alt
import pandas as pd
from altair_saver import save
from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template, render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from urllib3.exceptions import MaxRetryError

html_chart_titles = False
org_logo = "/sites/foi-monitor/static/img/mysociety-logo.jpg"
export_images = settings.EXPORT_CHARTS
force_reload = settings.FORCE_EXPORT_CHARTS

media_folder = settings.CHART_FOLDER
csv_folder = settings.CSV_FOLDER
chrome_driver_path = settings.CHROME_DRIVER


def query_to_df(query, values: dict):
    """
    Given a django queryset and a dictionary mapping
    django values to final columns, creates a pandas
    dataframe
    """
    keys = list(values.keys())
    columns = [values[x] for x in values]

    rows = query.values_list(*keys)
    df = pd.DataFrame(list(rows), columns=columns)
    return df


colours = {'colour_orange': '#f79421',
           'colour_off_white': '#f3f1eb',
           'colour_light_grey': '#e2dfd9',
           'colour_mid_grey': '#959287',
           'colour_dark_grey': '#6c6b68',
           'colour_black': '#333333',
           'colour_red': '#dd4e4d',
           'colour_yellow': '#fff066',
           'colour_violet': '#a94ca6',
           'colour_green': '#61b252',
           'colour_green_dark': '#53a044',
           'colour_green_dark_2': '#388924',
           'colour_blue': '#54b1e4',
           'colour_blue_dark': '#2b8cdb',
           'colour_blue_dark_2': '#207cba'}

palette = ["colour_blue_dark_2",
           "colour_red",
           "colour_green",
           "colour_violet"]

palette_colors = [colours[x] for x in palette]

font = "Source Sans Pro"

mysoc_theme = {

    'config': {
        "title": {'font': font,
                  'fontSize': 30,
                  'anchor': "start"
                  },
        'axis': {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            'titleFontSize': 16,
            'domain': False,
            'offset': 10
        },
        'axisX': {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            'titleFontSize': 16,
            'domain': True,
            'grid': True,
            "ticks": False,
            "gridWidth": 0.4,

        },
        'axisY': {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            'titleFontSize': 16,
            'domain': True,
            "ticks": False,
            "titleAngle": 0,  # horizontal
            "titleY": -10,  # move it up
            "titleX": 0,
            "gridWidth": 0.4,
        },
        'view': {
            "stroke": "transparent",
        },
        "line": {
            "strokeWidth": 2,
        },
        'mark': {"shape": "cross"},
        'legend': {
            "orient": 'bottom',
            "labelFont": font,
            "labelFontSize": 12,
            "titleFont": font,
            "titleFontSize": 12,
            "title": "",
            "offset": 18,
            "symbolType": 'square',
        }
    }
}

original_palette = [
    # Start with category10 color cycle:
    "#1f77b4", '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    # Then continue with the paired lighter colors from category20:
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
    '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5']

palette_colors = palette_colors[:1]

new_palette = palette_colors + original_palette[len(palette_colors):]

mysoc_theme.setdefault('encoding', {}).setdefault('color', {})['scale'] = {
    'range': new_palette,
}

# register the custom theme under a chosen name
alt.themes.register('mysoc_theme', lambda: mysoc_theme)
# enable the newly registered theme
alt.themes.enable('mysoc_theme')


def id_generator(size=6, chars=string.ascii_uppercase):
    return ''.join(random.choice(chars) for _ in range(size))


class Chrome(object):
    """
    stores selenium driver to reduce time spent after
    first start up
    """
    driver = None
    render_session = False
    count = 0

    @classmethod
    def get_driver(cls):
        if cls.driver:
            return cls.driver

        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        cls.driver = webdriver.Chrome(executable_path=chrome_driver_path,
                                      chrome_options=options)
        return cls.driver

    @classmethod
    def reset_driver(cls):
        if cls.driver:
            cls.driver.quit()
        cls.render_session = False

    def __del__(self):
        if self.driver:
            self.driver.quit()
        super(Chrome, self).__del__()

    @classmethod
    def start_render_session(cls):
        document = get_template("charts/chart_render.html")
        html_content = document.render()
        html_content = html_content.replace("#", "%23")
        driver = cls.get_driver()
        driver.get("data:text/html;charset=utf-8," + html_content)

        while True:
            state = driver.execute_script("return document.readyState")
            print(state)
            if state == "complete":
                break

        print("render page ready")
        cls.render_session = True

    @classmethod
    def _render_altair(cls, chart):
        if cls.render_session is False:
            cls.start_render_session()
        driver = cls.get_driver()
        loc = chart.image_location
        folder = os.path.dirname(loc)
        if os.path.exists(folder) is False:
            os.makedirs(folder)
        elem = driver.find_element_by_id("chart_standin")
        spec = chart.render_object().to_dict()
        command = "drawChart({spec})".format(spec=str(spec))
        altair_status = driver.execute_script(command)
        canvas = elem.find_element_by_tag_name("canvas")
        canvas_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas)
        encoded = base64.b64decode(bytes(canvas_base64, 'utf-8'))
        with open(loc, "wb") as fh:
            fh.write(encoded)
        return True

    @classmethod
    def render_altair(cls, chart):
        result = None
        # there's a periodic time out error we need to try and catch and avoid
        while not result:
            try:
                result = cls._render_altair(chart)
            except (TimeoutException, MaxRetryError):
                print("Timeout exception, resetting driver and retrying.")
                cls.reset_driver()
                time.sleep(5)


class ChartCollection(object):
    """
    Holds all charts to be rendered on a page

    """

    def __init__(self, slug="", *args):
        self.slug = slug
        self.logo = org_logo
        self.charts = []
        for x in args:
            self.register(x)

    def packages(self):
        packages = [x.package_name for x in self.charts]
        return list(set(packages))

    def charts_to_generate(self, force_static=False):
        """
        get charts that need to be rendered
        """
        for x in self.charts:
            if x.__class__.image_render:
                file_exists = os.path.exists(x.image_location)
                if (file_exists is False or force_static):
                    yield x

    def csvs_to_generate(self, force_static=False):
        """
        get charts that need to be rendered
        """
        for x in self.charts:
            if x.__class__.csv_render:
                file_exists = os.path.exists(x.csv_location)
                if (file_exists is False or force_static):
                    yield x

    def _get_driver(self):
        """
        override to use a different driver
        """
        return Chrome.get_driver()

    def export(self, baking_options):
        skip_charts = baking_options.get("skip_assets", False)
        force_charts = baking_options.get("all_assets", False)

        if export_images is True and skip_charts is False:
            self.export_csvs(force_charts)
            self.export_images(force_charts)

    def export_csvs(self, force_charts):
        for c in self.csvs_to_generate(force_charts):
            c.export_data()

    def export_images(self, force_charts):
        charts = [x for x in self.charts_to_generate(force_charts)
                  if x.package_name == "altair"]
        if len(charts) == 0:
            return None

        print("Exporting {0} images".format(len(charts)))
        for c in charts:
            Chrome.render_altair(c)

    def register(self, chart):
        """
        attaches chart to collection
        """

        if chart._register is None:
            ident = chart.generate_id()
            chart._register = self
            self.charts.append(chart)

    def render_code(self, static=False):
        """
        export the render code for the charts
        """
        rel_charts = self.charts
        good_packages = ["altair", "datatables"]
        rel_charts = [x for x in rel_charts if x.package_name in good_packages]
        if static:
            rel_charts = self.charts_to_generate()

        c = {'collection': self,
             'charts': rel_charts,
             'make_static': static}
        template = get_template("charts//set_code.html")
        return mark_safe(template.render(c))

    def __str__(self):
        return self.render_code()


class BaseChart(object):

    """
    Handles data contained in chart and formats
    for google chart
    """

    code_template = "charts//line_code.html"
    div_template = "charts//div_code.html"
    image_render = True
    csv_render = False
    _register = None

    def __init__(self, name="", file_name=""):
        self.name = name
        self.columns = []
        self.rows = []
        self.ident = "unassigned"
        if file_name:
            self.load_from_file(file_name)
        self.options = {"title": name}
        self.cell_modifications = []
        self.df = None
        self.header = OrderedDict()

    def apply_query(self, query):
        """
        create dataframe from django query
        """
        self.df = query_to_df(query, self.header)
        return self.df

    @property
    def folders(self):
        a = self.ident[0]
        b = self.ident[1]
        return a, b

    @property
    def safe_name_and_ident(self):
        """
        safe reference for file creation
        """
        if self.name:
            return slugify(self.name) + "_" + self.ident
        return self.ident

    @property
    def image_location(self):
        """
        where the static version should be stored
        """
        a, b = self.folders
        return os.path.join(media_folder,
                            self._register.slug,
                            a,
                            b,
                            "{0}.png".format(self.safe_name_and_ident))

    @property
    def csv_location(self):
        """
        where the static version should be stored
        """
        a, b = self.folders
        return os.path.join(csv_folder,
                            self._register.slug,
                            a, b,
                            "{0}.csv".format(self.safe_name_and_ident))

    def generate_id(self):
        """
        produce a hash as id for this table
        will change with contents
        """
        if self.df is None:
            columns = [x.as_dict() for x in self.columns]
            columns = json.dumps(columns)
            rows = json.dumps(self.rows)
            joined = columns + rows
            joined += json.dumps(self.options)
        else:
            if hasattr(self, "render_object"):
                joined = json.dumps(self.render_object().to_dict())
            else:
                joined = self.df.to_json()

        joined += self.name
        by_encoded = joined.encode('utf-8')
        hash = md5(by_encoded).hexdigest()
        self.ident = ""
        for h in hash:
            if h in string.digits:
                self.ident += chr(65 + 8 + int(h))
            else:
                self.ident += h

        self.ident = self.ident[:6]

    def compile_options(self):
        return self.options

    def json_options(self):
        """
        return options to template
        """
        return mark_safe(json.dumps(self.compile_options()))

    @property
    def image_url(self):
        """
        url to where the static image should be
        """
        slug = self._register.slug
        if slug:
            return settings.MEDIA_URL + \
                "charts/{0}/{1}/{2}/".format(slug, *self.folders) + \
                self.safe_name_and_ident + ".png"
        else:
            return settings.MEDIA_URL + \
                "charts/{0}/{1}/".format(*self.folders) + \
                self.safe_name_and_ident + ".png"

    @property
    def csv_url(self):
        """
        url to where the static image should be
        """
        slug = self._register.slug
        if slug:
            return settings.MEDIA_URL + \
                "csvs/{0}/{1}/{2}/".format(slug, *self.folders) + \
                self.safe_name_and_ident + ".csv"
        else:
            return settings.MEDIA_URL + \
                "csvs/{0}/{1}/".format(*self.folders) + \
                self.safe_name_and_ident + ".csv"

    def render_div(self):
        """
        render how the chart will be displayed
        """
        c = {'chart': self}
        template = get_template(self.__class__.div_template)
        return mark_safe(template.render(c))

    def __str__(self):
        return self.render_div()

    def render_code(self, static=False):
        """
        render the code segement for this chart
        """
        c = {'chart': self, 'make_static': static}
        template = get_template(self.__class__.code_template)
        return mark_safe(template.render(c))

    def render_code_static(self):
        """
        render the code so it outputs a static image
        """
        return self.render_code(True)

    def set_options(self, **kwargs):
        self.options.update(kwargs)

    def export_data(self):

        loc = self.csv_location
        folder = os.path.dirname(loc)
        if os.path.exists(folder) is False:
            os.makedirs(folder)
        self.df.to_csv(loc, index=False)


class AltairChart(BaseChart):
    """
    Base for loading, rendering and saving an Altair chart
    """
    package_name = "altair"
    code_template = "charts//altair_code.html"

    def __init__(self, df=None, title=None, footer=None, chart_type="line", interactive=False, ratio=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.footer = footer
        self.link_lookup = {}
        self.df = df
        self.chart_type = chart_type
        self.interactive = interactive
        self.custom_settings = lambda x: x
        self.ratio = ratio
        self.html_chart_titles = html_chart_titles

    def set_options(self, **kwargs):
        self.options.update(kwargs)
        if isinstance(self.options["x"], str):
            self.options["x"] = alt.X(self.options["x"])
        if isinstance(self.options["y"], str):
            self.options["y"] = alt.X(self.options["y"])
        if "tooltip" in self.options and isinstance(self.options["tooltip"], list):
            nl = []
            for t in self.options["tooltip"]:
                if isinstance(t, str):
                    nl.append(alt.Tooltip(t.replace(".", ""), title=t))
                else:
                    t.title = t.shorthand
                    t.shorthand = t.shorthand.replace(".", "")
                    nl.append(t)
            self.options["tooltip"] = nl

    def safe_options(self):
        new_options = dict(self.options)
        banned = ["title"]
        for b in banned:
            if b in new_options:
                del new_options[b]

        for o in ["x", "y"]:
            original = new_options[o].shorthand
            shorthand = new_options[o].shorthand
            if isinstance(shorthand, str) and "." in shorthand:
                shorthand = shorthand.replace(".", "")
                new_options[o].shorthand = shorthand
                new_options[o].title = original

        return new_options

    def y_axis_format(self, *args, **kwargs):
        new_axis = alt.Axis(*args, **kwargs)
        self.options["y"].axis = new_axis

    def x_axis_format(self, *args, **kwargs):
        new_axis = alt.Axis(*args, **kwargs)
        self.options["x"].axis = new_axis

    def fix_df(self):
        """
        generic column fixes
        """
        df = self.df
        new_cols = {x: x.replace(".", "") for x in df.columns}
        ndf = df.rename(columns=new_cols)

        return ndf

    def render_object(self):

        obj = alt.Chart(self.fix_df())
        if self.chart_type == "line":
            obj = obj.mark_line(point={"size":100})
        if self.chart_type == "bar":
            obj = obj.mark_bar()
        if self.chart_type == "step":
            obj = obj.mark_line(interpolate='step-after', point=True)
        obj = obj.encode(**self.safe_options())
        if self.interactive:
            obj = obj.interactive()

        properties = {"width": "container"}

        if self.ratio:
            properties["height"] = "container"

        if self.title and self.html_chart_titles is False:
            properties["title"] = self.title

        obj = obj.properties(**properties)

        if self.footer:
            obj = obj.properties(title=alt.TitleParams(self.footer,
                                                       baseline='bottom',
                                                       orient='bottom',
                                                       anchor='end',
                                                       fontWeight='normal',
                                                       fontSize=10
                                                       ))

        obj = self.custom_settings(obj)

        return obj


class Table(BaseChart):
    """
    Rather than rendering an image, this outputs
    an html table
    """
    package_name = "datatables"
    code_template = "charts//table_code.html"
    div_template = "charts//div_code_table.html"
    html_table_template = "charts//html_table.html"
    image_render = False
    csv_render = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format_transformation = {}
        self.format_on_row = {}
        self.format = self.format_transformation
        self.style = {}
        self.style_on_row = {}
        if self.df is None:
            self.df = pd.DataFrame()

    def format_cell(self, column, row, value):
        """
        create a human readable format for the cell
        """
        transform = self.format_on_row.get(column, None)
        if transform:
            return transform(row)
        if transform is None:
            transform = self.format_transformation.get(column, lambda x: x)
            return transform(value)

    def style_cell(self, column, row, value):
        """
        apply a style to the cell
        """
        transform = self.style_on_row.get(column, None)
        if transform:
            return transform(row)
        if transform is None:
            transform = self.style.get(column, None)
            if transform:
                return transform(value)

    def render_html_table(self):
        """
        makes a boring html table
        """
        table_rows = []
        for index, r in self.df.iterrows():
            row = []
            for c in self.df.columns:
                value = r[c]
                formatted_value = self.format_cell(c, r, value)
                style = self.style_cell(c, r, value)
                combo = {"f": formatted_value, "v": value, "s": style}
                row.append(combo)
            table_rows.append(row)

        c = {'table': self, 'rows': table_rows}
        template = get_template(self.__class__.html_table_template)

        return mark_safe(template.render(c))
