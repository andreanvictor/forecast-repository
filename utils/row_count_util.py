import click
import django


# set up django. must be done before loading models. NB: requires DJANGO_SETTINGS_MODULE to be set
django.setup()

from forecast_app.models import Project

from forecast_app.models.row_count_cache import enqueue_row_count_updates_all_projs



@click.group()
def cli():
    pass


@cli.command(name="print")
def print_counts():
    """
    A subcommand that prints all projects' RowCountCaches. Runs in the calling thread and therefore blocks.
    """
    click.echo("RowCountCaches:")
    for project in Project.objects.all():
        click.echo("- {} | {} | {}"
                   .format(project, project.row_count_cache.row_count, project.row_count_cache.updated_at))


@cli.command()
def clear():
    """
    A subcommand that resets all projects' RowCountCaches. Runs in the calling thread and therefore blocks.
    """
    click.echo("clearing all projects' RowCountCaches")
    for project in Project.objects.all():
        click.echo("- clearing {}".format(project))
        project.row_count_cache.row_count = None
        project.row_count_cache.save()
    click.echo("clear done")


@cli.command()
def update():
    """
    A subcommand that enqueues updating all projects' RowCountCaches.
    """
    click.echo("enqueuing all projects' RowCountCaches")
    enqueue_row_count_updates_all_projs()
    click.echo("enqueuing done")


if __name__ == '__main__':
    cli()
