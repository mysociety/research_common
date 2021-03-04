"""
mySociety colours and themes for altair
just needs to be imported before rendering charts
Mirrors ggplot theme
"""

import altair as alt

# brand colours
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

# based on data visualisation colour palette
adjusted_colours = {"colour_yellow": "#ffe269",
                    "colour_orange": "#f4a140",
                    "colour_berry": "#e02653",
                    "colour_purple": "#a94ca6",
                    "colour_blue": "#4faded",
                    "colour_dark_blue": "#0a4166"}

monochrome_colours = {"colour_blue_light_20": "#acd8f6",
                      "colour_blue": "#4faded",
                      "colour_blue_dark_20": "#147cc2",
                      "colour_blue_dark_30": "#0f5e94",
                      "colour_blue_dark_40": "#0a4166",
                      "colour_blue_dark_50": "#062337",
                      }

palette = ["colour_dark_blue",
           "colour_berry",
           "colour_orange",
           "colour_blue",
           "colour_purple",
           "colour_yellow"]

monochrome_palette = ["colour_blue_light_20",
                      "colour_blue",
                      "colour_blue_dark_20",
                      "colour_blue_dark_30",
                      "colour_blue_dark_40",
                      "colour_blue_dark_50",
                      ]

palette_colors = [adjusted_colours[x] for x in palette]

monochrome_palette_colors = [monochrome_colours[x] for x in monochrome_palette]

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
            "titleAlign": "left",
            'labelPadding': 10,
            'domain': True,
            "ticks": False,
            "titleAngle": 0,
            "titleY": -10,
            "titleX": -50,
            "gridWidth": 0.4,
        },
        'view': {
            "stroke": "transparent",
        },
        "line": {
            "strokeWidth": 3,
        },
        "bar":{"color": palette_colors[0]},
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

#set default has colours
original_palette = [
    # Start with category10 color cycle:
    "#1f77b4", '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    # Then continue with the paired lighter colors from category20:
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
    '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5']

# use new palette for as long as possible
new_palette = palette_colors + original_palette[len(palette_colors):]

mysoc_theme.setdefault('encoding', {}).setdefault('color', {})['scale'] = {
    'range': new_palette,
}

# register the custom theme under a chosen name
alt.themes.register('mysoc_theme', lambda: mysoc_theme)
# enable the newly registered theme
alt.themes.enable('mysoc_theme')
