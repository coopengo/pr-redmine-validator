# -*- coding: utf-8 -*-
import os
import json
import requests
import traceback

from flask import Flask, request

with open(os.environ.get('HOOK_CONFIG_FILE'), 'r') as conf_file:
    config = json.loads(conf_file.read())

GITHUB_TOKEN = config['github_token']
REDMINE_URL = config['redmine_url']
REDMINE_TOKEN = config['redmine_token']
REDMINE_BUG_IDS = config['redmine_bug_ids']
REDMINE_FEATURE_IDS = config['redmine_feature_ids']
ALLOWED_PROJECTS = config['redmine_project_matches']
DESCRIPTIONS = config['description_urls']

app = Flask(__name__)


@app.route('/', methods=['POST'])
def git_hook():
    try:
        data = json.loads(request.data)
        if 'pull_request' not in data:
            return
        # Title modification :
        #    data['action'] == 'edited'
        #    'title' in data['changes']

        # Body modification :
        #    data['action'] == 'edited'
        #    'body' in data['changes']

        # New PR :
        #    data['action'] == 'opened'

        # Label added :
        #    data['action'] == 'labeled'
        #    data['label']['name'] => 'bug'

        # Label removed :
        #    data['action'] == 'unlabeled'
        #    data['label']['name'] => 'bug'

        # Get all labels :
        #   requests.get(data['pull_request']['_links']['issue'] + '/labels' +
        #       '?access_GITHUB_TOKEN=' + github_token)

        # Pull request updated :
        #   data['action'] == 'synchronize'

        # Pull request target :
        #   data['pull_request']['base']['repo']['full_name'] ==
        #       'coopengo/coog'

        messages = []
        print 'Received status %s' % data['action']
        if data.get('action', '') in 'edited' and ('title' in data['changes']
                or 'body' in data['changes']) or data.get('action', '') in (
                'labeled', 'unlabeled', 'opened', 'synchronize'):
            messages.append(check_title(data))
            messages.append(check_body(data))
            messages.append(check_labels(data))
            messages.append(check_contents(data))
        print 'Done'
    except:
        messages = [
            ('error', x, 'CRASH !')
            for x in ('commit_title', 'commit_body', 'labels', 'contents')]
        traceback.print_exc()
    finally:
        if 'pull_request' in data:
            for state, context, description in messages:
                payload = {
                    'state': state,
                    'context': 'testing/' + context,
                    'target_url': DESCRIPTIONS[context],
                    'description': description,
                    }
                url = (data['repository']['statuses_url'][:-5] +
                    data['pull_request']['head']['sha'] + '?access_token=' +
                    GITHUB_TOKEN)
                requests.post(url, data=json.dumps(payload))
        return 'OK'


def get_labels(data):
    if 'labels' in data:
        return data['labels']
    labels = requests.get(
        data['pull_request']['_links']['issue']['href'] +
        '/labels' + '?access_token=' + GITHUB_TOKEN).json()
    data['labels'] = [x['name'] for x in labels]
    return data['labels']


def get_redmine_reference(data):
    if 'redmine_issue' in data:
        return data['redmine_issue'], data['redmine_type']
    data['redmine_issue'] = None
    data['redmine_type'] = None
    last_line = data['pull_request']['body'].split('\n')[-1]
    if not last_line.startswith('Fix #') and not last_line.startswith('Ref #'):
        return
    try:
        data['redmine_issue'] = last_line[5:]
        data['redmine_type'] = last_line[0:3]
        return data['redmine_issue'], data['redmine_type']
    except:
        return


def get_redmine_data(data):
    if 'redmine_data' in data:
        return data['redmine_data']
    number = get_redmine_reference(data)[0]
    data['redmine_data'] = requests.get(REDMINE_URL + '/issues/' + number +
            '.json', auth=(REDMINE_TOKEN, ''), verify=False).json()['issue']
    return data['redmine_data']


def get_pull_request_files(data):
    if 'pr_files' in data:
        return data['pr_files']
    data['pr_files'] = requests.get(
            data['pull_request']['_links']['self']['href'] + '/files' +
            '?access_token=' + GITHUB_TOKEN).json()
    return data['pr_files']


def check_title(data):
    if 'bypass title check' in get_labels(data):
        return ('success', 'commit_title', 'FORCED')
    title = data['pull_request']['title']
    if ': ' not in title:
        return ('failure', 'commit_title',
            'Expected "<module>: <short title>"')
    elif title.endswith(u'…'):
        return ('failure', 'commit_title', 'Title cannot end with "..."')
    else:
        return ('success', 'commit_title', '')


def check_body(data):
    if 'bypass body check' in get_labels(data):
        return ('success', 'commit_body', 'FORCED')
    body = data['pull_request']['body']
    if body == '':
        return ('failure', 'commit_body', 'Empty body')
    if not get_redmine_reference(data):
        return ('failure', 'commit_body',
            'Missing or malformed redmine reference')
    lines = body.split('\n')
    if len(lines) > 1:
        if lines[-2].strip() != '':
            return ('failure', 'commit_body',
                'Missing empty line before redmine reference')
    return ('success', 'commit_body', '')


def check_labels(data):
    labels = get_labels(data)
    if 'bypass label check' in labels:
        return ('success', 'labels', 'FORCED')
    if 'bug' not in labels and 'enhancement' not in labels:
        return ('failure', 'labels', 'No bug or enhancement labels found')
    if 'bug' in labels and 'enhancement' in labels:
        return ('failure', 'labels',
            'Cannot have both "bug" and "enhancement" label')
    redmine_number, redmine_type = get_redmine_reference(data)
    if not redmine_number:
        return ('failure', 'labels', 'Cannot find redmine issue')
    try:
        redmine_data = get_redmine_data(data)
    except:
        traceback.print_exc()
        return ('error', 'labels', 'Error accessing redmine')
    if 'bug' in labels:
        if (redmine_type == 'Fix' and
                redmine_data['tracker']['id'] not in REDMINE_BUG_IDS):
            return ('failure', 'labels', 'Issue %s is not a bug !'
                % redmine_number)
        elif (redmine_type == 'Ref' and
                redmine_data['tracker']['id'] not in REDMINE_FEATURE_IDS):
            return ('failure', 'labels', 'Ref %s is not a feature !'
                % redmine_number)
    if 'enhancement' in labels:
        if redmine_data['tracker']['id'] not in REDMINE_FEATURE_IDS:
            return ('failure', 'labels', 'Issue %s is not a feature !'
                % redmine_number)
    if redmine_data['project']['id'] not in [x[0] for x in ALLOWED_PROJECTS[
                data['pull_request']['base']['repo']['full_name']]]:
        print ALLOWED_PROJECTS[
                data['pull_request']['base']['repo']['full_name']]
        print redmine_data['project']['id']
        return ('failure', 'labels', 'Bad project for issue %s'
            % redmine_number)
    if 'bug' in labels and 'cherry checked' not in labels:
        return ('failure', 'labels', 'Missing cherry check')
    return ('success', 'labels', '')


def check_contents(data):
    labels = get_labels(data)
    if 'bypass content check' in labels:
        return ('success', 'contents', 'FORCED')

    files = get_pull_request_files(data)
    if not files:
        return ('failure', 'contents', 'Empty pull request')
    file_paths = [x['filename'] for x in files]
    if 'enhancement' in labels:
        if not any(['features.rst' in x for x in file_paths]):
            return ('failure', 'contents', 'Missing doc for feature')
        if not any(['features_log' in x for x in file_paths]):
            return ('failure', 'contents', 'Missing log entry for ' 'feature')
    return ('success', 'contents', '')


if __name__ == '__main__':
    app.run()
