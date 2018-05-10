from itertools import groupby

import pymmwr
from django.db import connection

from forecast_app.models import ForecastData, Forecast, TimeZero, ForecastModel
from forecast_app.models.data import CDCData


#
# This file defines functions related to the Flusight D3 component at https://github.com/reichlab/d3-foresight
#

def flusight_data_dicts_for_models(forecast_models, season_name, request=None):
    """
    Returns a dict containing forecast_model's point forecasts for all locations in season_name, structured
    according to https://github.com/reichlab/d3-foresight . Keys are the locations, and values are the individual data
    dicts for each. Recall the format of the latter:

    let data = {
    timePoints,
    models: [
      {
        id: 'mod',
        meta: {
          name: 'Name',
          description: 'Model description here',
          url: 'http://github.com'
        },
        predictions
      }
    ]
    }

    where timePoints is a list of objects like: { "week": 1, "year": 2016 },

    and predictions is a list of 'series' objects containing 'point' objects, e.g.,

     "predictions": [
       {
         "series": [
           { "point": 0.7090864619172196 },
           { "point": 1.4934249007589637 }
         ]
       },
       {
         "series": [
           { "point": 0.912445314619254 },
           { "point": 0.4646919757087566 }
         ]
       }
       ...
     ]

    Notes:
    - The length of predictions must match that of timePoints, using null for missing points.
    - All models must belong to the same Project.
    - Returns None if the project has no get_targets_for_mean_absolute_error().
    - If request is passed then it is used to calculate each model's absolute URL (used in the flusight component's info
      box). o/w the model's home_url is used
    """
    if not forecast_models:
        return None

    projects = [forecast_model.project for forecast_model in forecast_models]
    if not projects.count(projects[0]) == len(projects):
        raise RuntimeError("Not all models are in the same Project")

    project = projects[0]
    targets = project.get_targets_for_mean_absolute_error()
    if not targets:
        return None
    else:
        targets = sorted(targets)

    # set time_points. order_by -> matches ORDER BY in _flusight_point_value_rows_for_models():
    time_points = []
    project_timezeros = project.timezeros_in_season(season_name)
    for timezero in project_timezeros:
        # todo xx pymmwr dependency will go away once the D3 Foresight component is changed to work with dates, not EWs:
        tz_ywd_mmwr_dict = pymmwr.date_to_mmwr_week(timezero.timezero_date)
        time_points.append({'week': tz_ywd_mmwr_dict['week'],
                            'year': tz_ywd_mmwr_dict['year']})

    model_to_location_timezero_points = _model_to_location_timezero_points(project, forecast_models, season_name,
                                                                           targets)

    # now that we have model_to_location_timezero_points, we can build the return value, extracting each
    # location from all of the models
    locations_to_flusight_data_dicts = {}  # return value. filled next
    for location in project.get_locations():
        model_dicts = _model_dicts_for_location_to_timezero_points(project_timezeros, location,
                                                                   model_to_location_timezero_points, request)
        data_dict = {'timePoints': time_points,
                     'models': sorted(model_dicts, key=lambda _: _['meta']['name'])}
        locations_to_flusight_data_dicts[location] = data_dict
    return locations_to_flusight_data_dicts


def _model_dicts_for_location_to_timezero_points(project_timezeros, location,
                                                 model_to_location_timezero_points, request):
    model_dicts = []
    for forecast_model, location_to_timezero_points in model_to_location_timezero_points.items():
        timezero_to_points = location_to_timezero_points[location] if location in location_to_timezero_points \
            else {}  # NB: ordered by timezero_date
        model_dict = {
            'id': forecast_model.name[:10] + '(' + str(forecast_model.id) + ')',
            'meta': {
                'name': forecast_model.name,
                'description': forecast_model.description,
                # 'url': forecast_model.home_url,
                'url': request.build_absolute_uri(
                    forecast_model.get_absolute_url()) if request else forecast_model.home_url,
            },
            'predictions': _prediction_dicts_for_timezero_points(project_timezeros, timezero_to_points)
        }
        model_dicts.append(model_dict)
    return model_dicts


def _prediction_dicts_for_timezero_points(project_timezeros, timezero_to_points):
    prediction_dicts = []
    for timezero in project_timezeros:
        if timezero.timezero_date in timezero_to_points:
            point_dicts = [{'point': point} for point in timezero_to_points[timezero.timezero_date]]
            prediction_dicts.append({'series': point_dicts})
        else:  # no forecasts for this TimeZero
            prediction_dicts.append(None)
    return prediction_dicts


def _model_to_location_timezero_points(project, forecast_models, season_name, targets):
    """
    :return: a dict that maps: forecast_model -> location_dict. each location_dict maps: location ->
        timezero_points_dict, which maps timezero_datetime -> point values. note that some project TimeZeros have no
        predictions
    """
    # get the rows, ordered so we can groupby()
    # note that some project timezeros might not be returned by _flusight_point_value_rows_for_models():
    # query notes:
    # - ORDER BY ensures groupby() will work
    # - we don't need to select targets b/c forecast ids have 1:1 correspondence to TimeZeros
    # - "" b/c targets are needed only for ordering
    sql = """
        SELECT fm.id, fd.location, tz.timezero_date, fd.value
        FROM {forecast_data_table_name} fd
          JOIN {forecast_table_name} f ON fd.forecast_id = f.id
          JOIN {timezero_table_name} tz ON f.time_zero_id = tz.id
          JOIN {forecastmodel_table_name} fm ON f.forecast_model_id = fm.id
        WHERE fm.id IN ({model_ids_query_string})
              AND fd.row_type = %s
              AND fd.target IN ({target_query_string})
              AND %s <= tz.timezero_date
              AND tz.timezero_date <= %s
        ORDER BY fm.id, fd.location, tz.timezero_date, fd.target;
    """.format(forecast_data_table_name=ForecastData._meta.db_table,
               forecast_table_name=Forecast._meta.db_table,
               timezero_table_name=TimeZero._meta.db_table,
               forecastmodel_table_name=ForecastModel._meta.db_table,
               model_ids_query_string=', '.join(['%s'] * len(forecast_models)),
               target_query_string=', '.join(['%s'] * len(targets)))
    with connection.cursor() as cursor:
        season_start_date, season_end_date = project.start_end_dates_for_season(season_name)
        forecast_model_ids = [forecast_model.pk for forecast_model in forecast_models]
        cursor.execute(sql, [*forecast_model_ids, CDCData.POINT_ROW_TYPE, *targets, season_start_date, season_end_date])
        rows = cursor.fetchall()

    # build the dict
    model_to_location_timezero_points = {}  # return value. filled next
    for model_pk, loc_tz_val_grouper in groupby(rows, key=lambda _: _[0]):
        location_to_timezero_points_dict = {}
        for location, timezero_values_grouper in groupby(loc_tz_val_grouper, key=lambda _: _[1]):
            timezero_to_points_dict = {}
            for timezero_date, values_grouper in groupby(timezero_values_grouper, key=lambda _: _[2]):
                point_values = [_[3] for _ in list(values_grouper)]
                timezero_to_points_dict[timezero_date] = point_values
            location_to_timezero_points_dict[location] = timezero_to_points_dict
        forecast_model = ForecastModel.objects.get(pk=model_pk)
        model_to_location_timezero_points[forecast_model] = location_to_timezero_points_dict

    # b/c _flusight_point_value_rows_for_models() does not return any rows for models that don't have data for
    # season_name and targets, we need to add empty model entries for callers
    for forecast_model in forecast_models:
        if forecast_model not in model_to_location_timezero_points:
            model_to_location_timezero_points[forecast_model] = {}

    return model_to_location_timezero_points
