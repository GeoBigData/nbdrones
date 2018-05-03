from shapely.geometry import shape
from affine import Affine
import os
import rasterio
from rasterio import features
import numpy as np
import pyproj
from functools import partial
from matplotlib.colors import LightSource
import matplotlib.pyplot as plt
from shapely import ops
import json
from skimage import filters, measure, segmentation
import requests

# CONSTANTS
buildings_sanfran = 'https://s3.amazonaws.com/gbdx-training/drones/buildings_soma_subset.geojson'
dsm_sanfran = 'https://s3.amazonaws.com/gbdx-training/drones/dsm_soma_subset.tif'


# FUNCTIONS
def reproject(geom, from_proj=None, to_proj=None):
    tfm = partial(pyproj.transform, pyproj.Proj(init=from_proj), pyproj.Proj(init=to_proj))
    return ops.transform(tfm, geom)


def buffer_meters(geom, distance_m, from_proj='EPSG:4326', epsg_for_meters='EPSG:26944'):
    # convert the geometry from wgs84 to whatever projection is specified
    geom_tfm = reproject(geom, from_proj, epsg_for_meters)
    buffered_geom_meters = geom_tfm.buffer(distance_m)
    buffered_geom = reproject(buffered_geom_meters, epsg_for_meters, from_proj)

    return buffered_geom


def calc_stats(poly, rast_reader, no_data=-9999):
    # define the upper left and lower right pixels of the DSM in relation to the footprint
    upper_left = rast_reader.index(*poly.bounds[0:2])
    lower_right = rast_reader.index(*poly.bounds[2:4])

    # create a window for reading in the raster
    window = ((lower_right[0], upper_left[0] + 1), (upper_left[1], lower_right[1] + 1))

    # read in a subset of the DSM and vegetation arrays
    rast_subset = rast_reader.read(1, window=window)

    # use the original DSM affine to create a new affine transformation (for rasterizing the building footprint)
    rast_transform = rast_reader.affine
    shifted_affine = Affine(rast_transform.a,
                            rast_transform.b,
                            rast_transform.c + upper_left[1] * rast_transform.a,
                            rast_transform.d,
                            rast_transform.e,
                            rast_transform.f + lower_right[0] * rast_transform.e)

    # rasterize the geometry, which will be used to mask raster values that don't overlay the feature
    poly_mask = rasterio.features.rasterize(
            [(poly, 0)],
            out_shape=rast_subset.shape,
            transform=shifted_affine,
            fill=1,
            all_touched=True,
            dtype=np.uint8)

    # return the raster subset that only contains values that represent the geometry
    poly_data = np.ma.array(data=rast_subset, mask=np.logical_or(poly_mask == 1, rast_subset == no_data))

    # calculate standard statistics
    stats = {'min'   : float(poly_data.min()),
             'max'   : float(poly_data.max()),
             'mean'  : float(poly_data.mean()),
             'median': float(np.ma.median(poly_data)),
             'std'   : float(poly_data.std())}

    return stats


def calc_object_heights(poly, dsm_reader, top_source='max'):
    ground_poly = buffer_meters(poly, 4, epsg_for_meters='EPSG:26943').difference(poly)
    ground_stats = calc_stats(ground_poly, dsm_reader)

    poly_stats = calc_stats(poly, dsm_reader)

    results = {'ground_elev_m': ground_stats['min'],
               'top_elev_m'   : poly_stats[top_source],
               'height_m'     : poly_stats[top_source] - ground_stats['min']}

    return results


def write_geojson(features, out_file):
    with open(out_file, 'w') as f:
        f.write(to_geojson(features))


def labels_to_polygons(labels_array, image_affine, ignore_label=0, simplify=False):
    # create polygon generator object
    polygon_generator = features.shapes(labels_array.astype('uint8'),
                                        mask=labels_array <> ignore_label,
                                        transform=image_affine)
    # Extract out the individual polygons, fixing any invald geometries using buffer(0)
    polygons = [{'geometry': shape(g).buffer(0), 'properties': {'id': v}} for g, v in polygon_generator]
    if simplify is True:
        for polygon in polygons:
            polygon['geometry'] = polygon['geometry'].simplify(image_affine.a)

    return polygons


def read_from_raster(rast_reader, bounds=None, band=1):
    if bounds is not None:
        # define the upper left and lower right pixels of the DSM in relation to the footprint
        upper_left = rast_reader.index(*bounds[0:2])
        lower_right = rast_reader.index(*bounds[2:4])
        # create a window for reading in the raster
        window = ((lower_right[0], upper_left[0] + 1), (upper_left[1], lower_right[1] + 1))
    else:
        window = None

    return rast_reader.read(band, window=window)


def create_hillshade(array, cmap=plt.cm.pink, vert_exag=1, azdeg=315, altdeg=45):
    light_source = LightSource(azdeg=azdeg, altdeg=altdeg)
    hillshade = light_source.shade(array, vmin=0, vmax=array.max() * 1.25, cmap=cmap, vert_exag=vert_exag,
                                   blend_mode='soft')

    return hillshade


def segment_trees(img, n_segments=2000):
    # segment the image
    rgb = img.base_layer_match(blm=True, access_token=os.environ.get('MAPBOX_API_KEY'))
    rgb_smooth = filters.gaussian(filters.gaussian(rgb, preserve_range=True, ), preserve_range=True)
    img_segmented = segmentation.slic(rgb_smooth, n_segments=n_segments, max_iter=100)

    # calculate ndvi
    ndvi = img.ndvi(quiet=True)
    # clean up any nan values
    ndvi[np.isnan(ndvi)] = 0

    # find the trees
    ndvi_threshold = filters.threshold_otsu(ndvi)
    tree_regions = [r.label for r in measure.regionprops(img_segmented, intensity_image=ndvi) if
                    r.mean_intensity > ndvi_threshold]
    trees_array = np.isin(img_segmented, tree_regions) * img_segmented

    return trees_array


def from_geojson(source):
    if source.startswith('http'):
        response = requests.get(source)
        geojson = json.loads(response.content)
    else:
        if os.path.exists(source):
            with open(source, 'r') as f:
                geojson = json.loads(f.read())
        else:
            raise ValueError("File does not exist: {}".format(source))

    return geojson


def to_geojson(l):
    g = {'crs'     : {u'properties': {u'name': u'urn:ogc:def:crs:OGC:1.3:CRS84'}, 'type': 'name'},
         'features': [{'geometry': d['geometry'].__geo_interface__, 'properties': d['properties'], 'type': 'Feature'}
                      for d in l],
         'type'    : u'FeatureCollection'}

    gj = json.dumps(g)

    return gj