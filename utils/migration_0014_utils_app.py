import logging
from itertools import groupby

import click
import django
import django_rq


# set up django. must be done before loading models. NB: requires DJANGO_SETTINGS_MODULE to be set
django.setup()

from utils.forecast import load_predictions_from_json_io_dict, cache_forecast_metadata

from utils.migration_0014_utils import _migrate_correctness_worker, is_different_old_new_json, \
    _grouped_version_rows, _migrate_forecast_worker, pred_dicts_with_implicit_retractions, \
    _forecast_previous_version, forecast_ids_with_no_data_new

from forecast_app.models import Forecast, Project, PredictionElement


logger = logging.getLogger(__name__)


#
# cli()
#

@click.group()
def cli():
    pass


#
# check_correctness()
#

@cli.command(name="check")
@click.option('--enqueue/--no-enqueue', default=False)
def check_correctness(enqueue):
    """
    Compares old and new json_io_dict outputs for every Forecast in the database. ERRORs if didn't match.

    :param enqueue: controls whether the update will be immediate in the calling thread (blocks), or enqueued for RQ
    """
    from forecast_repo.settings.base import DEFAULT_QUEUE_NAME  # avoid circular imports


    forecasts = Forecast.objects.all().order_by('created_at')
    if not enqueue:
        logger.info(f"checking {len(forecasts)} forecasts")
        for forecast in forecasts:
            is_different = is_different_old_new_json(forecast)
            if is_different:
                logger.error(f"old != new: {is_different}")
        logger.info(f"checking done")
    else:
        logger.info(f"enqueuing {len(forecasts)} forecasts")
        queue = django_rq.get_queue(DEFAULT_QUEUE_NAME)
        for forecast in forecasts:
            queue.enqueue(_migrate_correctness_worker, forecast.pk)
        logger.info(f"enqueuing done")


#
# enqueue_migrate_worker()
#

@cli.command(name="migrate")
def enqueue_migrate_worker():
    """
    CLI that enqueues migration of all forecasts in every project in the database. NB: there should be no non-migration
    jobs running! We order by created_at to simulate how the forecasts were created as close as possible. This becomes
    an issue with respect to versioning of the same timezero: If we load a newer version first and then an older
    version, the latter will possibly have fewer post-migrate rows due to duplications. B/c workers are running in
    parallel, we cannot guarantee order, though. But this is the best we came up with.
    """
    from forecast_repo.settings.base import DEFAULT_QUEUE_NAME  # avoid circular imports


    logger.info(f"enqueuing ~{Forecast.objects.count()} forecasts")  # COUNT is somewhat expensive
    queue = django_rq.get_queue(DEFAULT_QUEUE_NAME)
    num_jobs = 0
    for project in Project.objects.all():  # iterate over projects b/c _grouped_version_rows() is by project
        logger.info(f"* {project}")
        # process forecast versions in issue_date order (created_at) to avoid out-of-sequence problems.
        # each row (ordered by issue_date): [fm_id, tz_id, issue_date, f_id, f_source, f_created_at, rank]:
        grouped_version_rows = _grouped_version_rows(project, False)  # is_versions_only
        for (fm_id, tz_id), grouper in groupby(grouped_version_rows, key=lambda _: (_[0], _[1])):
            logger.info(f"  {fm_id}, {tz_id}")
            versions = list(grouper)
            queue.enqueue(_migrate_forecast_worker, [version[3] for version in versions])  # f_id
            num_jobs += 1
            for _, _, issue_date, f_id, source, created_at, rank in versions:
                logger.info(f"    {issue_date}, {f_id}, {source}, {created_at}, {rank}")
    logger.info(f"enqueuing done. num_jobs={num_jobs}")


#
# load_forecasts_with_implicit_retractions()
#

@cli.command(name="load_implicit")
@click.argument('forecast_ids', type=click.STRING, required=True)
def load_forecasts_with_implicit_retractions(forecast_ids):
    """
    CLI that takes a comma-separated list of forecast IDs that failed migration due to:
    "new data is a subset of previous". It passes each one of these to
    pred_dicts_with_implicit_retractions() along with that forecast's immediate previous one and then loads the
    returned new data, which should not fail since it has the missing retractions.
    """
    logger.info(f"load_forecasts_with_implicit_retractions(): starting. forecast_ids={forecast_ids!r}")

    # validate forecast_ids
    forecast_ids = forecast_ids.split(',')
    for forecast_id_str in forecast_ids:
        try:
            int(forecast_id_str)
        except ValueError as ve:
            logger.error(f"forecast_id was not in int: {forecast_id_str!r}")
            return

    # all ints, so fill implicit retractions and the load, first deleting
    forecast_ids = list(map(int, forecast_ids))

    logger.info(f"deleting new data")
    PredictionElement.objects.filter(forecast__in=forecast_ids).delete()

    for forecast_id in forecast_ids:
        f2 = Forecast.objects.get(pk=forecast_id)
        f1 = _forecast_previous_version(f2)
        pred_eles_f1_not_in_f2, pred_dicts_with_retractions = pred_dicts_with_implicit_retractions(f1, f2)
        logger.info(f"loading modified f2 (forecast_id)={f2.pk}, f1 (previous)={f1.pk}, #pred_eles_f1_not_in_f2="
                    f"{len(pred_eles_f1_not_in_f2)}")
        try:
            load_predictions_from_json_io_dict(f2, {'meta': {}, 'predictions': pred_dicts_with_retractions})  # atomic
            cache_forecast_metadata(f2)  # atomic
        except Exception as ex:
            logger.error(f"error loading updated predictions: forecast_id={forecast_id}, ex={ex!r}")

    # done
    logger.info(f"load_forecasts_with_implicit_retractions(): done")


#
# delete_empty_forecasts_new()
#

@cli.command(name="delete_empty_forecasts")
@click.option('--dry-run/--no-dry-run', default=False)
def delete_empty_forecasts_new(dry_run):
    """
    CLI that deletes forecasts from all projects that contain no new data. NB: We process in a single thread, which
    allows us to delete in descending issue_date order, i.e., to delete newer then older versions. This is important
    b/c o/w we would break the forecast version rule: "you cannot delete a forecast that has any newer versions".
    """
    from django.db.models.signals import pre_delete  # avoid circular imports
    from forecast_app.models.forecast import pre_validate_deleted_forecast  # ""


    empty_forecast_ids = forecast_ids_with_no_data_new()
    logger.info(f"delete_empty_forecasts_new(): starting. dry_run={dry_run}, #empty_forecast_ids="
                f"{len(empty_forecast_ids)}")

    # disconnect the signal that validates the rule: "you cannot delete a forecast that has any newer versions". we do
    # this to avoid the "you cannot delete a forecast that has any newer versions" error, which does not apply in this
    # case b/c the deleting forecast is empty and therefore did not contribute to any duplicates being removed
    pre_delete.disconnect(receiver=pre_validate_deleted_forecast, sender=Forecast)

    for forecast in Forecast.objects.filter(pk__in=empty_forecast_ids).order_by('-issue_date'):
        if dry_run:
            logger.info(f"found empty forecast={forecast}")
        else:
            logger.info(f"deleting empty forecast={forecast}")
            try:
                forecast.delete()
            except Exception as ex:
                logger.error(f"error deleting empty forecast: forecast={forecast}, ex={ex!r}")
    logger.info(f"delete_empty_forecasts_new(): done. {'found' if dry_run else 'deleted'} {len(empty_forecast_ids)} "
                f"forecasts")


#
# ---- main ----
#

if __name__ == '__main__':
    cli()
