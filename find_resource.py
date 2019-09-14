"""
FindResource
------------
Retrieve a resource ID from AWS for use in a CloudFormation Stack
"""

import awsapi_helpers
import boto3
import logging

LOGGER = logging.getLogger(__name__)
FORMAT = '%(asctime)s %(module)s.py:%(funcName)s, line %(lineno)s, %(levelname)s - %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)

def send_response(event, context, status, data=None):

	response_url = None

	if 'ResponseUrl' in event:
    	response_url = event['ResponseURL']
    else:
		LOGGER.warning('Request did not contain a ResponseUrl.')
        return 500

    response_body = {}
    response_body['Status'] = status
    response_body['Reason'] = 'Log Stream=%s' % context.log_stream_name
    response_body['PhysicalResourceId'] = context.log_stream_name
    response_body['StackId'] = event['StackId'] if 'StackId' in event else "Unknown StackId"
    response_body['RequestId'] = event['RequestId'] if 'RequestId' in event else "Unknown RequestId"
    response_body['LogicalResourceId'] = (event['LogicalResourceId'] if 'LogicalResourceId' in event
                                          else "Unknown LogicalResourceId")

    response_body['Data'] = data if data else {}
    json_body = json.dumps(response_body)
    LOGGER.debug("Response %s" % json_body)
    headers = {
        'content-type': '',
        'content-length': str(len(json_body))
    }

    try:
        response = requests.put(response_url, data=json_body, headers=headers, proxies=PROXIES)

    except Exception as e:
        LOGGER.error("Failed to send response. stack-id=%(stack)s, resource-type=%(rt)s, err=%(err)s, url=%(url)s" %
                  {'stack': event['StackId'],
                   'rt': event['ResourceType'],
                   'err': e,
                   'url': response_url})
        return 500

    else:
        LOG.info("Response sent, status=%(code)s, url=%(url)s" %
                 {'code': response.reason, 'url': response_url})
        return response.reason

def lambda_handler(event, context):

	response = {}

	if 'RequestType' not in event:
		event['RequestType'] = 'search'

	if event['RequestType'].lower() == 'delete':
		send_response(event, context, SUCCESS)
		return

	elif event['RequestType'].lower() == 'update':
		pass

	# Do stuff
	# - Call a helper
	# - get the status
	# - send the response
	# - return



    send_response(event, context, status, response)
    return response