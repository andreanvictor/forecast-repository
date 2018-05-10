import logging
from itertools import groupby

import pymmwr
from django.db import connection

from forecast_app.models import ForecastData, Forecast, ForecastModel, TimeZero
from forecast_app.models.data import CDCData
from utils.delphi import delphi_wili_for_mmwr_year_week


logger = logging.getLogger(__name__)


def location_to_mean_abs_error_rows_for_project(project, season_name,
                                                wili_for_epi_week_fcn=delphi_wili_for_mmwr_year_week):
    """
    Called by the project_visualizations() view function, returns a dict containing a table of mean absolute errors for
    all models and all locations in project for season_name. The dict maps:
    {location: (mean_abs_error_rows, target_to_min_mae)}, where rows is a table in the form of a list of rows where each
    row corresponds to a model, and each column corresponds to a target, i.e., X=target vs. Y=Model.

    See _mean_abs_error_rows_for_project() for the format of mean_abs_error_rows.

    Returns {} if no appropriate targets in project.
    """
    targets = project.get_targets_for_mean_absolute_error()
    if not targets:
        return {}

    targets = sorted(targets)

    # cache all the data we need for all models
    logger.debug("location_to_mean_abs_error_rows_for_project(): calling: _model_ids_to_point_values_dicts(). "
                 "targets={}".format(targets))
    model_ids_to_point_values_dicts = _model_ids_to_point_values_dicts(project, season_name, targets)
    logger.debug("location_to_mean_abs_error_rows_for_project(): calling: _model_ids_to_forecast_rows()")
    model_ids_to_forecast_rows = _model_ids_to_forecast_rows(project, project.models.all(), season_name)
    logger.debug("location_to_mean_abs_error_rows_for_project(): calling: _mean_abs_error_rows_for_project(), multiple")
    location_to_mean_abs_error_rows = {
        location: _mean_abs_error_rows_for_project(project, targets, location, model_ids_to_point_values_dicts,
                                                   model_ids_to_forecast_rows, wili_for_epi_week_fcn)
        for location in project.get_locations()}
    logger.debug("location_to_mean_abs_error_rows_for_project(): done")
    return location_to_mean_abs_error_rows


def _mean_abs_error_rows_for_project(project, targets, location,
                                     model_ids_to_point_values_dicts, model_ids_to_forecast_rows,
                                     wili_for_epi_week_fcn):
    """
    Returns a 2-list of the form: (rows, target_to_min_mae), where rows is a table in the form of a list of rows where
    each row corresponds to a model, and each column corresponds to a target, i.e., X=target vs. Y=Model. The format:

        [[model1_pk, target1_mae, target2_mae, ...], ...]

    The first row is the header.

    Recall the Mean Absolute Error table from http://reichlab.io/flusight/ , such as for these settings:

        US National > 2016-2017 > 1 wk, 2 wk, 3 wk, 4 wk ->

        +----------+------+------+------+------+
        | Model    | 1 wk | 2 wk | 3 wk | 4 wk |
        +----------+------+------+------+------+
        | kcde     | 0.29 | 0.45 | 0.61 | 0.69 |
        | kde      | 0.58 | 0.59 | 0.6  | 0.6  |
        | sarima   | 0.23 | 0.35 | 0.49 | 0.56 |
        | ensemble | 0.3  | 0.4  | 0.53 | 0.54 |
        +----------+------+------+------+------+

    The second return arg - target_to_min_mae - is a dict that maps: {target_ minimum_mae). Returns ([], {}) if the
    project does not have appropriate targets defined in its configuration. NB: assumes all of project's models have the
    same targets - something is validated by ForecastModel.load_forecast()
    """
    logger.debug("_mean_abs_error_rows_for_project(): entered. location={}".format(location))
    target_to_min_mae = {target: None for target in targets}  # tracks min MAE for bolding in table. filled next
    rows = [['Model', *targets]]  # header
    for forecast_model in sorted(project.models.all(), key=lambda fm: fm.name):
        # logger.debug("\t{}".format(forecast_model))
        row = [forecast_model.pk]
        for target in targets:
            forecast_to_point_dicts = model_ids_to_point_values_dicts[forecast_model.pk] \
                if forecast_model.pk in model_ids_to_point_values_dicts \
                else {}
            forecast_id_tz_date_csv_fname_rows = model_ids_to_forecast_rows[forecast_model.pk] \
                if forecast_model.pk in model_ids_to_forecast_rows \
                else {}
            mae_val = mean_absolute_error(forecast_model, location, target, wili_for_epi_week_fcn,
                                          forecast_to_point_dicts, forecast_id_tz_date_csv_fname_rows)
            if not mae_val:
                return []

            target_to_min_mae[target] = min(mae_val, target_to_min_mae[target]) \
                if target_to_min_mae[target] else mae_val
            row.append(mae_val)
        rows.append(row)

    logger.debug("_mean_abs_error_rows_for_project(): done")
    return [rows, target_to_min_mae]


def mean_absolute_error(forecast_model, location, target, wili_for_epi_week_fcn,
                        forecast_to_point_dicts, forecast_id_tz_date_csv_fname_rows):
    """
    Calculates the mean absolute error for the passed model and parameters. Note: Uses cached values
    (forecast_to_point_dicts and forecast_id_tz_date_csv_fname_rows) instead of hitting the database directly, for
    speed.

    :param: forecast_model: ForecastModel whose forecasts are used for the calculation
    :param: location: a location in the model
    :param: target: "" target ""
    :param: forecast_to_point_dicts: cached points for forecast_model as returned by _model_ids_to_point_values_dicts()
    :param: forecast_id_tz_date_csv_fname_rows: cached rows for forecast_model as returned by
        _model_ids_to_forecast_rows()
    :param: wili_for_epi_week_fcn: a function of three args (year, week, location_name) that returns the true/actual
        wili value for an epi week. (2017-09-06: from Abhinav: We use wili for all our work. *w* in wili is for
        weighted. If I recall correctly, wili is the ili which is normalized according to population. So two wilis from
        two different regions can be compared fairly but not two ilis.)
    :return: mean absolute error (scalar) for my predictions for a location and target. returns None if can't be
        calculated
    """
    forecasts = forecast_model.forecasts.all()
    if not forecasts:
        raise RuntimeError("could not calculate absolute errors: no data. forecast_model={}".format(forecast_model))

    week_increment = forecast_model.project.get_week_increment_for_target_name(target)
    if not week_increment:
        return None

    cdc_file_name_to_abs_error = {}
    for forecast_id, forecast_timezero_date, forecast_csv_filename in forecast_id_tz_date_csv_fname_rows:
        tz_ywd_mmwr_dict = pymmwr.date_to_mmwr_week(forecast_timezero_date)
        future_yw_mmwr_dict = pymmwr.mmwr_week_with_delta(tz_ywd_mmwr_dict['year'],
                                                          tz_ywd_mmwr_dict['week'],
                                                          week_increment)
        true_value = wili_for_epi_week_fcn(forecast_model.project,
                                           future_yw_mmwr_dict['year'],
                                           future_yw_mmwr_dict['week'],
                                           location)
        if true_value is None:  # truth not available
            continue

        predicted_value = forecast_to_point_dicts[forecast_id][location][target]
        abs_error = abs(predicted_value - true_value)
        cdc_file_name_to_abs_error[forecast_csv_filename] = abs_error

    return (sum(cdc_file_name_to_abs_error.values()) / len(cdc_file_name_to_abs_error)) if cdc_file_name_to_abs_error \
        else None


def _model_ids_to_forecast_rows(project, forecast_models, season_name):
    """
    Returns a dict for forecast_models and season_name that maps: ForecastModel.pk -> 3-tuple of the form:
    (forecast_id, forecast_timezero_date, forecast_csv_filename). This is an optimization that avoids some ORM overhead
    when simply iterating like so: `for forecast in forecast_model.forecasts.all(): ...`
    """
    # get the rows, ordered so we can groupby()
    sql = """
        SELECT fm.id, f.id, tz.timezero_date, f.csv_filename
        FROM {forecastmodel_table_name} fm
          JOIN {forecast_table_name} f on fm.id = f.forecast_model_id
          JOIN {timezero_table_name} tz ON f.time_zero_id = tz.id
        WHERE fm.id IN ({model_ids_query_string})
              AND %s <= tz.timezero_date
              AND tz.timezero_date <= %s
        ORDER BY fm.id;
    """.format(forecastmodel_table_name=ForecastModel._meta.db_table,
               forecast_table_name=Forecast._meta.db_table,
               timezero_table_name=TimeZero._meta.db_table,
               model_ids_query_string=', '.join(['%s'] * len(forecast_models)))
    with connection.cursor() as cursor:
        season_start_date, season_end_date = project.start_end_dates_for_season(season_name)
        forecast_model_ids = [forecast_model.pk for forecast_model in forecast_models]
        logger.debug("_model_ids_to_forecast_rows(): calling: execute(): {}, {}".format(
            sql,
            [*forecast_model_ids, season_start_date, season_end_date]))
        cursor.execute(sql, [*forecast_model_ids, season_start_date, season_end_date])
        rows = cursor.fetchall()

    # build the dict
    logger.debug("_model_ids_to_forecast_rows(): building model_ids_to_forecast_rows")
    model_ids_to_forecast_rows = {}  # return value. filled next
    for model_pk, forecast_row_grouper in groupby(rows, key=lambda _: _[0]):
        model_ids_to_forecast_rows[model_pk] = [row[1:] for row in forecast_row_grouper]

    logger.debug("_model_ids_to_forecast_rows(): done")
    return model_ids_to_forecast_rows


def _model_ids_to_point_values_dicts(project, season_name, targets):
    """
    :return: a dict that provides predicted point values for all of project's models, season_name, and targets. The dict
        drills down as such:

    - model_to_point_dicts: {forecast_model_id -> forecast_to_point_dicts}
    - forecast_to_point_dicts: {forecast_id -> location_to_point_dicts}
    - location_to_point_dicts: {location -> target_to_points_dicts}
    - target_to_points_dicts: {target -> point_value}
    """
    forecast_models = project.models.all()

    # get the rows, ordered so we can groupby()
    sql = """
        SELECT fm.id, f.id, fd.location, fd.target, fd.value
        FROM {forecast_data_table_name} fd
          JOIN {forecast_table_name} f ON fd.forecast_id = f.id
          JOIN {timezero_table_name} tz ON f.time_zero_id = tz.id
          JOIN {forecastmodel_table_name} fm ON f.forecast_model_id = fm.id
        WHERE fm.id IN ({model_ids_query_string})
              AND fd.row_type = %s
              AND fd.target IN ({target_query_string})
              AND %s <= tz.timezero_date
              AND tz.timezero_date <= %s
        ORDER BY fm.id, f.id, fd.location, fd.target;
    """.format(forecast_data_table_name=ForecastData._meta.db_table,
               forecast_table_name=Forecast._meta.db_table,
               timezero_table_name=TimeZero._meta.db_table,
               forecastmodel_table_name=ForecastModel._meta.db_table,
               model_ids_query_string=', '.join(['%s'] * len(forecast_models)),
               target_query_string=', '.join(['%s'] * len(targets)))
    with connection.cursor() as cursor:
        season_start_date, season_end_date = project.start_end_dates_for_season(season_name)
        forecast_model_ids = [forecast_model.pk for forecast_model in forecast_models]
        logger.debug("_model_ids_to_point_values_dicts(): calling: execute(): {}, {}".format(
            sql,
            [*forecast_model_ids, CDCData.POINT_ROW_TYPE, *targets, season_start_date, season_end_date]))
        cursor.execute(sql, [*forecast_model_ids, CDCData.POINT_ROW_TYPE, *targets, season_start_date, season_end_date])
        rows = cursor.fetchall()

    # build the dict
    logger.debug("_model_ids_to_point_values_dicts(): building models_to_point_values_dicts")
    models_to_point_values_dicts = {}  # return value. filled next
    for model_pk, forecast_loc_target_val_grouper in groupby(rows, key=lambda _: _[0]):
        forecast_to_point_dicts = {}
        for forecast_pk, loc_target_val_grouper in groupby(forecast_loc_target_val_grouper, key=lambda _: _[1]):
            location_to_point_dicts = {}
            for location, target_val_grouper in groupby(loc_target_val_grouper, key=lambda _: _[2]):
                grouper_rows = list(target_val_grouper)
                location_to_point_dicts[location] = {grouper_row[3]: grouper_row[4] for grouper_row in grouper_rows}
            forecast_to_point_dicts[forecast_pk] = location_to_point_dicts
        models_to_point_values_dicts[model_pk] = forecast_to_point_dicts

    logger.debug("_model_ids_to_point_values_dicts(): done")
    return models_to_point_values_dicts
