wmf_user_metrics
================


Introduction
------------

UserMetrics is a set of data analysis tools developed by the Wikimedia Foundation to measure on-site user activity via a set of standardized metrics. Using the modules in this package, a set of key metrics can be selected and applied to an arbitrary list of user IDs to measure their engagement and productivity. UserMetrics is designed for extensibility (creating new metrics, modifying metric parameters) and to support various types of cohort analysis and program evaluation in a user-friendly way. The methods are exposed via a RESTful API that can be used to generate requests and retrieve the results in JSON format.


Running on the Mediawiki Vagrant (for development)
--------------------------------------------------

We have added UserMetrics puppet configuration to [MediaWiki Vagrant][mediawiki_vagrant] to make it easy to get up and running.  Here's how:

Make sure you have vagrant and virtualbox installed.  For this humble author, Vagrant 1.1.2 and VirtualBox 4.2.8 worked well on Ubuntu.

    git clone https://gerrit.wikimedia.org/r/mediawiki/vagrant mediawiki-vagrant
    cd mediawiki-vagrant
    vagrant up
    vim puppet/manifests/site.pp

right under [this line][line_in_site_pp] add this line:

    class { 'user_metrics': }

then run puppet again:

    vagrant provision

Now you should be able to browse to [user metrics running locally][local_vagrant_user_metrics_server] and start working.  The code that's being served is under the user\_metrics folder and you can use that like any clone of a gerrit repository.


Setup a Virtual Environment
---------------------------

Note: instructions to install a virtualenv here - http://www.virtualenv.org/en/latest/.

Create virtualenv with `virtualenv <your virtualenv>`

Activate with `source <yourenv>/bin/activate`
 

Installing Umapi
----------------

Run `git clone ssh://rfaulk@gerrit.wikimedia.org:29418/analytics/user-metrics`

Navigate to `user-metrics` and run `pip install -e .`


Configure the clone
-------------------

In user_metrics/config run `cp settings.py.example settings.py` and configure as instructed below to point to datasources. Ensure that
datasource hosts are reachable from your environment.  To run the server execute:

	$ python user_metrics/api/run.py
	$ python user_metrics/api/run_handlers.py

The module run.py initiates the flask web server and is also the wsgi target if the instance is being run via Apache.
Also it is necessary to execute run_handlers.py which initiates the job handling processes.  If you are running the
service through Apache this module will need to be initiated independently, it utilizes the queues that are
visible to the http view targets.

Once installed you will need to modify the configuration files.  This
can be found in the file `settings.py` under
`$site-packages-home$/e3_analysis/config`.  Within this file configure
the connections dictionary to point to a replicated production MySQL instance
containing the .  The 'db' setting should be an instance which 'user' has write
access to.  If you are from outside the Wikimedia Foundation and do not have
access to these credentials please contact us at usermetrics@wikimedia.org if you'd
like to work with this package.

The template configuration file looks like the following:

    # Project settings
    # ================
    
    version = {% your version %}
    __project_home__ = realpath('../..') + '/'
    __web_home__ = ''.join([__project_home__, 'src/api/'])
    __data_file_dir__ = ''.join([__project_home__, 'data/'])

    __query_module__ = 'query_calls_noop'
    __user_thread_max__ = 100
    __rev_thread_max__ = 50

    # Database connection settings
    # ============================

    connections = {
        'slave': {
            'user' : 'research',
            'host' : '127.0.0.1',
            'db' : 'staging',
            'passwd' : 'xxxx',
            'port' : 3307},
        'slave-2': {
            'user' : 'rfaulk',
            'host' : '127.0.0.1',
            'db' : 'rfaulk',
            'passwd' : 'xxxx',
            'port' : 3307}
    }

    PROJECT_DB_MAP = {
        'enwiki': 's1',
        'dewiki': 's5',
        'itwiki': 's2',
    }

    # SSH Tunnel Parameters
    # =====================

    TUNNEL_DATA = {
        's1': {
            'cluster_host': 'stats',
            'db_host': 's1-db',
            'user': 'xxxx',
            'remote_port': 3306,
            'tunnel_port': 3307
        },
        's2': {
            'cluster_host': 'stats',
            'db_host': 's2-db',
            'user': 'xxxx',
            'remote_port': 3306,
            'tunnel_port': 3308
        }
    }

Documentation
-------------

Once the installation is complete and the configuration has been set the
modules can be imported into the Python environment.  The available
operational modules are the following:

    user_metrics.api
    user_metrics.api.run
    user_metrics.api.views

    user_metrics.api.engine
    user_metrics.api.engine.data
    user_metrics.api.engine.request_manager
    user_metrics.api.engine.request_meta

    user_metrics.etl
    user_metrics.etl.data_loader
    user_metrics.etl.aggregator
    user_metrics.etl.table_loader
    user_metrics.etl.log_parser
    user_metrics.etl.time_series_process_methods
    user_metrics.etl.wpapi

    user_metrics.metrics
    user_metrics.metrics.blocks
    user_metrics.metrics.bytes_added
    user_metrics.metrics.live_account.pyc
    user_metrics.metrics.edit_count
    user_metrics.metrics.edit_rate
    user_metrics.metrics.live_account
    user_metrics.metrics.metrics_manager
    user_metrics.metrics.namespace_of_edits
    user_metrics.metrics.query_calls
    user_metrics.metrics.revert_rate
    user_metrics.metrics.survival
    user_metrics.metrics.time_to_threshold
    user_metrics.metrics.user_metric
    user_metrics.metrics.users

    user_metrics.query
    user_metrics.query.query_calls_noop
    user_metrics.query.query_calls_sql

    user_metrics.utils
    user_metrics.utils.autovivification
    user_metrics.utils.multiprocessing_wrapper
    user_metrics.utils.record_type


Links
-----

- UserMetrics API: http://metrics.wikimedia.org
- Project homepage: https://www.mediawiki.org/wiki/UserMetrics
- Code documentation: http://stat1.wikimedia.org/rfaulk/pydocs/_build/


[mediawiki_vagrant]: https://github.com/wikimedia/mediawiki-vagrant "MediaWiki Vagrant on GitHub"
[line_in_site_pp]: https://github.com/wikimedia/mediawiki-vagrant/blob/53ee094f122dd58c61eae7c7de453e09051d309d/puppet/manifests/site.pp#L54 "class { 'mediawiki': }"
[local_vagrant_user_metrics_server]: 10.11.12.13:8182 "Local User Metrics Server"
