import datetime
import json
import re
from ast import literal_eval

import requests


def basic_str(obj):
    return obj.__class__.__name__ + ': ' + obj.__repr__()


def parse_value(value):
    """
    Parses a value numerically as smartly as possible, in order: float, int, None. o/w is an error
    """
    # https://stackoverflow.com/questions/34425583/how-to-check-if-string-is-int-or-float-in-python-2-7
    try:
        return literal_eval(value)
    except ValueError:
        return None


def filename_components(filename):
    """
    :param filename: something like 'EW1-KoTstable-2017-01-17.csv'
    :return: either () (if filename invalid) or a 3-tuple (if valid) that indicates if filename matches the CDC
    standard format as defined in [1]. The tuple format is: (ew_week_number, team_name, submission_datetime) . Note that
    "ew_week_number" AKA the forecast's "time zero"
    
    [1] https://webcache.googleusercontent.com/search?q=cache:KQEkQw99egAJ:https://predict.phiresearchlab.org/api/v1/attachments/flusight/flu_challenge_2016-17_update.docx+&cd=1&hl=en&ct=clnk&gl=us
        From that document: 
    
        For submission, the filename should be modified to the following standard naming convention: a forecast
        submission using week 43 surveillance data submitted by John Doe University on November 7, 2016, should be named
        “EW43-JDU-2016-11-07.csv” where EW43 is the latest week of ILINet data used in the forecast, JDU is the name of
        the team making the submission (e.g. John Doe University), and 2016-11-07 is the date of submission.
        
    """
    re_split = re.split(r'^EW(\d*)-(\S*)-(\d{4})-(\d{2})-(\d{2})\.csv$', filename)
    if len(re_split) != 7:
        return ()

    re_split = re_split[1:-1]  # drop outer two ''
    if any(map(lambda part: len(part) == 0, re_split)):
        return ()

    return int(re_split[0]), re_split[1], datetime.date(int(re_split[2]), int(re_split[3]), int(re_split[4]))

#
# ---- functions to access the delphi API ----
#

# server memory cache that maps a 2-tuple (epi_year, epi_week) to the retrieved 'wili' value from Delphi. keys are
# ints. managed by delphi_wili_for_epi_week()
DELPHI_EPIYEAR_AND_EPIWEEK_TO_WILI = {}


def delphi_wili_for_epi_week(forecast_model, year, week, location):
    """
    Looks up the fluview 'wili' value for the past args, using the delphi REST API. Returns as a float see:
    https://github.com/cmu-delphi/delphi-epidata#fluview

    :param forecast_model: the ForecastModel instance making the call
    :param year: EW year
    :param week: EW week number between 1 and 52 inclusive
    :param location: project location name. used to look up the delphi region via Project.region_for_location_name()
    :return: true/actual wili value for the passed year and week, using the delphi REST API. Returns as a float see:
        https://github.com/cmu-delphi/delphi-epidata#fluview . Caches the retrieved value for speed-ups. NB: caching
        means that the values in server memory won't be updated if they change on delphi.midas.cs.cmu.edu , i.e., they
        could become stale and need flushing.
    """
    region = forecast_model.project.get_region_for_location_name(location)
    if not region:
        raise RuntimeError("location_name is not a valid Delphi location: {}".format(location))

    if (year, week) in DELPHI_EPIYEAR_AND_EPIWEEK_TO_WILI:
        return DELPHI_EPIYEAR_AND_EPIWEEK_TO_WILI[(year, week)]
    else:  # cache entire year (requires only one lookup using a Delphi range)
        url = 'https://delphi.midas.cs.cmu.edu/epidata/api.php' \
              '?source=fluview' \
              '&regions={region}' \
              '&epiweeks={epi_year}01-{epi_year}52'. \
            format(region=region, epi_year=year)
        response = requests.get(url)
        response.raise_for_status()  # does nothing if == requests.codes.ok
        delphi_dict = json.loads(response.text)
        for epidata_dict in delphi_dict['epidata']:
            epiweek_val = str(epidata_dict['epiweek'])
            epi_year = int(epiweek_val[:4])
            epi_week = int(epiweek_val[4:])
            wili_val = epidata_dict['wili']
            DELPHI_EPIYEAR_AND_EPIWEEK_TO_WILI[(epi_year, epi_week)] = wili_val
    return DELPHI_EPIYEAR_AND_EPIWEEK_TO_WILI[(year, week)]


#
# ---- mean absolute error functions ----
#

def increment_week(year, week, delta_weeks):
    """
    Adds delta_weeks to timezero_week in timezero_year modulo 52, wrapping around to next year as needed. Returns a
    2-tuple: (incremented_year, incremented_week)
    """
    if (delta_weeks < 1) or (delta_weeks > 52):
        raise RuntimeError("delta_weeks wasn't between 1 and 52: {}".format(delta_weeks))

    incremented_week = week + delta_weeks
    if incremented_week > 52:
        return year + 1, incremented_week - 52
    else:
        return year, incremented_week


def mean_absolute_error(forecast_model, season_start_year, location, target,
                        wili_for_epi_week_fcn=delphi_wili_for_epi_week):
    """
    :param:forecast_model: ForecastModel whose forecasts are used for the calculation
    :param:season_start_year: year of the season, e.g., 2016 for the season 2016-2017
    :param:true_value_for_epi_week_fcn: a function of three args (year, week, location_name) that returns the
        true/actual wili value for an epi week
    :return: mean absolute error (scalar) for my predictions for a location and target
    """
    forecasts = forecast_model.forecasts.all()
    if not forecasts:
        raise RuntimeError("could not calculate absolute errors: no data: {}".format(forecast_model))

    cdc_file_name_to_abs_error = {}
    for forecast in forecasts:
        # set timezero week and year, inferring the latter based on @Evan's and @Nick's replies:
        # > We used week 30. I don't think this is a standardized concept outside of our lab though."
        # > We use separate concepts for a "season" and a "year". So, e.g. the "2016/2017 season" starts with
        # > EW30-2016 and ends with EW29-2017.  <- todo abstract this standard/convention out
        timezero_week = filename_components(forecast.csv_filename)[0]
        timezero_year = season_start_year if timezero_week >= 30 else season_start_year + 1
        future_year, future_week = increment_week(timezero_year, timezero_week,
                                                  forecast_model.project.get_week_increment_for_target_name(target))
        true_value = wili_for_epi_week_fcn(forecast_model, future_year, future_week, location)
        predicted_value = forecast.get_target_point_value(location, target)
        abs_error = abs(predicted_value - true_value)
        cdc_file_name_to_abs_error[forecast.csv_filename] = abs_error

    return sum(cdc_file_name_to_abs_error.values()) / len(cdc_file_name_to_abs_error)


#
# ---- view-related functions ----
#

def mean_abs_error_rows_for_project(project, season_start_year, location):
    """
    Called by the project_visualizations() view function, returns a table in the form of a list of rows where each row
    corresponds to a model, and each column corresponds to a target, i.e., X=target vs. Y=Model. The format:
    
        [[model_name1, target1_mae, target2_mae, ...], ...]

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

    """
    # NB: assumes all of project's models have the same targets - something that should be validated by
    # ForecastModel.load_forecast() or similar

    # todo return indication of best model for each target -> bold in project_visualizations.html
    mae_targets = sorted(project.get_targets_for_mean_absolute_error())
    rows = [['Model', *mae_targets]]  # header
    for forecast_model in project.models.all():
        row = [forecast_model.name]
        for target in mae_targets:
            try:
                mae_val = mean_absolute_error(forecast_model, season_start_year, location, target,
                                              wili_for_epi_week_fcn=delphi_wili_for_epi_week)
                row.append("{:0.2f}".format(mae_val))
            except:
                return []
        rows.append(row)
    return rows
