from __future__ import absolute_import
from builtins import zip
import jinja2
import json
import folium
from matplotlib import pyplot as plt, colors
import os
from . import ops
import pandas as pd
import numpy as np
import sys


# CONSTANTS
TMS_104001002E6A7E00 = 'https://s3.amazonaws.com/notebooks-small-tms/104001002E6A7E00/{z}/{x}/{y}.png'
COLORS = {'gray'       : '#8F8E8E',
          'white'      : '#FFFFFF',
          'brightgreen': '#00FF17',
          'red'        : '#FF0000',
          'cyan'       : '#1FFCFF',
          'yellow'     : '#FCFE1A',
          'pink'       : '#F30EFE'}

TABLE_CSS = """<style>
.dataframe .ps__rail-y {
  width: 9px;
  background-color: transparent;
  opacity: 1 !important;
  right: 5px;
}
.dataframe .ps__rail-y::before {
  content: "";
  display: block;
  position: absolute;
  background-color: #ebebeb;
  border-radius: 5px;
  width: 100%;
  height: calc(100% - 30px);
  left: 0;
  top: 15px;
}
.dataframe .ps__rail-y .ps__thumb-y {
  width: 100%;
  right: 0;
  background-color: transparent;
  opacity: 1 !important;
}
.dataframe .ps__rail-y .ps__thumb-y::before {
  content: "";
  display: block;
  position: absolute;
  background-color: #cccccc;
  border-radius: 5px;
  width: 100%;
  height: calc(100% - 30px);
  left: 0;
  top: 15px;
}
/*//////////////////////////////////////////////////////////////////
[ Table ]*/
.dataframe {
  background-color: #fff;
	font-size: 14px;
	font-style: normal;
	font-variant: normal;
	font-weight: 300;
}
table {
  width: 400px;
}
th, td {
  font-weight: unset;
  padding-right: 10px;
}
.column1 {
  width: 30%;
  font-weight: 450;
}
.column2 {
  padding-left: 16px;
  width: 70%;
  font-weight: 300;
}
.dataframe-head th {
  padding-top: 18px;
  padding-bottom: 18px;
}
.dataframe-body td {
  padding-top: 16px;
  padding-bottom: 16px;
	font-style: normal;
	font-variant: normal;
}
/*==================================================================
[ Fix header ]*/
.dataframe {
  position: relative;
  padding-top: 60px;
}
.dataframe-head {
  position: absolute;
  width: 100%;
  top: 0;
  left: 0;
}
.dataframe-body {
  max-height: 585px;
  overflow: auto;
}
/*==================================================================
[ Ver5 ]*/
.dataframe {
  margin-right: 30px;
}
.dataframe .dataframe-head {
  padding-right: 30px;
}
.dataframe th {
  color: #555555;
  line-height: 1.4;
  text-transform: uppercase;
  background-color: transparent;
}
.dataframe td {
  line-height: 1.4;
  background-color: #f7f7f7;
}
.dataframe .dataframe-body tr {
  overflow: hidden;
  border-bottom: 10px solid #fff;
  border-radius: 10px;
}
.dataframe .dataframe-body table {
  border-collapse: separate;
  border-spacing: 0 10px;
}
.dataframe .dataframe-body td {
    border: solid 1px transparent;
    border-style: solid none;
    padding-top: 10px;
    padding-bottom: 10px;
}
.dataframe .dataframe-body td:first-child {
    border-left-style: solid;
    border-top-left-radius: 10px;
    border-bottom-left-radius: 10px;
}
.dataframe .dataframe-body td:last-child {
    border-right-style: solid;
    border-bottom-right-radius: 10px;
    border-top-right-radius: 10px;
}
.dataframe tr:hover td {
  background-color: #ebebeb;
  cursor: pointer;
}
.dataframe .dataframe-head th {
  padding-top: 25px;
  padding-bottom: 25px;
}
/*---------------------------------------------*/
.dataframe {
  overflow: hidden;
}
.dataframe .dataframe-body{
  padding-right: 30px;
}
.dataframe .ps__rail-y {
  right: 0px;
}
.dataframe .ps__rail-y::before {
  background-color: #ebebeb;
}
.dataframe .ps__rail-y .ps__thumb-y::before {
  background-color: #cccccc;
}
</style>"""


# FUNCTIONS
def plot_array(array, subplot_ijk, title="", font_size=18, cmap=None):
    sp = plt.subplot(*subplot_ijk)
    sp.set_title(title, fontsize=font_size)
    plt.axis('off')
    plt.imshow(array, cmap=cmap)


def footprints_outline_styler(x):
    return {'fillOpacity': .25,
            'color'      : COLORS['pink'],
            'fillColor'  : COLORS['gray'],
            'weight'     : 1}


def folium_map(geojson_to_overlay, layer_name, location, style_function=None, tiles='Stamen Terrain', zoom_start=16,
               show_layer_control=True, width='100%', height='75%', attr=None, map_zoom=18, max_zoom=20, tms=False,
               zoom_beyond_max=None, base_tiles='OpenStreetMap', opacity=1):
    m = folium.Map(location=location, zoom_start=zoom_start, width=width, height=height, max_zoom=map_zoom,
                   tiles=base_tiles)
    tiles = folium.TileLayer(tiles=tiles, attr=attr, name=attr, max_zoom=max_zoom)
    if tms is True:
        options = json.loads(tiles.options)
        options.update({'tms': True})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if zoom_beyond_max is not None:
        options = json.loads(tiles.options)
        options.update({'maxNativeZoom': zoom_beyond_max, 'maxZoom': max_zoom})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if opacity < 1:
        options = json.loads(tiles.options)
        options.update({'opacity': opacity})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)

    tiles.add_to(m)
    if style_function is not None:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name, style_function=style_function)
    else:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name)
    gj.add_to(m)

    if show_layer_control is True:
        folium.LayerControl().add_to(m)

    return m


def add_popups(features, m):
    for feature in features:
        lngs, lats = list(zip(*list(feature['geometry'].exterior.coords)))
        locations = list(zip(lats, lngs))
        df = pd.DataFrame(list(zip(*[(k, v) for k, v in feature['properties'].items()]))).transpose()
        df.columns = ['attribute', 'value']
        df.set_index('attribute', inplace=True)
        html = df.to_html(header=False, float_format='{:,.2f}'.format, border=False)
        html = TABLE_CSS + html.replace('<tbody>', '<tbody class="dataframe-body">').replace('<td>',
                                                                                             '<td class="column2">').replace(
            '<th>', '<td class="column1">').replace('</th>', '</td>')
        popup = folium.map.Popup(html=html, max_width=500, parse_html=True)
        popup._template = jinja2.Template(u"""
            var {{this.get_name()}} = L.popup({maxWidth: '{{this.max_width}}'});
            {% for name, element in this.html._children.items() %}
                var {{name}} = $('{{element.render(**kwargs).replace('\\n',' ')}}')[0];
                {{this.get_name()}}.setContent({{name}});
            {% endfor %}
            {{this._parent.get_name()}}.bindPopup({{this.get_name()}});
            {{this._parent._parent.get_name()}}.on('overlayadd', function(){
                {{this._parent.get_name()}}.bringToFront();
            });
            {% for name, element in this.script._children.items() %}
                {{element.render()}}
            {% endfor %}
            """)
        marker = folium.features.RegularPolygonMarker(locations, color='white', weight=0, fill_color='white', fill_opacity=0,
                                               popup=popup)

        marker.add_to(m)
    return m

def folium_map_tooltips(geojson_to_overlay, layer_name, location, style_function=None, tiles='Stamen Terrain', zoom_start=16,
               show_layer_control=True, width='100%', height='75%', attr=None, map_zoom=18, max_zoom=20, tms=False,
               zoom_beyond_max=None, base_tiles='OpenStreetMap', opacity=1,
               tooltip_props=None, tooltip_aliases=None):
    m = folium.Map(location=location, zoom_start=zoom_start, width=width, height=height, max_zoom=map_zoom,
                   tiles=base_tiles)
    tiles = folium.TileLayer(tiles=tiles, attr=attr, name=attr, max_zoom=max_zoom,
                             overlay=True, show=True)
    if tms is True:
        options = json.loads(tiles.options)
        options.update({'tms': True})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if zoom_beyond_max is not None:
        options = json.loads(tiles.options)
        options.update({'maxNativeZoom': zoom_beyond_max, 'maxZoom': max_zoom})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)
    if opacity < 1:
        options = json.loads(tiles.options)
        options.update({'opacity': opacity})
        tiles.options = json.dumps(options, sort_keys=True, indent=2)
        tiles._template = jinja2.Template(u"""
        {% macro script(this, kwargs) %}
            var {{this.get_name()}} = L.tileLayer(
                '{{this.tiles}}',
                {{ this.options }}
                ).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)

    tiles.add_to(m)
    if style_function is not None:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name, style_function=style_function)
    else:
        gj = folium.GeoJson(geojson_to_overlay, overlay=True, name=layer_name)
    if tooltip_props is not None:
        folium.features.GeoJsonTooltip(tooltip_props, aliases=tooltip_aliases).add_to(gj)
    gj.add_to(m)

    if show_layer_control is True:
        folium.LayerControl().add_to(m)

    return m

def to_geojson(l):
    g = {'crs': {u'properties': {u'name': u'urn:ogc:def:crs:OGC:1.3:CRS84'}, 'type': 'name'},
         'features': [{'geometry': d['geometry'].__geo_interface__, 'properties': d['properties'], 'type': 'Feature'}
                      for d in l],
         'type': u'FeatureCollection'}

    if sys.version_info[0] == 3:
        serializer = np_serializer
    else:
        serializer = None

    gj = json.dumps(g, default=serializer)

    return gj

def np_serializer(i):
    if type(i).__module__ == np.__name__:
        return np.asscalar(i)
    raise TypeError(repr(i) + " is not JSON serializable")

def get_map_style(map_center, buildings=None, trees=None):
    map_style = {
        'version': 8,
        'center' : map_center,
        'zoom'   : 17.2,
        'pitch'  : 60,
        'bearing': 85,
        'sources': {
            'basemap': {
                'type' : 'raster',
                'tiles': ['https://api.mapbox.com/v4/mapbox.light/{z}/{x}/{y}.png?access_token=%(token)s' % {
                    'token': os.environ.get('MAPBOX_API_KEY')}]
            }
        },
        'layers' : [
            {
                'id'    : 'basemap',
                'type'  : 'raster',
                'source': 'basemap'
            }
        ]
    }

    if buildings is not None:
        map_style['sources']['buildings'] = {'type': 'geojson',
                                             'data': json.loads(to_geojson(buildings))}
        new_layers = [{
            'id'    : 'buildings_base',
            'source': 'buildings',
            'type'  : 'fill',
            'paint' : {
                'fill-color'  : '#777777',
                'fill-opacity': 1,
            }
        },
            {
                'id'    : 'buildings',
                'source': 'buildings',
                'type'  : 'fill-extrusion',
                'paint' : {
                    'fill-extrusion-color'  : '#777777',
                    'fill-extrusion-opacity': 0.95,
                    'fill-extrusion-height' : ['get', 'height_m'],
                    'fill-extrusion-base'   : 0,
                }
            }]
        map_style['layers'].extend(new_layers)

    if trees is not None:
        map_style['sources']['trees'] = {'type': 'geojson',
                                         'data': json.loads(to_geojson(trees))}
        new_layers = [{
            'id'    : 'trees',
            'source': 'trees',
            'type'  : 'fill-extrusion',
            'paint' : {
                'fill-extrusion-color'  : '#3a9642',
                'fill-extrusion-opacity': 0.95,
                'fill-extrusion-height' : ['get', 'height_m'],
                'fill-extrusion-base'   : 0,
            }
        }]
        map_style['layers'].extend(new_layers)

    return map_style
