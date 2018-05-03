import jinja2
import json
import folium
from matplotlib import pyplot as plt, colors
import os
import ops

# CONSTANTS
TMS_104001002E6A7E00 = 'https://s3.amazonaws.com/notebooks-small-tms/104001002E6A7E00/{z}/{x}/{y}.png'
COLORS = {'gray'       : '#8F8E8E',
          'white'      : '#FFFFFF',
          'brightgreen': '#00FF17',
          'red'        : '#FF0000',
          'cyan'       : '#1FFCFF',
          'yellow'     : '#FCFE1A',
          'pink'       : '#F30EFE'}


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
                                             'data': json.loads(ops.to_geojson(buildings))}
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
                                         'data': json.loads(ops.to_geojson(trees))}
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