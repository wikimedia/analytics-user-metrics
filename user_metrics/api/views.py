"""
    This module defines the flask application and views utilizing flask
    functionality to define leverage Jinja2_ templating system.

    .. _Jinja2: http://jinja.pocoo.org/docs/

    View & Method Definitions
    ~~~~~~~~~~~~~~~~~~~~~~~~~
"""

__author__ = {
    "dario taraborelli": "dario@wikimedia.org",
    "ryan faulkner": "rfaulkner@wikimedia.org",
    "dan andreescu": "dandreescu@wikimedia.org"
}
__date__ = "2012-12-21"
__license__ = "GPL (version 2 or later)"

from flask import Flask, render_template, Markup, redirect, url_for, \
    request, escape, flash, jsonify, make_response

from user_metrics.etl.data_loader import Connector
from user_metrics.config import logging, settings
from user_metrics.api.engine.data import get_data, get_url_from_keys, \
    read_pickle_data
from user_metrics.api import error_codes, query_mod, \
    REQUEST_BROKER_TARGET, umapi_broker_context, RESPONSE_BROKER_TARGET, \
    PROCESS_BROKER_TARGET
from user_metrics.api.engine.request_meta import get_metric_names
from user_metrics.api.session import APIUser
import user_metrics.config.settings as conf
from hashlib import sha1

# upload files
import re
import csv
import json

UPLOAD_FOLDER = 'csv_uploads'
ALLOWED_EXTENSIONS = set(['csv'])


# Instantiate flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# REGEX to identify refresh flags in the URL
REFRESH_REGEX = r'refresh[^&]*&|\?refresh[^&]*$|&refresh[^&]*$'


def get_errors(request_args):
    """ Returns the error string given the code in request_args """
    error = ''
    if 'error' in request_args:
        try:
            error = error_codes[int(request_args['error'])]
        except (KeyError, ValueError):
            pass
    return error


# Views
# #####

# Flask Login views

if settings.__flask_login_exists__:

    from flask.ext.login import login_required, logout_user, \
        confirm_login, login_user, fresh_login_required, current_user

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST' and 'username' in request.form:

            username = escape(unicode(str(request.form['username'])))
            passwd = escape(unicode(str(request.form['password'])))
            remember = request.form.get('remember', 'no') == 'yes'

            # Initialize user
            user_ref = APIUser(username)
            user_ref.authenticate(passwd)

            logging.debug(__name__ + ' :: Authenticating "{0}"/"{1}" ...'.
                format(username, passwd))

            if user_ref.is_authenticated():
                login_user(user_ref, remember=remember)
                flash('Logged in.')
                return redirect(request.args.get('next')
                                or url_for('api_root'))
            else:
                flash('Login failed.')
        return render_template('login.html')

    @app.route('/reauth', methods=['GET', 'POST'])
    @login_required
    def reauth():
        if request.method == 'POST':
            confirm_login()
            flash(u'Reauthenticated.')
            return redirect(request.args.get('next') or url_for('api_root'))
        return render_template('reauth.html')

    @app.route('/logout')
    def logout():
        logout_user()
        flash('Logged out.')
        return redirect(url_for('api_root'))

else:

    def login_required(f):
        """ Does Nothing."""
        def wrap(*args, **kwargs):
            f(*args, **kwargs)
        return wrap()


# API views

def api_root():
    """ View for root url - API instructions """
    #@@@ TODO make tag list generation a dedicated method
    conn = Connector(instance=settings.__cohort_data_instance__)
    conn._cur_.execute('select utm_name from usertags_meta')
    data = [r[0] for r in conn._cur_]
    del conn

    if settings.__flask_login_exists__ and current_user.is_anonymous():
        return render_template('index_anon.html', cohort_data=data,
                               m_list=get_metric_names())
    else:
        return render_template('index.html',
            cohort_data=data,
            m_list=get_metric_names(),
        )


def about():
    return render_template('about.html')


def contact():
    return render_template('contact.html')


def version():
    return render_template('version.html', version=conf.version)


def all_metrics():
    """ Display a list of available metrics """
    if request.method == 'POST':
        #@@@ TODO  validate form input against existing cohorts
        return metric(request.form['selectMetric'])
    else:
        return render_template('all_metrics.html')


def normalize_newlines(stream):
    for line in stream:
        if '\r' in line:
            for tok in line.split('\r'):
                yield tok
        else:
            yield line


def upload_csv_cohort():
    """ View for uploading and validating a new cohort via CSV """
    if request.method == 'GET':
        return render_template('csv_upload.html',
            wiki_projects=sorted(conf.PROJECT_DB_MAP.keys())
        )

    elif request.method == 'POST':
        try:
            cohort_file = request.files['csv_cohort']
            cohort_name = request.form['cohort_name']
            cohort_project = request.form['cohort_project']
            if not cohort_file or not cohort_name or len(cohort_name) is 0:
                flash('The form was invalid, please select a file and name the cohort.')
                return redirect('/uploads/cohort')
            
            if not query_mod.is_valid_cohort_query(cohort_name):
                flash('That Cohort name is already taken.')
                return redirect('/uploads/cohort')
            
            unparsed = csv.reader(normalize_newlines(cohort_file.stream))
            unvalidated = parse_records(unparsed, cohort_project)
            (valid, invalid) = validate_records(unvalidated)
            
            return render_template('csv_upload_review.html',
                valid=valid,
                invalid=invalid,
                valid_json=to_safe_json(valid),
                invalid_json=to_safe_json(invalid),
                cohort_name=cohort_name,
                cohort_project=cohort_project,
                wiki_projects=sorted(conf.PROJECT_DB_MAP.keys())
            )
        except Exception, e:
            logging.exception(str(e))
            flash('The file you uploaded was not in a valid format, could not be validated, or the project you specified is not configured on this instance of User Metrics API.')
            return redirect('/uploads/cohort')

def to_safe_json(s):
    return json.dumps(s).replace("'", "\\'").replace('"','\\"')

def validate_cohort_name_allowed():
    cohort = request.args.get('cohort_name')
    available = query_mod.is_valid_cohort_query(cohort)
    return json.dumps(available)

def parse_records(records, default_project):
    # NOTE: the reason for the crazy -1 and comma joins
    # is that some users can have commas in their name
    # TODO: This makes it impossible to add fields to the csv in the future,
    # so maybe require the project to be the first field and the username to be the last
    # or maybe change to a tsv format
    return [{
        'username': parse_username(",".join([str(p) for p in r[:-1]])),
        'project': r[-1].decode('utf8') if len(r) > 1 else default_project
    } for r in records if r]

def parse_username(raw_name):
    stripped = str(raw_name).decode('utf8').strip()
    # unfortunately .title() or .capitalize() don't work
    # because 'miliMetric'.capitalize() == 'Milimetric'
    return stripped[0].upper() + stripped[1:]

def normalize_project(project):
    project = project.strip().lower()
    if project in conf.PROJECT_DB_MAP:
        return project
    else:
        # try adding wiki to end
        new_proj = project + 'wiki'
        if new_proj not in conf.PROJECT_DB_MAP:
            return None
        else:
            return new_proj

def normalize_user(user_str, project):
    user_str_sql_safe = user_str.encode('utf-8')
    uid = query_mod.is_valid_username_query(user_str_sql_safe, project)
    if uid is not None:
        return (uid, user_str)
    elif user_str.isdigit():
        username = query_mod.is_valid_uid_query(user_str_sql_safe, project)
        if username is not None:
            return (user_str, username)
        else:
            return None
    else:
        return None

def deduplicate(list_of_objects, key_function):
    uniques = dict()
    for o in list_of_objects:
        key = key_function(o)
        if not key in uniques:
            uniques[key] = o
    
    return uniques.values()

def project_name_for_link(project):
    if project.endswith('wiki'):
        return project[:len(project)-4]
    return project

def link_to_user_page(username, project):
    project = project_name_for_link(project)
    return 'https://%s.wikipedia.org/wiki/User:%s' % (project, username)

def validate_records(records):
    valid = []
    invalid = []
    for record in records:
        record['user_str'] = record['username']
        normalized_project = normalize_project(record['project'])
        if normalized_project is None:
            record['reason_invalid'] = 'invalid project: %s' % record['project']
            invalid.append(record)
            continue
        normalized_user = normalize_user(record['user_str'], normalized_project)
        # make a link to the potential user page even if user doesn't exist
        # this gives a chance to see any misspelling etc.
        record['link'] = link_to_user_page(record['username'], normalized_project)
        if normalized_user is None:
            logging.debug('invalid: %s', record['user_str'])
            record['reason_invalid'] = 'invalid user_name / user_id: %s' % record['user_str']
            invalid.append(record)
            continue
        # set the normalized values and append to valid
        logging.debug('found a valid user_str: %s', record['user_str'])
        record['project'] = normalized_project
        record['user_id'], record['username'] = normalized_user
        valid.append(record)
    
    valid = deduplicate(valid, lambda record: record['username'])
    return (valid, invalid)


def upload_csv_cohort_finish():
    try:
        cohort_name = request.form.get('cohort_name')
        project = request.form.get('cohort_project')
        users_json = request.form.get('users')
        users = json.loads(users_json)
        # re-validate
        available = query_mod.is_valid_cohort_query(cohort_name)
        if not available:
            raise Exception('Cohort name `%s` is no longer available' % (cohort_name))
        
        # TODO: re-enable validation when either
        # 1. the site is used by external, potentially untrusted users
        # 2. the performance of validation is improved
        #(valid, invalid) = validate_records(users)
        #if invalid:
            #raise Exception('Cohort changed since last validation')
        # save the cohort
        valid = users
        
        if not project:
            if all([user['project'] == users[0]['project'] for user in users]):
                project = users[0]['project']
        logging.debug('adding cohort: %s, with project: %s', cohort_name, project)
        owner_id = current_user.id
        query_mod.create_cohort(cohort_name, project, owner=owner_id)
        query_mod.add_cohort_users(cohort_name, valid)
        return url_for('cohort', cohort=cohort_name)
        
    except Exception, e:
        logging.exception(str(e))
        flash('There was a problem finishing the upload.  The cohort was not saved.')
        return '<<error>>'


def metric(metric=''):
    """ Display single metric documentation """
    #@@@ TODO make tag list generation a dedicated method
    conn = Connector(instance=settings.__cohort_data_instance__)
    conn._cur_.execute('select utm_name from usertags_meta')
    data = [r[0] for r in conn._cur_]
    del conn
    #@@@ TODO validate user input against list of existing metrics
    return render_template('metric.html', m_str=metric, cohort_data=data)


def all_cohorts():
    """ View for listing and selecting cohorts """
    error = get_errors(request.args)

    #@@@ TODO  form validation against existing cohorts and metrics
    if request.method == 'POST':
        #@@@ TODO  validate form input against existing cohorts
        return cohort(request.form['selectCohort'])
    else:
        #@@@ TODO make tag list generation a dedicated method
        conn = Connector(instance=settings.__cohort_data_instance__)
        conn._cur_.execute('select distinct utm_name from usertags_meta')
        o = [r[0] for r in conn._cur_]
        del conn
        return render_template('all_cohorts.html', data=o, error=error)


def cohort(cohort=''):
    """ View single cohort page """
    error = get_errors(request.args)

    # @TODO CALL COHORT VALIDATION HERE

    if not cohort:
        return redirect(url_for('all_cohorts'))
    else:
        #return render_template('cohort.html', c_str=cohort,
                               #m_list=get_metric_names(), error=error, members=get_users(cohort))
        return render_template('cohort.html', c_str=cohort,
                               m_list=get_metric_names(), error=error)


def output(cohort, metric):
    """
    View corresponding to a data request.  Fetches response if it exists or adds
    request to the request broker target.

    TODO - change app.route to accept regex to avoid passing unused vars
    """

    # Check for refresh flag
    refresh = True if 'refresh' in request.args else False

    # Generate url hash - replace 'refresh' in url
    url = re.sub(REFRESH_REGEX, '', request.script_root + request.path)
    url = re.sub('/cohorts/', '', url)
    url_hash = sha1(url.encode('utf-8')).hexdigest()

    # Determine whether result is already cached
    data = get_data(url)

    # Is the request already running or queued?
    is_queued = umapi_broker_context.is_item(REQUEST_BROKER_TARGET, url_hash)
    is_running = umapi_broker_context.is_item(PROCESS_BROKER_TARGET, url_hash)

    logging.info(__name__ + ' :: REQ {0}:{1}\n\tqueued={2}\n\tprocessing={3}'.
        format(url_hash, url, str(is_queued), str(is_running)))

    # Determine if response is already cached
    if data and not refresh:
        return make_response(jsonify(data))

    # Determine if the job is already queued
    elif is_queued:
        return render_template('processing.html', error=error_codes[6])

    # Determine if the job is already running
    elif is_running:
        return render_template('processing.html', error=error_codes[0])

    # Add the request to the queue
    else:
        umapi_broker_context.add(REQUEST_BROKER_TARGET, url_hash, url)
        return render_template('processing.html')


def job_queue():
    """ View for listing current jobs working """

    error = get_errors(request.args)

    p_list = list()
    p_list.append(Markup('<thead><tr><th>state</th><th>url'
                         '</th></tr></thead>\n<tbody>\n'))

    # Get keys from broker targets
    items_req = umapi_broker_context.get_all_items(REQUEST_BROKER_TARGET)
    items_res = umapi_broker_context.get_all_items(RESPONSE_BROKER_TARGET)
    items_proc = umapi_broker_context.get_all_items(PROCESS_BROKER_TARGET)

    for item in items_req:
        url = item[item.keys()[0]]
        row_markup = '<tr><td>{0}</td><td><a href="{1}">{2}</a></td></tr>'\
            .format('request pending', url, url)
        p_list.append(Markup(row_markup))

    for item in items_res:
        url = item[item.keys()[0]]
        row_markup = '<tr><td>{0}</td><td><a href="{1}">{2}</a></td></tr>'\
            .format('response generating', url, url)
        p_list.append(Markup(row_markup))

    for item in items_proc:
        url = item[item.keys()[0]]
        row_markup = '<tr><td>{0}</td><td><a href="{1}">{2}</a></td></tr>'\
            .format('processing', url, url)
        p_list.append(Markup(row_markup))

    if error:
        return render_template('queue.html', procs=p_list, error=error)
    else:
        return render_template('queue.html', procs=p_list)


def all_urls():
    """ View for listing all requests.  Retrieves from cache """

    # @TODO - this reads the entire cache into memory, filters will be needed
    # This extracts ALL data from the cache, the data is assumed to be in the
    # form of <hash key -> (data, key signature)> pairs.  The key signature is
    # extracted to reconstruct the url.

    all_data = read_pickle_data()
    key_sigs = list()

    for key, val in all_data.iteritems():
        if hasattr(val, '__iter__'):
            try:
                key_sigs.append(val[1])
            except (KeyError, IndexError):
                logging.error(__name__ + ' :: Could not render key signature '
                                         'from data, key = {0}'.format(key))

    # Compose urls from key sigs
    url_list = list()
    for key_sig in key_sigs:

        url = get_url_from_keys(key_sig, 'cohorts/')
        url_list.append("".join(['<a href="',
                                 request.url_root, url + '">',
                                 url,
                                 '</a>']))
    return render_template('all_urls.html', urls=url_list)


def thin_client_view():
    """
        View for handling requests outside sessions.  Useful for processing
        jobs from https://github.com/rfaulkner/umapi_client.

        Returns:

            1) JSON response if the request is complete
            2) Validation response (minimal size)
    """

    # Validate key
    # Construct request meta
    # Check for job cached
    #   If YES return
    #   If NO queue job, return verify

    return None


# Add View Decorators
# ##

# Stores view references in structure
view_list = {
    api_root.__name__: api_root,
    all_urls.__name__: all_urls,
    job_queue.__name__: job_queue,
    output.__name__: output,
    cohort.__name__: cohort,
    all_cohorts.__name__: all_cohorts,
    metric.__name__: metric,
    all_metrics.__name__: all_metrics,
    about.__name__: about,
    contact.__name__: contact,
    thin_client_view.__name__: thin_client_view,
    upload_csv_cohort.__name__: upload_csv_cohort,
    upload_csv_cohort_finish.__name__: upload_csv_cohort_finish,
    validate_cohort_name_allowed.__name__: validate_cohort_name_allowed,
    version.__name__: version
}

# Dict stores routing paths for each view
route_deco = {
    api_root.__name__: app.route('/'),
    all_urls.__name__: app.route('/all_requests'),
    job_queue.__name__: app.route('/job_queue/'),
    output.__name__: app.route('/cohorts/<string:cohort>/<string:metric>'),
    cohort.__name__: app.route('/cohorts/<string:cohort>'),
    all_cohorts.__name__: app.route('/cohorts/', methods=['POST', 'GET']),
    metric.__name__: app.route('/metrics/<string:metric>'),
    all_metrics.__name__: app.route('/metrics/', methods=['POST', 'GET']),
    about.__name__: app.route('/about/'),
    contact.__name__: app.route('/contact/'),
    thin_client_view.__name__: app.route('/thin/<string:cohort>/<string:metric>'),
    upload_csv_cohort_finish.__name__: app.route('/uploads/cohort/finish', methods=['POST']),
    upload_csv_cohort.__name__: app.route('/uploads/cohort', methods=['POST', 'GET']),
    validate_cohort_name_allowed.__name__: app.route('/validate/cohort/allowed', methods=['GET']),
    version.__name__: app.route('/version')
}

# Dict stores flag for login required on view
views_with_anonymous_access = [
    api_root.__name__,
    all_metrics.__name__,
    about.__name__,
    contact.__name__,
    thin_client_view.__name__
]

# Apply decorators to views

if settings.__flask_login_exists__:
    for key in view_list:
        if key not in views_with_anonymous_access:
            view_list[key] = login_required(view_list[key])

for key in route_deco:
    route = route_deco[key]
    view_method = view_list[key]
    view_list[key] = route(view_method)

