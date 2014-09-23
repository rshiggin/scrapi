#!/usr/bin/env python
from datetime import date, timedelta
import time
import xmltodict
import requests
from lxml import etree
from xml.parsers import expat
from scrapi_tools import lint
from scrapi_tools.document import RawDocument, NormalizedDocument

TODAY = date.today()
NAME = "ClinicalTrials"

def consume(days_back=4):
    """ First, get a list of all recently updated study urls,
    then get the xml one by one and save it into a list 
    of docs including other information """

    start_date = TODAY - timedelta(days_back)

    month = TODAY.strftime('%m')
    day = TODAY.strftime('%d') 
    year = TODAY.strftime('%Y')

    y_month = start_date.strftime('%m')
    y_day = start_date.strftime('%d')
    y_year = start_date.strftime('%Y')

    base_url = 'http://clinicaltrials.gov/ct2/results?lup_s=' 
    url_end = '{}%2F{}%2F{}%2F&lup_e={}%2F{}%2F{}&displayxml=true'.\
                format(y_month, y_day, y_year, month, day, year)

    url = base_url + url_end

    # grab the total number of studies
    initial_request = requests.get(url)
    initial_request = xmltodict.parse(initial_request.text) 
    count = initial_request['search_results']['@count']

    xml_list = []
    if int(count) > 0:
        # get a new url with all results in it
        url = url + '&count=' + count
        print url
        total_requests = requests.get(url)
        response = xmltodict.parse(total_requests.text)

        # make a list of urls from that full list of studies
        study_urls = []
        for study in response['search_results']['clinical_study']:
            study_urls.append(study['url'] + '?displayxml=true')

        # grab each of those urls for full content
        for study_url in study_urls[:10]:
            content = requests.get(study_url)
            try:
                xml_doc = xmltodict.parse(content.text)
            except expat.ExpatError:
                print 'xml reading error for ' + study_url
                pass
            doc_id = xml_doc['clinical_study']['id_info']['nct_id']
            xml_list.append(RawDocument({
                    'doc': content.content,
                    'source': NAME,
                    'doc_id': doc_id,
                    'filetype': 'xml',
                }))
            time.sleep(1)

        if int(count) == 0:
            print "No new or updated studies!"
        else: 
            pass

    return xml_list


def normalize(raw_doc, timestamp):
    raw_doc = raw_doc.get('doc')
    try:
        result = xmltodict.parse(raw_doc)
    except expat.ExpatError:
        print 'xml reading error...'
        pass

    xml_doc = etree.XML(raw_doc)

    # Title
    try: 
        title = result['clinical_study']['official_title']
    except KeyError:
        try:
            title = result['clinical_study']['brief_title']
        except KeyError:
            title = 'No title available'
            pass

    # contributors
    contributor_list = xml_doc.xpath('//overall_official/last_name/node()') or xml_doc.xpath('//lead_sponsor/agency/node()') or ['No contributors']
    contributors = [{'full_name': contributor_list[0], 'email': ''}]

    # abstract
    try:
        abstract = result['clinical_study']['brief_summary'].get('textblock')
    except KeyError:
        try:
            abstract = result['clinical_study']['detailed_description'].get('textblock')
        except KeyError:
            abstract = 'No abstract available'

    # IDs
    try: 
        nct_id = result['clinical_study']['id_info']['nct_id']
    except KeyError:
        nct_id = 'Secondary ID: ' + result['clinical_study']['id_info'].get('secondary_id')
    url = result['clinical_study']['required_header'].get('url')
    ids = {'service_id': nct_id, 'doi': '', 'url': url}

    # date created
    date_created = result['clinical_study'].get('firstreceived_date')

    # tags/keywords
    keywords = xml_doc.xpath('//keyword/node()')

    lead_sponsor  = {
            'agency': (xml_doc.xpath('//lead_sponsor/agency/node()') or [''])[0],
            'agency_class': (xml_doc.xpath('//lead_sponsor/agency_class/node()') or [''])[0]
        }

    primary_outcome = {
            'measure': (xml_doc.xpath('//primary_outcome/measure/node()') or [''])[0],
            'time_frame': (xml_doc.xpath('//primary_outcome/time_frame/node()') or [''])[0],
            'safety_issue': (xml_doc.xpath('//primary_outcome/safety_issue/node()') or [''])[0]
        }

    ## extra properties ##
    properties = {
        'sponsors': lead_sponsor,
        'oversight_authority': xml_doc.xpath('//oversigh_info/authority/node()'),
        'study_design': (xml_doc.xpath('//study_design/node') or [''])[0],
        'primary_outcome': primary_outcome,
        'source': (xml_doc.xpath('//source/node()') or [''])[0],
        'condition': (xml_doc.xpath('//condition/node()') or [''])[0], 
        'last_changed': (xml_doc.xpath('//lastchanged_date/node()') or [''])[0],
        'status': (xml_doc.xpath('//status/node()') or [''])[0],
        'location_countries': xml_doc.xpath('//location_countries/country/node()')
    }

    normalized_dict = {
            'title': title,
            'contributors': contributors,
            'properties': properties,
            'description': abstract,
            'meta': {},
            'id': ids,
            'source': NAME,
            'tags': keywords,
            'date_created': date_created,
            'timestamp': str(timestamp)
    }

    print normalized_dict['properties']
    return NormalizedDocument(normalized_dict)



if __name__ == '__main__':
    print(lint(consume, normalize))