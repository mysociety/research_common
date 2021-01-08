"""
mySociety colours and themes for altair
just needs to be imported before rendering charts
Mirrors ggplot theme
"""

import altair as alt

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
            'offset': 0
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
            'labelPadding': 10,

        },
        'axisY': {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            'titleFontSize': 16,
            'labelPadding': 10,
            'domain': True,
            "ticks": False,
            "titleAngle": 0,
            "titleY": -10,
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
