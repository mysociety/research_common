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
from urllib.parse import urlencode

import altair as alt
from altair.utils.schemapi import UndefinedType
import numpy as np
import pandas as pd
from altair_saver import save
from cryptography.fernet import Fernet
from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template, render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from urllib3.exceptions import MaxRetryError

# load theme
import research_common.altair_theme as theme

# register the custom theme under a chosen name
alt.themes.register('mysoc_theme', lambda: theme.mysoc_theme)
# enable the newly registered theme
alt.themes.enable('mysoc_theme')


html_chart_titles = False
org_logo = settings.ORG_LOGO
export_images = settings.EXPORT_CHARTS
export_csvs = settings.EXPORT_CSVS
force_reload = settings.FORCE_EXPORT_CHARTS

media_folder = settings.CHART_FOLDER
csv_folder = settings.CSV_FOLDER
chrome_driver_path = settings.CHROME_DRIVER


def group_to_other(df, values_col, years_col, labels_col,
                   cut_off=2, agg_func="sum", other_label="Other"):
    """
    Group to get lowest values into an 'Other' category
    """
    pt = df.pivot_table(values_col, labels_col)
    values = pt[values_col]
    if len(values.unique()) <= cut_off:
        return df
    top_sectors = values.sort_values(ascending=False)[:cut_off].index

    df["grouped_labels"] = df[labels_col]
    df.loc[~df[labels_col].isin(
        top_sectors), "grouped_labels"] = other_label

    gb = df.groupby(["grouped_labels", years_col]).agg(
        {values_col: agg_func}).reset_index()
    gb.columns = [labels_col, years_col, values_col]
    return gb


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
    reset_count = 100

    @classmethod
    def get_driver(cls):
        if cls.driver:
            return cls.driver

        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_argument("--no-sandbox")
        cls.driver = webdriver.Chrome(executable_path=chrome_driver_path,
                                      chrome_options=options)
        return cls.driver

    @classmethod
    def reset_driver(cls):
        if cls.driver:
            cls.driver.quit()
            cls.driver = None
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
        spec = chart.json()
        command = "drawChart({spec})".format(spec=str(spec))
        altair_status = driver.execute_script(command)
        canvas = elem.find_element_by_tag_name("canvas")
        canvas_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas)
        encoded = base64.b64decode(bytes(canvas_base64, 'utf-8'))
        print(loc)
        with open(loc, "wb") as fh:
            fh.write(encoded)
        return True

    @classmethod
    def render_altair(cls, chart):
        result = None
        # there's a periodic time out error we need to try and catch and avoid
        while not result:
            if cls.count >= cls.reset_count:
                cls.count = 0
                cls.reset_driver()
                time.sleep(5)
            try:
                result = cls._render_altair(chart)
                cls.count += 1
            except (TimeoutException, MaxRetryError):
                print("Timeout exception, resetting driver and retrying.")
                cls.count = 0
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
            self.export_images(force_charts)
        if export_csvs is True and skip_charts is False:
            self.export_csvs(force_charts)

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
        self.text_options = {}
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

    def set_text_options(self, **kwargs):
        self.text_options.update(kwargs)

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

    def __init__(self,
                 df=None,
                 title=None,
                 footer=None,
                 chart_type="line",
                 interactive=False,
                 ratio=None,
                 default_width="container",
                 facet_width=None,
                 use_render_site=None,
                 *args, **kwargs):

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
        self.default_width = default_width
        self.facet_width = facet_width
        self._json = ""
        self.data_source = ""

        self.use_render_site = use_render_site
        if self.use_render_site is None:
            self.use_render_site = False
        if settings.VEGALITE_USE_SERVER:
            self.use_render_site = True
        if not settings.VEGALITE_SERVER_URL:
            self.use_render_site = False

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

    @property
    def image_url(self):
        if self.use_render_site:
            return self.server_based_render_url()
        else:
            return self.rendered_image_url()

    def rendered_image_url(self):
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

    def server_based_render_url(self):
        """
        get url for server image
        """
        root_url = "{0}/convert_spec".format(settings.VEGALITE_SERVER_URL)
        spec = self.json()
        encrypt = False
        if settings.VEGALITE_ENCRYPT_KEY:
            key = settings.VEGALITE_ENCRYPT_KEY.encode()
            spec = Fernet(key).encrypt(spec.encode())
            encrypt = True

        parameters = urlencode({"spec": spec,
                                "format": "png",
                                "encrypted": encrypt,
                                "width": 700})
        return root_url + "?" + parameters

    def json(self, refresh=False):
        """
        render and cache json for charts
        """

        if self._json and refresh is False:
            return self._json

        di = self.render_object().to_dict()

        if di['config']['legend']['title'] == "":
            di['config']['legend']['title'] = None

        self._json = json.dumps(di)
        return self._json

    def accessible_title(self):
        title = self.title
        if isinstance(title, alt.TitleParams):
            return title.text
        else:
            return title

    def accessible_subtitle(self):
        if isinstance(self.title, alt.TitleParams):
            if hasattr(self.title, "subtitle"):
                return self.title.subtitle
        return []

    def accessible_df(self):
        """
        Make a table that can be put into a longdesc
        that is semi helpful for screen readers
        """
        df = self.fix_df()

        used_columns = []

        def get_field(o):
            results = []
            if isinstance(o, str):
                results.append(o)
            if isinstance(o, list):
                for tooltip in o:
                    results.extend(get_field(tooltip))
            if hasattr(o, "shorthand"):
                results.append(o.shorthand)
            if hasattr(o, "field"):
                results.append(o.field)
            return results

        # make sure we're only carrying columns that are used by the dataframe
        for o in self.options.values():
            used_columns.extend(get_field(o))

        valid_cols = [x for x in df.columns.values if x in used_columns]
        df = df.loc[:, valid_cols].copy()

        def clickable_link(url):
            template = '<a href="{0}">{0}</a>'
            return mark_safe(template.format(url))

        # slightly more readable colours
        if "style" in df.columns:
            df["style"] = df["style"].map(theme.colour_lookup)
            df["style"] = df["style"].str.replace("colour_", "")
            df["style"] = df["style"].str.replace("_", " ")
        txt = df.to_html(index=False)

        # clickable links if there are urls
        if "url" in df.columns:
            for x, item in df["url"].iteritems():
                txt = txt.replace(item, clickable_link(item))

        return txt

    def render_object(self):
        df = self.fix_df()
        obj = alt.Chart(df)
        if self.chart_type == "line":
            obj = obj.mark_line(point={"size": 100})
        if self.chart_type == "bar":
            obj = obj.mark_bar()
        if self.chart_type == "step":
            obj = obj.mark_line(interpolate='step-after', point=True)
        options = self.safe_options()
        x_axis = options['x']
        y_axis = options['y']

        # hack to push the y-axis to the rough position of the left most label
        # on the y axis
        axis_name = ""
        if not isinstance(y_axis.shorthand, UndefinedType):
            axis_name = y_axis.shorthand
        if not isinstance(y_axis.field, UndefinedType):
            axis_name = y_axis.field
        if isinstance(y_axis.axis, UndefinedType):
            y_axis.axis = alt.Axis()
        # if any kind of formatting of number, assume the default is fine
        if isinstance(y_axis.axis.format, UndefinedType):
            format_str = ""
        else:
            format_str = y_axis.axis.format      
        if axis_name and not format_str:
            col = df[axis_name]
            try:
                col = col.astype(int)
            except ValueError:
                pass
            max_len = col.astype(str).str.len().max()
            if max_len > 5:
                y_axis.axis.titleX = 0 - (int(max_len * 6.5) + 10)

        # add spacing to x axis to match ggplot approach
        values = None
        try:
            values = x_axis["axis"]["values"]
        except Exception:
            pass
        if isinstance(values, pd.Series) is False:
            values = None
            try:
                values = df[x_axis.shorthand]
            except Exception as e:
                pass

        if values is not None and values.dtype in [np.int64, np.int32]:
            maxv = values.max() + 0.5
            minv = values.min() - 0.5
            options["x"].scale = alt.Scale(domain=[minv, maxv])
        obj = obj.encode(**options)
        if self.interactive:
            obj = obj.interactive()

        # process any label functions
        if self.text_options:
            text_opts = dict(self.text_options)
            text_option = text_opts["text"]
            del text_opts["text"]
            text_obj = obj.mark_text(**text_opts)
            text_obj = text_obj.encode(text=text_option)
            obj = (obj + text_obj)

        properties = {}

        if self.default_width:
            properties["width"] = self.default_width

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
