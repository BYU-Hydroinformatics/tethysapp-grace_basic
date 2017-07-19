from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from tethys_sdk.gizmos import *
import csv, os
from datetime import datetime
from tethys_sdk.services import get_spatial_dataset_engine
import urlparse
import random
import string

WORKSPACE = 'grace_basic_app'
GEOSERVER_URI = 'http://www.example.com/grace-basic-app'

def check_shapefile(id):
    '''
    Check to see if shapefile is on geoserver. If not, upload it.
    '''
    geoserver_engine = get_spatial_dataset_engine(name='default')
    response = geoserver_engine.get_layer(id, debug=True)
    if response['success'] == False:
        #Shapefile was not found. Upload it from app workspace

        #Create the workspace if it does not already exist
        response = geoserver_engine.list_workspaces()
        if response['success']:
            workspaces = response['result']
            if WORKSPACE not in workspaces:
                geoserver_engine.create_workspace(workspace_id=WORKSPACE, uri=GEOSERVER_URI)

        #Create a string with the path to the zip archive
        project_directory = os.path.dirname(__file__)
        app_workspace = os.path.join(project_directory, 'workspaces', 'app_workspace')
        zip_archive = os.path.join(app_workspace, 'shapefiles', id, id + '.zip')

        # Upload shapefile to the workspaces
        store = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        store_id = WORKSPACE + ':' + store
        geoserver_engine.create_shapefile_resource(
            store_id=store_id,
            shapefile_zip=zip_archive,
            overwrite=True
        )

@login_required()
def home(request):
    """
    Controller for the app home page.
    """

    '''
    Check each region to ensure that the shapefile for the region
    is stored in geoserver.
    '''
    check_shapefile('nepal')
    check_shapefile('reg18_calif')
    check_shapefile('reg12_texas')

    context = {}

    return render(request, 'grace_basic/home.html', context)


@login_required
def home_graph(request, id):
    """
    Controller for home page to display a graph and map.
    """

    # Set up the map options

    '''
    First query geoserver to get the layer corresponding to id, then parse
    one of the URLs in the response DICT to get the bounding box.
    Then parse the box to get lat/long to properly center the map
    '''
    geoserver_engine = get_spatial_dataset_engine(name='default')
    response = geoserver_engine.get_layer(id, debug=False)
    kmlurl = response['result']['wms']['kml']
    parsedkml = urlparse.urlparse(kmlurl)
    bbox = urlparse.parse_qs(parsedkml.query)['bbox'][0]
    bboxitems = bbox.split(",")
    box_left = float(bboxitems[0])
    box_right = float(bboxitems[2])
    box_top = float(bboxitems[3])
    box_bottom = float(bboxitems[1])
    centerlat = (box_left + box_right) / 2
    centerlong = (box_top + box_bottom) / 2

    map_layers = []
    geoserver_layer = MVLayer(
        source='ImageWMS',
        options={'url': 'http://localhost:8181/geoserver/wms',
                 'params': {'LAYERS': id},
                 'serverType': 'geoserver'},
        legend_title=id,
        legend_extent=[box_left, box_bottom, box_right, box_top],
        legend_classes=[
            MVLegendClass('polygon', 'Boundary', fill='#999999'),
        ])

    map_layers.append(geoserver_layer)

    view_options = MVView(
        projection='EPSG:4326',
        center=[centerlat, centerlong],
        zoom=4,
        maxZoom=18,
        minZoom=2,
    )

    map_options = MapView(height='300px',
                          width='100%',
                          layers=map_layers,
                          legend=True,
                          view=view_options
                          )

    # Set up the graph options
    project_directory = os.path.dirname(__file__)
    app_workspace = os.path.join(project_directory, 'workspaces', 'app_workspace')
    csv_file = os.path.join(app_workspace, 'output' , id,  'hydrograph.csv')
    with open(csv_file, 'rb') as f:
        reader = csv.reader(f)
        csvlist = list(reader)
    volume_time_series = []
    formatter_string = "%m/%d/%Y"
    for item in csvlist:
        mydate = datetime.strptime(item[0], formatter_string)
        volume_time_series.append([mydate, float(item[1])])

    # Configure the time series Plot View
    grace_plot = TimeSeries(
        engine='highcharts',
        title=id + ' GRACE Data',
        y_axis_title='Volume',
        y_axis_units='cm',
        series=[
            {
                'name': 'Change in Volume',
                'color': '#0066ff',
                'data': volume_time_series,
            },
        ],
        width='100%',
        height='300px'
    )

    context = {'map_options': map_options,
               'grace_plot': grace_plot,
               'reg_id': id}

    return render(request, 'grace_basic/home.html', context)