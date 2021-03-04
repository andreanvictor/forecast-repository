import csv
from itertools import groupby

import click
import django
from django.db import connection
from django.shortcuts import get_object_or_404

# set up django. must be done before loading models. NB: requires DJANGO_SETTINGS_MODULE to be set
django.setup()

from utils.migration_0014_utils import _grouped_version_rows

from utils.utilities import YYYY_MM_DD_DATE_FORMAT

from forecast_app.models import Project


@click.command()
def main():
    """
    Prints version information about all forecasts in the project that have versions, esp. versions that implicitly
    retract data, i.e., versions where the older issue_date has rows that are missing in the next newer one. We process
    issue_dates in pairs in ASC order, and output one report row per pair.
    """
    project = get_object_or_404(Project, pk=44)
    timezero_id_to_obj = {timezero.pk: timezero for timezero in project.timezeros.all()}

    with open('/tmp/temp.csv', 'w') as fp:
        csv_writer = csv.writer(fp, delimiter=',')
        csv_writer.writerow(['timezero', 'source', 'issue_date_1', 'issue_date_2', 'order',
                             'num_pes_both', 'num_pes_added', 'num_pes_removed', 'num_rows_both',
                             'f2_earlier?', 'f1_id', 'f2_id', 'f1_upload', 'f2_upload'])  # header
        print(f'starting. project={project}. getting _grouped_version_rows()')
        grouped_version_rows = _grouped_version_rows(project, True)  # is_versions_only
        print(f'starting. #grouped_version_rows={len(grouped_version_rows)}')
        for (fm_id, tz_id), grouper in groupby(grouped_version_rows, key=lambda _: (_[0], _[1])):
            print(fm_id, tz_id)
            tz_date = timezero_id_to_obj[tz_id].timezero_date.strftime(YYYY_MM_DD_DATE_FORMAT)
            versions = list(grouper)  # list for zip
            for (_, _, issue_date_1, f_id_1, source_1, created_at_1, rank_1), \
                (_, _, issue_date_2, f_id_2, source_2, created_at_2, rank_2) in zip(versions, versions[1:]):
                num_pes_removed, num_pes_added, num_pes_both, num_rows_both = _compare_forecasts_old(f_id_1, f_id_2)
                row = [tz_date, source_1, issue_date_1.strftime(YYYY_MM_DD_DATE_FORMAT),
                       issue_date_2.strftime(YYYY_MM_DD_DATE_FORMAT), f'{rank_1}->{rank_2}',
                       num_pes_both, num_pes_added, num_pes_removed, num_rows_both,
                       created_at_1 > created_at_2, f_id_1, f_id_2, created_at_1, created_at_2]
                csv_writer.writerow(row)
        print('done')


def _compare_forecasts_old(f_id_1, f_id_2):
    """
    Compares the point and quantile predictions of two forecasts (versions for the same timezero) and returns a rows
    suitable for csv output.

    :param f_id_1: a Forecast ID
    :param f_id_2: ""
    :return: a 4-tuple: (num_pes_removed, num_pes_added, num_pes_both, num_rows_both)
    """
    num_f1_not_in_f2_p = _forecast_diff_old(f_id_1, f_id_2, True, False, True)
    num_f2_not_in_f1_p = _forecast_diff_old(f_id_2, f_id_1, True, False, True)

    num_f1_not_in_f2_q = _forecast_diff_old(f_id_1, f_id_2, False, False, True)
    num_f2_not_in_f1_q = _forecast_diff_old(f_id_2, f_id_1, False, False, True)

    num_both_f1_f2_p = _forecast_diff_old(f_id_1, f_id_2, True, True, True)
    num_both_f1_f2_q = _forecast_diff_old(f_id_1, f_id_2, False, True, True)

    num_pes_both_p = _forecast_diff_old(f_id_1, f_id_2, True, True, False)
    num_pes_both_q = _forecast_diff_old(f_id_1, f_id_2, False, True, False)

    return [num_f1_not_in_f2_p + num_f1_not_in_f2_q,
            num_f2_not_in_f1_p + num_f2_not_in_f1_q,
            num_both_f1_f2_p + num_both_f1_f2_q,
            num_pes_both_p + num_pes_both_q]


def _forecast_diff_old(f_id_1, f_id_2, is_point, is_intersect, is_pred_eles):
    """
    Returns the number of point or quantile old data prediction elements (i.e., `unit_id, target_id` key) rows in first
    forecast that are not in the second one.
    """
    table_name = 'forecast_app_pointprediction' if is_point else 'forecast_app_quantiledistribution'
    columns = 'unit_id, target_id'  # is_pred_eles
    if not is_pred_eles and is_point:  # add PointPrediction-specific columns
        columns += ', value_i, value_f, value_t, value_d, value_b'
    elif not is_pred_eles:  # add QuantileDistribution columns
        columns += ', value_i, value_f, value_d'
    sql = f"""
        WITH except_rows AS (
            SELECT {columns}
            FROM {table_name}
            WHERE forecast_id = %s
                {'INTERSECT' if is_intersect else 'EXCEPT'}
            SELECT {columns}
            FROM {table_name}
            WHERE forecast_id = %s
        )
        SELECT COUNT(*)
        FROM except_rows;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, (f_id_1, f_id_2,))
        return cursor.fetchone()[0]


if __name__ == '__main__':
    main()
