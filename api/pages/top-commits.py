#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This is the TopN repos by commits list renderer for Kibble
"""

import json
import time
import re

def run(API, environ, indata, session):
    
    # We need to be logged in for this!
    if not session.user:
        raise API.exception(403, "You must be logged in to use this API endpoint! %s")
    
    now = time.time()
    
    # First, fetch the view if we have such a thing enabled
    viewList = []
    if indata.get('view'):
        if session.DB.ES.exists(index=session.DB.dbname, doc_type="view", id = indata['view']):
            view = session.DB.ES.get(index=session.DB.dbname, doc_type="view", id = indata['view'])
            viewList = view['_source']['sourceList']
    
    dateTo = indata.get('to', int(time.time()))
    dateFrom = indata.get('from', dateTo - (86400*30*3)) # Default to a 3 month span
    
    ####################################################################
    ####################################################################
    dOrg = session.user['defaultOrganisation'] or "apache"
    query = {
                'query': {
                    'bool': {
                        'must': [
                            {'range':
                                {
                                    'tsday': {
                                        'from': dateFrom,
                                        'to': dateTo
                                    }
                                }
                            },
                            {
                                'term': {
                                    'organisation': dOrg
                                }
                            }
                        ]
                    }
                }
            }
    if viewList:
        query['query']['bool']['must'].append({'terms': {'sourceID': viewList}})
    
    
    # Get top 25 committers this period
    query['aggs'] = {
            'by_repo': {
                'terms': {
                    'field': 'sourceURL',
                    'size': 5000
                }                
            }
        }
    res = session.DB.ES.search(
            index=session.DB.dbname,
            doc_type="code_commit",
            size = 0,
            body = query
        )
    
    toprepos = []
    for bucket in res['aggregations']['by_repo']['buckets']:
        repo = re.sub(r".+/([^/]+?)(?:\.git)?$", r"\1", bucket['key'])
        count = bucket['doc_count']
        
        toprepos.append([repo, count])
        
    toprepos = sorted(toprepos, key = lambda x: x[1], reverse = True)
    top = toprepos[0:24]
    if len(toprepos) > 25:
        count = 0
        for repo in toprepos[25:]:
            count += repo[1]
        top.append(["Other repos", count])
    
    tophash = {}
    for v in top:
        tophash[v[0]] = v[1]
        
    JSON_OUT = {
        'counts': tophash,
        'okay': True,
        'responseTime': time.time() - now,
    }
    yield json.dumps(JSON_OUT)
